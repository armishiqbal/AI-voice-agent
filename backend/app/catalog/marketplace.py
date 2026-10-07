"""Tenant-authorized submissions and platform-controlled publication."""

# FastAPI resolves validated dependencies from endpoint signatures.
# ruff: noqa: B008
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, update

from app.catalog.identity import Identity, require_identity
from app.catalog.staff import StaffListingCreate, StaffListingPatch, _slugify, _staff_listing
from app.catalog.staff_auth import StaffPrincipal, require_roles
from app.core.config import settings
from app.core.pii import ContactCipher
from app.domain.models import AppointmentUpdate
from app.repositories.appointments import SqlAppointmentService
from app.repositories.database import SessionLocal
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    AgentScheduleRecord,
    AppointmentRecord,
    ListingRevisionRecord,
    LocationRecord,
    MarketplaceAuditRecord,
    MembershipRecord,
    OrganizationRecord,
    OutboxEventRecord,
    PropertyMediaRecord,
    PropertyRecord,
    WebsiteInquiryRecord,
)

agency = APIRouter(prefix="/v1/agency/{organization_id}", tags=["agency workspace"])
platform = APIRouter(prefix="/v1/staff/marketplace", tags=["marketplace moderation"])


def authorize(session, organization_id: str, identity: Identity, manager: bool = False):
    if not settings.marketplace_enabled:
        raise HTTPException(503, "Marketplace submissions are paused")
    org = session.get(OrganizationRecord, organization_id)
    member = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.organization_id == organization_id,
            MembershipRecord.subject == identity.subject,
            MembershipRecord.active.is_(True),
        )
    )
    if not org or org.status != "approved" or not member or identity.assurance != "aal2":
        raise HTTPException(403, "Active membership and authenticator MFA are required")
    if manager and member.role not in {"administrator", "manager"}:
        raise HTTPException(403, "Agency management permission is required")
    return member


def owned(session, organization_id, property_id, member):
    record = session.get(PropertyRecord, property_id)
    if not record or record.organization_id != organization_id:
        raise HTTPException(404, "Listing was not found")
    if member.role == "agent" and record.assigned_staff_id != member.subject:
        raise HTTPException(403, "Listing is not assigned to you")
    return record


def audit(session, actor, org, action, resource):
    session.add(
        MarketplaceAuditRecord(
            id=str(uuid4()), actor=actor, organization_id=org, action=action, resource_id=resource
        )
    )


class AgencyCreate(StaffListingCreate):
    classification: Literal["residential", "commercial"]
    rental_period: Literal["monthly", "yearly"] | None = None
    assigned_subject: str = Field(min_length=1, max_length=128)


class Proposal(StaffListingPatch):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    classification: Literal["residential", "commercial"] | None = None
    rental_period: Literal["monthly", "yearly"] | None = None


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edit_version: int = Field(ge=1)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "needs_changes", "rejected"]
    note: str = Field(default="", max_length=1000)


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=128)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=32)
    description: str = Field(default="", max_length=3000)
    coverage: list[Literal["Islamabad", "Rawalpindi", "Lahore", "Karachi"]] = Field(max_length=4)


class Invitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=128)
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=128)
    role: Literal["administrator", "manager", "agent"]


@platform.post("/organizations", status_code=201)
def create_org(
    payload: OrganizationCreate,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
):
    with SessionLocal.begin() as session:
        if session.scalar(
            select(OrganizationRecord).where(OrganizationRecord.slug == payload.slug)
        ):
            raise HTTPException(409, "Agency slug is already used")
        org = OrganizationRecord(
            id=str(uuid4()), **payload.model_dump(mode="json"), status="pending"
        )
        session.add(org)
        audit(session, staff.subject, org.id, "agency.invited", org.id)
        return {"id": org.id, "status": "pending"}


@platform.get("/organizations")
def orgs(staff: StaffPrincipal = Depends(require_roles("administrator", "manager"))):
    with SessionLocal() as session:
        return {
            "data": [
                {"id": o.id, "name": o.name, "status": o.status, "edit_version": o.edit_version}
                for o in session.scalars(
                    select(OrganizationRecord).order_by(OrganizationRecord.name)
                ).all()
            ]
        }


class OrgStatus(Version):
    status: Literal["approved", "suspended", "pending"]


@platform.patch("/organizations/{org_id}")
def org_status(
    org_id: str,
    payload: OrgStatus,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
):
    with SessionLocal.begin() as session:
        result = session.execute(
            update(OrganizationRecord)
            .where(
                OrganizationRecord.id == org_id,
                OrganizationRecord.edit_version == payload.edit_version,
            )
            .values(
                status=payload.status,
                approved_at=datetime.now(UTC) if payload.status == "approved" else None,
                edit_version=payload.edit_version + 1,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Agency changed; refresh before retrying")
        audit(session, staff.subject, org_id, "agency." + payload.status, org_id)
    return {"status": payload.status, "edit_version": payload.edit_version + 1}


@platform.post("/organizations/{org_id}/members", status_code=201)
def invite(
    org_id: str,
    payload: Invitation,
    staff: StaffPrincipal = Depends(require_roles("administrator")),
):
    with SessionLocal.begin() as session:
        if not session.get(OrganizationRecord, org_id):
            raise HTTPException(404, "Agency was not found")
        if session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.organization_id == org_id,
                MembershipRecord.subject == payload.subject,
            )
        ):
            raise HTTPException(409, "Identity is already a member")
        session.add(
            MembershipRecord(
                id=str(uuid4()),
                organization_id=org_id,
                **payload.model_dump(mode="json"),
                active=True,
                profile_approved=False,
            )
        )
        audit(session, staff.subject, org_id, "member.invited", payload.subject)
    return {"status": "invited"}


@agency.get("/listings")
def agency_list(organization_id: str, identity: Identity = Depends(require_identity)):
    with SessionLocal() as session:
        member = authorize(session, organization_id, identity)
        stmt = select(PropertyRecord).where(PropertyRecord.organization_id == organization_id)
        if member.role == "agent":
            stmt = stmt.where(PropertyRecord.assigned_staff_id == identity.subject)
        return {
            "data": [
                _staff_listing(session, p)
                for p in session.scalars(stmt.order_by(PropertyRecord.id)).all()
            ]
        }


@agency.post("/listings", status_code=201)
def create_listing(
    organization_id: str, payload: AgencyCreate, identity: Identity = Depends(require_identity)
):
    with SessionLocal.begin() as session:
        authorize(session, organization_id, identity, True)
        agent = session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.subject == payload.assigned_subject,
                MembershipRecord.active.is_(True),
            )
        )
        if not agent:
            raise HTTPException(422, "Assigned agent must be an active agency member")
        if payload.transaction_type == "rent" and not payload.rental_period:
            raise HTTPException(422, "Rental period is required")
        pid = str(uuid4())
        data = payload.model_dump(exclude={"assigned_subject"})
        record = PropertyRecord(
            id=pid,
            organization_id=organization_id,
            slug=_slugify(payload.title, payload.city, pid),
            **data,
            purpose=payload.transaction_type,
            available=False,
            assigned_staff_id=agent.subject,
            assigned_employee="agent:" + agent.subject,
            source="agency-submission",
            source_version="1",
            publication_status="draft",
            availability_status="unconfirmed",
            investment_goals=[],
            nearby_schools=[],
            nearby_hospitals=[],
        )
        session.add(record)
        audit(session, identity.subject, organization_id, "listing.created", pid)
        return {"id": pid, "edit_version": 1, "publication_status": "draft"}


@agency.post("/listings/{property_id}/submit", status_code=201)
def submit(
    organization_id: str,
    property_id: str,
    payload: Proposal,
    identity: Identity = Depends(require_identity),
):
    with SessionLocal.begin() as session:
        member = authorize(session, organization_id, identity)
        record = owned(session, organization_id, property_id, member)
        if record.edit_version != payload.edit_version:
            raise HTTPException(409, "Listing changed; refresh")
        if session.scalar(
            select(ListingRevisionRecord).where(
                ListingRevisionRecord.property_id == property_id,
                ListingRevisionRecord.status == "submitted",
            )
        ):
            raise HTTPException(409, "A revision is already under review")
        rid = str(uuid4())
        session.add(
            ListingRevisionRecord(
                id=rid,
                property_id=property_id,
                organization_id=organization_id,
                base_version=record.edit_version,
                proposed=payload.model_dump(exclude={"edit_version"}, exclude_unset=True),
                submitted_by=identity.subject,
                status="submitted",
            )
        )
        audit(session, identity.subject, organization_id, "revision.submitted", rid)
        return {"id": rid, "status": "submitted"}


@platform.get("/revisions")
def revisions(staff: StaffPrincipal = Depends(require_roles("administrator", "manager"))):
    with SessionLocal() as session:
        return {
            "data": [
                {
                    "id": r.id,
                    "property_id": r.property_id,
                    "organization_id": r.organization_id,
                    "proposed": r.proposed,
                    "base_version": r.base_version,
                    "status": r.status,
                }
                for r in session.scalars(
                    select(ListingRevisionRecord).where(ListingRevisionRecord.status == "submitted")
                ).all()
            ]
        }


@platform.post("/revisions/{revision_id}/review")
def review(
    revision_id: str,
    payload: Review,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
):
    with SessionLocal.begin() as session:
        rev = session.scalar(
            select(ListingRevisionRecord)
            .where(ListingRevisionRecord.id == revision_id)
            .with_for_update()
        )
        if not rev:
            raise HTTPException(404, "Revision was not found")
        if rev.status != "submitted":
            raise HTTPException(409, "Revision already reviewed")
        record = session.scalar(
            select(PropertyRecord).where(PropertyRecord.id == rev.property_id).with_for_update()
        )
        if record.edit_version != rev.base_version:
            raise HTTPException(409, "Listing changed since submission")
        if payload.decision == "approved":
            org = session.get(OrganizationRecord, rev.organization_id)
            agent = session.scalar(
                select(MembershipRecord).where(
                    MembershipRecord.organization_id == rev.organization_id,
                    MembershipRecord.subject == record.assigned_staff_id,
                    MembershipRecord.active.is_(True),
                )
            )
            proposed = Proposal(edit_version=rev.base_version, **rev.proposed).model_dump(
                exclude={"edit_version"}, exclude_unset=True
            )
            values = {
                k: proposed.get(k, getattr(record, k))
                for k in (
                    "title",
                    "description",
                    "city",
                    "area",
                    "price_pkr",
                    "size_sqft",
                    "classification",
                    "rental_period",
                    "transaction_type",
                )
            }
            photo = session.scalar(
                select(PropertyMediaRecord.id).where(
                    PropertyMediaRecord.property_id == record.id,
                    PropertyMediaRecord.processing_status == "ready",
                    PropertyMediaRecord.is_public.is_(True),
                    PropertyMediaRecord.derivative_object_path.is_not(None),
                    PropertyMediaRecord.public_url.is_not(None),
                )
            )
            confirmation = record.availability_confirmed_at
            fresh = (
                confirmation and (datetime.now(UTC) - confirmation.replace(tzinfo=UTC)).days < 30
            )
            location = session.scalar(
                select(LocationRecord.id).where(
                    LocationRecord.city == values["city"],
                    LocationRecord.area == values["area"],
                    LocationRecord.reviewed.is_(True),
                )
            )
            if (
                not org
                or org.status != "approved"
                or not agent
                or not photo
                or not fresh
                or not record.content_permission_confirmed_at
                or not location
                or not values["description"]
                or not values["classification"]
                or (values["transaction_type"] == "rent" and not values["rental_period"])
            ):
                raise HTTPException(
                    422,
                    "Publication requires approved publisher/location, agent, permitted processed photo, complete facts and current availability",
                )
            if "latitude" in proposed or "longitude" in proposed:
                if proposed.get("latitude") is None or proposed.get("longitude") is None:
                    raise HTTPException(422, "Review both coordinates together")
                record.coordinates_approved_at = datetime.now(UTC)
            # Compare and set public fields atomically; row locks alone do not protect SQLite.
            changed = session.execute(
                update(PropertyRecord)
                .where(
                    PropertyRecord.id == record.id, PropertyRecord.edit_version == rev.base_version
                )
                .values(**proposed, edit_version=rev.base_version + 1)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Listing changed during review")
            for key, value in proposed.items():
                setattr(record, key, value)
            record.publication_status = "published"
            record.edit_version = rev.base_version + 1
            if not record.published_at:
                record.published_at = datetime.now(UTC)
        rev.status = payload.decision
        rev.reviewed_by = staff.subject
        rev.review_note = payload.note
        audit(session, staff.subject, rev.organization_id, "revision." + payload.decision, rev.id)
    return {"status": payload.decision}


class Availability(Version):
    status: Literal["available", "unavailable", "reserved", "sold"]
    content_permission: bool = False


@agency.patch("/listings/{property_id}/availability")
def availability(
    organization_id: str,
    property_id: str,
    payload: Availability,
    identity: Identity = Depends(require_identity),
):
    with SessionLocal.begin() as session:
        member = authorize(session, organization_id, identity)
        record = owned(session, organization_id, property_id, member)
        if record.edit_version != payload.edit_version:
            raise HTTPException(409, "Listing changed")
        changed = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(
                available=payload.status == "available",
                availability_status=payload.status,
                availability_confirmed_at=datetime.now(UTC),
                content_permission_confirmed_at=datetime.now(UTC)
                if payload.content_permission
                else record.content_permission_confirmed_at,
                edit_version=payload.edit_version + 1,
            )
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Listing changed")
        audit(
            session,
            identity.subject,
            organization_id,
            "availability." + payload.status,
            property_id,
        )
    return {"edit_version": payload.edit_version + 1}


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=128)
    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1410, multiple_of=30)
    end_minute: int = Field(ge=30, le=1440, multiple_of=30)
    exception_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    unavailable: bool = False


@agency.post("/schedules", status_code=201)
def schedule(
    organization_id: str, payload: Schedule, identity: Identity = Depends(require_identity)
):
    if payload.end_minute <= payload.start_minute:
        raise HTTPException(422, "Schedule end must follow start")
    if payload.exception_date:
        try:
            datetime.strptime(payload.exception_date, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError as e:
            raise HTTPException(422, "Invalid exception date") from e
    with SessionLocal.begin() as session:
        authorize(session, organization_id, identity, True)
        if not session.scalar(
            select(MembershipRecord.id).where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.subject == payload.subject,
                MembershipRecord.active.is_(True),
            )
        ):
            raise HTTPException(422, "Agent is not a member")
        sid = str(uuid4())
        session.add(
            AgentScheduleRecord(
                id=sid, organization_id=organization_id, **payload.model_dump(), approved=True
            )
        )
        audit(session, identity.subject, organization_id, "schedule.created", sid)
    return {"id": sid}


@agency.get("/inquiries")
def inquiries(organization_id: str, identity: Identity = Depends(require_identity)):
    from app.catalog.inquiries import _staff_inquiry

    with SessionLocal() as session:
        member = authorize(session, organization_id, identity)
        stmt = select(WebsiteInquiryRecord).where(
            WebsiteInquiryRecord.organization_id == organization_id,
            WebsiteInquiryRecord.expires_at > datetime.now(UTC),
        )
        if member.role == "agent":
            stmt = stmt.where(WebsiteInquiryRecord.assigned_staff_id == member.subject)
        return {"data": [_staff_inquiry(session, r) for r in session.scalars(stmt).all()]}


class CanonicalLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: Literal["Islamabad", "Rawalpindi", "Lahore", "Karachi"]
    area: str = Field(default="", max_length=128)
    area_slug: str = Field(default="", pattern=r"^[a-z0-9-]*$", max_length=128)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    sqft_per_marla: int | None = Field(default=None, ge=100, le=400)


@platform.post("/locations", status_code=201)
def location(
    payload: CanonicalLocation,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
):
    with SessionLocal.begin() as session:
        if session.scalar(
            select(LocationRecord.id).where(
                LocationRecord.city == payload.city, LocationRecord.area == payload.area
            )
        ):
            raise HTTPException(409, "Location already exists")
        lid = str(uuid4())
        session.add(
            LocationRecord(
                id=lid, city_slug=payload.city.lower(), **payload.model_dump(), reviewed=True
            )
        )
        audit(session, staff.subject, None, "location.reviewed", lid)
    return {"id": lid}


class ProfileReview(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    languages: list[str] = Field(max_length=10)
    approved: bool


@platform.post("/members/{member_id}/profile")
def profile_review(
    member_id: str,
    payload: ProfileReview,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
):
    with SessionLocal.begin() as session:
        row = session.get(MembershipRecord, member_id)
        if not row:
            raise HTTPException(404, "Membership was not found")
        row.slug = payload.slug
        row.languages = payload.languages
        row.profile_approved = payload.approved
        audit(session, staff.subject, row.organization_id, "profile.reviewed", member_id)
    return {"status": "reviewed"}


@agency.get("/members")
def members(organization_id: str, identity: Identity = Depends(require_identity)):
    with SessionLocal() as session:
        authorize(session, organization_id, identity, True)
        return {
            "data": [
                {
                    "id": m.id,
                    "subject": m.subject,
                    "name": m.display_name,
                    "role": m.role,
                    "active": m.active,
                }
                for m in session.scalars(
                    select(MembershipRecord).where(
                        MembershipRecord.organization_id == organization_id
                    )
                ).all()
            ]
        }


class MembershipStatus(BaseModel):
    active: bool
    role: Literal["administrator", "manager", "agent"]


class AgencyViewingCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: __import__("uuid").UUID
    reason: str = Field(default="", max_length=500)


class AgencyViewingReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: __import__("uuid").UUID
    new_starts_at: datetime


@agency.patch("/members/{member_id}")
def member_status(
    organization_id: str,
    member_id: str,
    payload: MembershipStatus,
    identity: Identity = Depends(require_identity),
):
    with SessionLocal.begin() as session:
        actor = authorize(session, organization_id, identity, True)
        if actor.role != "administrator":
            raise HTTPException(403, "Agency administrator is required")
        row = session.get(MembershipRecord, member_id)
        if not row or row.organization_id != organization_id:
            raise HTTPException(404, "Membership was not found")
        if row.subject == identity.subject:
            raise HTTPException(409, "Ask another administrator to change your own membership")
        row.active = payload.active
        row.role = payload.role
        audit(session, identity.subject, organization_id, "member.updated", member_id)
    return {"status": "updated"}


@agency.get("/schedules")
def schedules(organization_id: str, identity: Identity = Depends(require_identity)):
    with SessionLocal() as session:
        member = authorize(session, organization_id, identity)
        stmt = select(AgentScheduleRecord).where(
            AgentScheduleRecord.organization_id == organization_id
        )
        if member.role == "agent":
            stmt = stmt.where(AgentScheduleRecord.subject == member.subject)
        return {
            "data": [
                {
                    "id": r.id,
                    "subject": r.subject,
                    "weekday": r.weekday,
                    "start_minute": r.start_minute,
                    "end_minute": r.end_minute,
                    "exception_date": r.exception_date,
                    "unavailable": r.unavailable,
                }
                for r in session.scalars(stmt).all()
            ]
        }


@agency.delete("/schedules/{schedule_id}")
def remove_schedule(
    organization_id: str, schedule_id: str, identity: Identity = Depends(require_identity)
):
    with SessionLocal.begin() as session:
        authorize(session, organization_id, identity, True)
        row = session.get(AgentScheduleRecord, schedule_id)
        if not row or row.organization_id != organization_id:
            raise HTTPException(404, "Schedule was not found")
        session.delete(row)
        audit(session, identity.subject, organization_id, "schedule.removed", schedule_id)
    return {"status": "removed"}


from app.catalog.inquiries import StaffInquiryUpdate, _staff_inquiry


@agency.patch("/inquiries/{inquiry_id}")
def update_inquiry(
    organization_id: str,
    inquiry_id: str,
    payload: StaffInquiryUpdate,
    identity: Identity = Depends(require_identity),
):
    from app.repositories.records import WebsiteInquiryActivityRecord
    from app.services.appointments import redact_for_retention

    with SessionLocal.begin() as session:
        member = authorize(session, organization_id, identity)
        row = session.get(WebsiteInquiryRecord, inquiry_id, with_for_update=True)
        if not row or row.organization_id != organization_id:
            raise HTTPException(404, "Inquiry was not found")
        if member.role == "agent" and row.assigned_staff_id != identity.subject:
            raise HTTPException(403, "Inquiry is not assigned to you")
        changes = payload.model_dump(exclude={"edit_version", "note"}, exclude_unset=True)
        if "assigned_staff_id" in changes:
            if member.role == "agent":
                raise HTTPException(403, "Agency manager must assign inquiries")
            target = session.scalar(
                select(MembershipRecord).where(
                    MembershipRecord.organization_id == organization_id,
                    MembershipRecord.subject == changes["assigned_staff_id"],
                    MembershipRecord.active.is_(True),
                )
            )
            if not target:
                raise HTTPException(422, "Assignee must be an active agency member")
        if changes.get("workflow_status") == "closed" and not (
            changes.get("closing_outcome") or row.closing_outcome
        ):
            raise HTTPException(422, "Closing outcome is required")
        result = session.execute(
            update(WebsiteInquiryRecord)
            .where(
                WebsiteInquiryRecord.id == inquiry_id,
                WebsiteInquiryRecord.edit_version == payload.edit_version,
            )
            .values(**changes, edit_version=payload.edit_version + 1)
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Inquiry changed; refresh")
        session.add(
            WebsiteInquiryActivityRecord(
                id=str(uuid4()),
                inquiry_id=inquiry_id,
                actor_staff_id=identity.subject,
                action="agency.updated",
                details_redacted=redact_for_retention(payload.note or ""),
            )
        )
        audit(session, identity.subject, organization_id, "inquiry.updated", inquiry_id)
        session.flush()
        session.refresh(row)
        return _staff_inquiry(session, row)


@agency.get("/viewings")
def agency_viewings(organization_id: str, identity: Identity = Depends(require_identity)):
    with SessionLocal() as session:
        member = authorize(session, organization_id, identity)
        stmt = select(AppointmentRecord).where(AppointmentRecord.organization_id == organization_id)
        if member.role == "agent":
            stmt = stmt.where(AppointmentRecord.agent_subject == identity.subject)
        records = session.scalars(
            stmt.order_by(AppointmentRecord.starts_at.desc()).limit(200)
        ).all()
        references = {r.reference for r in records}
        delivery: dict[str, str] = {}
        if references:
            events = session.scalars(
                select(OutboxEventRecord)
                .where(
                    OutboxEventRecord.event_type.in_(
                        ("appointment.booked", "appointment.cancelled", "appointment.rescheduled")
                    )
                )
                .order_by(OutboxEventRecord.created_at.desc())
                .limit(1000)
            ).all()
            for event in events:
                reference = (event.payload or {}).get("reference")
                if (
                    not isinstance(reference, str)
                    or reference not in references
                    or reference in delivery
                ):
                    continue
                delivery[reference] = (
                    "delivered"
                    if event.delivered_at
                    else "failed"
                    if event.attempts >= settings.outbox_max_attempts
                    else "pending"
                )
        return {
            "data": [
                {
                    "reference": r.reference,
                    "property_id": r.property_id,
                    "starts_at": r.starts_at,
                    "status": r.status,
                    "agent_subject": r.agent_subject,
                    "delivery_status": delivery.get(r.reference, "not_configured"),
                }
                for r in records
            ]
        }


def _agency_viewing_update(
    organization_id: str,
    reference: str,
    identity: Identity,
    idempotency_key,
    *,
    starts_at: datetime | None = None,
    cancel: bool = False,
):
    with SessionLocal() as session:
        member = authorize(session, organization_id, identity)
        record = session.scalar(
            select(AppointmentRecord).where(AppointmentRecord.reference == reference)
        )
        if not record or record.organization_id != organization_id:
            raise HTTPException(404, "Viewing was not found")
        if member.role == "agent" and record.agent_subject != identity.subject:
            raise HTTPException(403, "Viewing is not assigned to you")
        if record.status in {"cancelled", "completed"}:
            raise HTTPException(409, "Closed viewings cannot be changed")
        try:
            contact_email = ContactCipher().decrypt(record.contact_email_ciphertext)
        except Exception as error:
            raise HTTPException(503, "Viewing contact cannot be securely read") from error

    service = SqlAppointmentService(SqlPropertyRepository())
    try:
        updated = service.update(
            AppointmentUpdate(
                reference=reference,
                contact_email=contact_email,
                starts_at=starts_at,
                idempotency_key=idempotency_key,
            ),
            cancel=cancel,
            # Authorization came from the organization's active MFA-protected membership.
            verified_contact=True,
        )
    except ValueError as error:
        message = str(error)
        status = 409 if "already booked" in message else 422
        raise HTTPException(status, message) from error
    return {
        "reference": updated.reference,
        "starts_at": updated.starts_at,
        "status": updated.status,
        "delivery_status": "pending",
    }


@agency.post("/viewings/{reference}/cancel")
def cancel_agency_viewing(
    organization_id: str,
    reference: str,
    payload: AgencyViewingCancel,
    identity: Identity = Depends(require_identity),
):
    return _agency_viewing_update(
        organization_id,
        reference,
        identity,
        payload.idempotency_key,
        cancel=True,
    )


@agency.post("/viewings/{reference}/reschedule")
def reschedule_agency_viewing(
    organization_id: str,
    reference: str,
    payload: AgencyViewingReschedule,
    identity: Identity = Depends(require_identity),
):
    return _agency_viewing_update(
        organization_id,
        reference,
        identity,
        payload.idempotency_key,
        starts_at=payload.new_starts_at,
    )


@agency.post("/viewings/{reference}/complete")
def complete_agency_viewing(
    organization_id: str,
    reference: str,
    identity: Identity = Depends(require_identity),
):
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        member = authorize(session, organization_id, identity)
        record = session.scalar(
            select(AppointmentRecord)
            .where(AppointmentRecord.reference == reference)
            .with_for_update()
        )
        if not record or record.organization_id != organization_id:
            raise HTTPException(404, "Viewing was not found")
        if member.role == "agent" and record.agent_subject != identity.subject:
            raise HTTPException(403, "Viewing is not assigned to you")
        if record.status == "completed":
            return {"reference": reference, "status": "completed"}
        if record.status == "cancelled":
            raise HTTPException(409, "Cancelled viewings cannot be marked completed")
        starts_at = record.starts_at
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        if starts_at > now:
            raise HTTPException(409, "A future viewing cannot be marked completed")
        result = session.execute(
            update(AppointmentRecord)
            .where(
                AppointmentRecord.reference == reference,
                AppointmentRecord.status.in_(("booked", "rescheduled")),
                AppointmentRecord.closed_at.is_(None),
            )
            .values(status="completed", closed_at=now)
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Viewing changed; refresh")
        audit(session, identity.subject, organization_id, "viewing.completed", reference)
    return {"reference": reference, "status": "completed"}


from fastapi import Request


@agency.post("/listings/{property_id}/media", status_code=201)
async def upload_media(
    organization_id: str,
    property_id: str,
    request: Request,
    identity: Identity = Depends(require_identity),
):
    import asyncio
    import io

    import httpx
    from PIL import Image

    with SessionLocal() as session:
        member = authorize(session, organization_id, identity)
        owned(session, organization_id, property_id, member)
    if not settings.supabase_service_role_key or not settings.supabase_url:
        raise HTTPException(503, "Private media storage is not configured")
    limit = 8 * 1024 * 1024
    if int(request.headers.get("content-length", "0")) > limit:
        raise HTTPException(413, "Photo limit is 8 MB")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, "Photo limit is 8 MB")
        data.extend(chunk)

    def check():
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 20_000_000 or image.format not in {
                    "JPEG",
                    "PNG",
                    "WEBP",
                }:
                    raise ValueError()
                image.verify()
        except Exception as error:
            raise HTTPException(
                422, "Upload a valid JPEG, PNG or WebP up to 20 megapixels"
            ) from error

    await asyncio.to_thread(check)
    media_id = str(uuid4())
    path = f"{organization_id}/{property_id}/{media_id}"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{settings.supabase_url.rstrip('/')}/storage/v1/object/property-originals/{path}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
                "content-type": "application/octet-stream",
            },
            content=bytes(data),
        )
        if r.status_code not in {200, 201}:
            raise HTTPException(502, "Private photo upload failed")
    with SessionLocal.begin() as session:
        session.add(
            PropertyMediaRecord(
                id=media_id,
                property_id=property_id,
                original_object_path="supabase:" + path,
                alt_text=request.headers.get("x-photo-alt", "")[:250],
                sort_order=0,
                processing_status="pending",
                is_public=False,
            )
        )
        audit(session, identity.subject, organization_id, "media.uploaded", media_id)
    return {"id": media_id, "processing_status": "pending", "public": False}


class MediaReview(BaseModel):
    permitted: bool
    alt_text: str = Field(min_length=1, max_length=250)
    sort_order: int = Field(ge=0, le=100)


@platform.post("/media/{media_id}/review")
def media_review(
    media_id: str,
    payload: MediaReview,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
):
    with SessionLocal.begin() as session:
        row = session.get(PropertyMediaRecord, media_id)
        if not row:
            raise HTTPException(404, "Media was not found")
        if row.processing_status != "ready":
            raise HTTPException(409, "Photo processing must finish first")
        if (
            payload.permitted
            and row.derivative_object_path
            and row.derivative_object_path.startswith("supabase:")
        ):
            import httpx

            path = row.derivative_object_path.removeprefix("supabase:")
            headers = {
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
            }
            with httpx.Client(timeout=20) as client:
                original = client.get(
                    f"{settings.supabase_url.rstrip('/')}/storage/v1/object/property-processed/{path}",
                    headers=headers,
                )
                if original.status_code != 200:
                    raise HTTPException(502, "Processed photo could not be read")
                result = client.post(
                    f"{settings.supabase_url.rstrip('/')}/storage/v1/object/property-public/{path}",
                    headers={**headers, "content-type": "image/webp", "x-upsert": "true"},
                    content=original.content,
                )
                if result.status_code not in {200, 201}:
                    raise HTTPException(502, "Photo publication failed")
            row.public_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/property-public/{path}"
        row.is_public = payload.permitted
        row.alt_text = payload.alt_text
        row.sort_order = payload.sort_order
        record = session.get(PropertyRecord, row.property_id)
        audit(session, staff.subject, record.organization_id, "media.reviewed", media_id)
    return {"status": "reviewed"}


@agency.post("/listings/{property_id}/archive")
def archive(
    organization_id: str,
    property_id: str,
    payload: Version,
    identity: Identity = Depends(require_identity),
):
    with SessionLocal.begin() as session:
        member = authorize(session, organization_id, identity, True)
        owned(session, organization_id, property_id, member)
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(
                publication_status="archived",
                available=False,
                edit_version=payload.edit_version + 1,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Listing changed")
        audit(session, identity.subject, organization_id, "listing.archived", property_id)
    return {"status": "archived"}


@platform.get("/audit")
def audit_events(staff: StaffPrincipal = Depends(require_roles("administrator", "manager"))):
    with SessionLocal() as session:
        return {
            "data": [
                {
                    "actor": r.actor,
                    "organization_id": r.organization_id,
                    "action": r.action,
                    "resource_id": r.resource_id,
                    "created_at": r.created_at,
                }
                for r in session.scalars(
                    select(MarketplaceAuditRecord)
                    .order_by(MarketplaceAuditRecord.created_at.desc())
                    .limit(200)
                ).all()
            ]
        }


class Assignment(Version):
    subject: str = Field(min_length=1, max_length=128)


@agency.patch("/listings/{property_id}/assignment")
def assignment(
    organization_id: str,
    property_id: str,
    payload: Assignment,
    identity: Identity = Depends(require_identity),
):
    with SessionLocal.begin() as session:
        actor = authorize(session, organization_id, identity, True)
        owned(session, organization_id, property_id, actor)
        member = session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.subject == payload.subject,
                MembershipRecord.active.is_(True),
            )
        )
        if not member:
            raise HTTPException(422, "Assignee must be an active member")
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(
                assigned_staff_id=payload.subject,
                assigned_employee="agent:" + payload.subject,
                edit_version=payload.edit_version + 1,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Listing changed")
        audit(session, identity.subject, organization_id, "listing.assigned", property_id)
    return {"edit_version": payload.edit_version + 1, "accepted_viewings": "retain_recorded_agent"}


@platform.get("/media")
def media_queue(staff: StaffPrincipal = Depends(require_roles("administrator", "manager"))):
    with SessionLocal() as session:
        return {
            "data": [
                {
                    "id": r.id,
                    "property_id": r.property_id,
                    "status": r.processing_status,
                    "permitted": r.is_public,
                    "alt_text": r.alt_text,
                    "sort_order": r.sort_order,
                }
                for r in session.scalars(
                    select(PropertyMediaRecord)
                    .where(PropertyMediaRecord.is_public.is_(False))
                    .order_by(PropertyMediaRecord.created_at)
                    .limit(100)
                ).all()
            ]
        }


@platform.get("/media/{media_id}/preview")
def media_preview(
    media_id: str, staff: StaffPrincipal = Depends(require_roles("administrator", "manager"))
):
    import httpx

    with SessionLocal() as session:
        row = session.get(PropertyMediaRecord, media_id)
        if (
            not row
            or not row.derivative_object_path
            or not row.derivative_object_path.startswith("supabase:")
        ):
            raise HTTPException(404, "Processed private photo was not found")
        path = row.derivative_object_path.removeprefix("supabase:")
    if not settings.supabase_service_role_key:
        raise HTTPException(503, "Private storage is not configured")
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/property-processed/{path}",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        },
        json={"expiresIn": 60},
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(502, "Private preview is unavailable")
    value = response.json().get("signedURL")
    if not isinstance(value, str) or not value.startswith("/object/sign/"):
        raise HTTPException(502, "Storage returned an invalid preview")
    return {"url": f"{settings.supabase_url.rstrip('/')}/storage/v1{value}", "expires_in": 60}


@platform.get("/reports")
def reports(staff: StaffPrincipal = Depends(require_roles("administrator", "manager"))):
    from app.repositories.records import ListingReportRecord

    with SessionLocal() as session:
        return {
            "data": [
                {
                    "id": r.id,
                    "property_id": r.property_id,
                    "category": r.category,
                    "status": r.status,
                }
                for r in session.scalars(
                    select(ListingReportRecord)
                    .where(ListingReportRecord.status == "new")
                    .limit(100)
                ).all()
            ]
        }


class ReportReview(BaseModel):
    status: Literal["resolved", "dismissed"]
    suspend_listing: bool = False


@platform.patch("/reports/{report_id}")
def resolve_report(
    report_id: str,
    payload: ReportReview,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
):
    from app.repositories.records import ListingReportRecord

    with SessionLocal.begin() as session:
        row = session.get(ListingReportRecord, report_id)
        if not row:
            raise HTTPException(404, "Report was not found")
        row.status = payload.status
        prop = session.get(PropertyRecord, row.property_id)
        if payload.suspend_listing:
            prop.publication_status = "suspended"
            prop.available = False
            prop.edit_version += 1
        audit(session, staff.subject, prop.organization_id, "report." + payload.status, report_id)
    return {"status": payload.status}
