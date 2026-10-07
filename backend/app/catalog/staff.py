from __future__ import annotations

# FastAPI declares validated request and role dependencies in endpoint signatures.
# ruff: noqa: B008
import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select, update

from app.catalog.staff_auth import StaffPrincipal, require_roles, require_staff
from app.core.config import settings
from app.core.pii import ContactCipher
from app.domain.models import AppointmentUpdate
from app.repositories.appointments import SqlAppointmentService
from app.repositories.database import SessionLocal
from app.repositories.listing_visibility import AVAILABILITY_CONFIRMATION_MAX_AGE
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    AppointmentRecord,
    AreaGuideRecord,
    PropertyMediaRecord,
    PropertyRecord,
    StaffUserRecord,
    ToolAuditEventRecord,
)

StaffTransactionType = Literal["sale", "rent"]
StaffPropertyType = Literal["house", "apartment", "plot", "shop", "office", "warehouse", "other"]
StaffAvailability = Literal["available", "unavailable", "reserved", "sold"]


class StaffMedia(BaseModel):
    id: str
    alt_text: str
    sort_order: int
    processing_status: str
    is_public: bool


class StaffListing(BaseModel):
    id: str
    slug: str | None
    title: str
    description: str
    transaction_type: str | None
    property_type: str | None
    city: str
    area: str
    price_pkr: int
    bedrooms: int
    bathrooms: int | None
    size_sqft: int
    amenities: list[str]
    publication_status: str
    availability_status: str
    availability_confirmed_at: datetime | None
    content_permission_confirmed_at: datetime | None
    assigned_staff_id: str | None
    assigned_employee: str
    edit_version: int
    source: str
    imported_at: datetime | None
    photos: list[StaffMedia]


class StaffListingPage(BaseModel):
    data: list[StaffListing]
    pagination: dict[str, int]


class StaffListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=5000)
    transaction_type: StaffTransactionType
    property_type: StaffPropertyType
    city: str = Field(min_length=2, max_length=64)
    area: str = Field(min_length=1, max_length=128)
    price_pkr: int = Field(gt=0, le=9_000_000_000_000_000_000)
    bedrooms: int = Field(ge=0, le=10)
    bathrooms: int | None = Field(default=None, ge=0, le=20)
    size_sqft: int = Field(gt=0)
    amenities: list[str] = Field(default_factory=list, max_length=40)
    developer: str = Field(min_length=1, max_length=128)
    payment_plan: str = Field(max_length=3000)


class StaffListingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    transaction_type: StaffTransactionType | None = None
    property_type: StaffPropertyType | None = None
    city: str | None = Field(default=None, min_length=2, max_length=64)
    area: str | None = Field(default=None, min_length=1, max_length=128)
    price_pkr: int | None = Field(default=None, gt=0, le=9_000_000_000_000_000_000)
    bedrooms: int | None = Field(default=None, ge=0, le=10)
    bathrooms: int | None = Field(default=None, ge=0, le=20)
    size_sqft: int | None = Field(default=None, gt=0)
    amenities: list[str] | None = Field(default=None, max_length=40)
    developer: str | None = Field(default=None, min_length=1, max_length=128)
    payment_plan: str | None = Field(default=None, max_length=3000)


class StaffAssignListing(BaseModel):
    staff_id: str = Field(min_length=1, max_length=128)
    edit_version: int = Field(ge=1)


class StaffAvailabilityUpdate(BaseModel):
    status: StaffAvailability
    edit_version: int = Field(ge=1)


class StaffSlugResponse(BaseModel):
    data: StaffListing


def _slugify(title: str, city: str, property_id: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", f"{title}-{city}".casefold()).strip("-")
    if not stem:
        stem = "property"
    return f"{stem[:140].rstrip('-')}-{property_id[-8:].lower()}"


def _staff_listing(session, record: PropertyRecord) -> StaffListing:
    media = session.scalars(
        select(PropertyMediaRecord)
        .where(PropertyMediaRecord.property_id == record.id)
        .order_by(PropertyMediaRecord.sort_order.asc(), PropertyMediaRecord.id.asc())
    ).all()
    return StaffListing(
        id=record.id,
        slug=record.slug,
        title=record.title,
        description=record.description,
        transaction_type=record.transaction_type,
        property_type=record.property_type,
        city=record.city,
        area=record.area,
        price_pkr=record.price_pkr,
        bedrooms=record.bedrooms,
        bathrooms=record.bathrooms,
        size_sqft=record.size_sqft,
        amenities=record.amenities or [],
        publication_status=record.publication_status,
        availability_status=record.availability_status,
        availability_confirmed_at=record.availability_confirmed_at,
        content_permission_confirmed_at=record.content_permission_confirmed_at,
        assigned_staff_id=record.assigned_staff_id,
        assigned_employee=record.assigned_employee,
        edit_version=record.edit_version,
        source=record.source,
        imported_at=record.imported_at,
        photos=[
            StaffMedia(
                id=item.id,
                alt_text=item.alt_text,
                sort_order=item.sort_order,
                processing_status=item.processing_status,
                is_public=item.is_public,
            )
            for item in media
        ],
    )


def _require_listing_access(record: PropertyRecord, staff: StaffPrincipal) -> None:
    if staff.role == "agent" and record.assigned_staff_id != staff.subject:
        raise HTTPException(status_code=403, detail="Listing is not assigned to this agent")


def _audit(session, actor: str, action: str, property_id: str, status: str) -> None:
    session.add(
        ToolAuditEventRecord(
            id=str(uuid4()),
            action=f"website.listing.{action}",
            status=status,
            reference=property_id,
            payload={"actor_staff_id": actor},
        )
    )


router = APIRouter(prefix="/v1/staff/listings", tags=["staff listings"])


@router.get("", response_model=StaffListingPage)
def list_staff_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: Literal["draft", "published", "archived"] | None = None,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffListingPage:
    statement = select(PropertyRecord)
    if status:
        statement = statement.where(PropertyRecord.publication_status == status)
    if staff.role == "agent":
        statement = statement.where(PropertyRecord.assigned_staff_id == staff.subject)
    with SessionLocal() as session:
        total = (
            session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
            or 0
        )
        records = session.scalars(
            statement.order_by(PropertyRecord.imported_at.desc(), PropertyRecord.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        listings = [_staff_listing(session, record) for record in records]
    return StaffListingPage(
        data=listings,
        pagination={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@router.post("", response_model=StaffSlugResponse, status_code=201)
def create_staff_listing(
    payload: StaffListingCreate,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
) -> StaffSlugResponse:
    property_id = str(uuid4())
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        record = PropertyRecord(
            id=property_id,
            title=payload.title,
            city=payload.city,
            area=payload.area,
            purpose=payload.transaction_type,
            transaction_type=payload.transaction_type,
            property_type=payload.property_type,
            description=payload.description,
            price_pkr=payload.price_pkr,
            bedrooms=payload.bedrooms,
            bathrooms=payload.bathrooms,
            size_sqft=payload.size_sqft,
            amenities=payload.amenities,
            investment_goals=[],
            nearby_schools=[],
            nearby_hospitals=[],
            developer=payload.developer,
            payment_plan=payload.payment_plan,
            available=False,
            assigned_employee="",
            assigned_staff_id=None,
            source_version="website-v1",
            source="website-managed",
            imported_at=now,
            slug=_slugify(payload.title, payload.city, property_id),
            publication_status="draft",
            availability_status="unconfirmed",
            edit_version=1,
        )
        session.add(record)
        _audit(session, staff.subject, "created", property_id, "draft")
        session.flush()
        result = _staff_listing(session, record)
    return StaffSlugResponse(data=result)


@router.get("/{property_id}", response_model=StaffSlugResponse)
def get_staff_listing(
    property_id: str,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffSlugResponse:
    with SessionLocal() as session:
        record = session.get(PropertyRecord, property_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Listing was not found")
        _require_listing_access(record, staff)
        return StaffSlugResponse(data=_staff_listing(session, record))


@router.patch("/{property_id}", response_model=StaffSlugResponse)
def update_staff_listing(
    property_id: str,
    payload: StaffListingPatch,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffSlugResponse:
    values = payload.model_dump(exclude={"edit_version"}, exclude_unset=True)
    if any(value is None for key, value in values.items() if key != "bathrooms"):
        raise HTTPException(status_code=422, detail="Only bathrooms may be cleared")
    with SessionLocal.begin() as session:
        record = session.get(PropertyRecord, property_id, with_for_update=True)
        if record is None:
            raise HTTPException(status_code=404, detail="Listing was not found")
        _require_listing_access(record, staff)
        update_values: dict[str, object] = dict(values)
        if "transaction_type" in update_values:
            update_values["purpose"] = update_values["transaction_type"]
        update_values["edit_version"] = payload.edit_version + 1
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(**update_values)
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Listing changed; reload before editing")
        _audit(session, staff.subject, "updated", property_id, "accepted")
        session.flush()
        updated = session.get(PropertyRecord, property_id)
        result_dto = _staff_listing(session, updated)
    return StaffSlugResponse(data=result_dto)


@router.post("/{property_id}/assign", response_model=StaffSlugResponse)
def assign_staff_listing(
    property_id: str,
    payload: StaffAssignListing,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
) -> StaffSlugResponse:
    with SessionLocal.begin() as session:
        record = session.get(PropertyRecord, property_id, with_for_update=True)
        assigned = session.get(StaffUserRecord, payload.staff_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Listing was not found")
        if assigned is None or not assigned.is_active or assigned.role not in {"manager", "agent"}:
            raise HTTPException(status_code=422, detail="Choose an active manager or agent")
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(
                assigned_staff_id=assigned.provider_subject,
                assigned_employee=assigned.display_name,
                edit_version=payload.edit_version + 1,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Listing changed; reload before assigning")
        _audit(session, staff.subject, "assigned", property_id, "accepted")
        session.flush()
        result_dto = _staff_listing(session, session.get(PropertyRecord, property_id))
    return StaffSlugResponse(data=result_dto)


@router.post("/{property_id}/availability", response_model=StaffSlugResponse)
def update_listing_availability(
    property_id: str,
    payload: StaffAvailabilityUpdate,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffSlugResponse:
    with SessionLocal.begin() as session:
        record = session.get(PropertyRecord, property_id, with_for_update=True)
        if record is None:
            raise HTTPException(status_code=404, detail="Listing was not found")
        _require_listing_access(record, staff)
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(
                availability_status=payload.status,
                available=payload.status == "available",
                availability_confirmed_at=datetime.now(UTC),
                edit_version=payload.edit_version + 1,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Listing changed; reload before confirming")
        _audit(session, staff.subject, "availability_confirmed", property_id, payload.status)
        session.flush()
        result_dto = _staff_listing(session, session.get(PropertyRecord, property_id))
    return StaffSlugResponse(data=result_dto)


@router.post("/{property_id}/confirm-content-permission", response_model=StaffSlugResponse)
def confirm_listing_content_permission(
    property_id: str,
    payload: StaffAssignListing,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
) -> StaffSlugResponse:
    with SessionLocal.begin() as session:
        record = session.get(PropertyRecord, property_id, with_for_update=True)
        if record is None:
            raise HTTPException(status_code=404, detail="Listing was not found")
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(
                content_permission_confirmed_at=datetime.now(UTC),
                edit_version=payload.edit_version + 1,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Listing changed; reload before confirming")
        _audit(session, staff.subject, "content_permission_confirmed", property_id, "accepted")
        session.flush()
        result_dto = _staff_listing(session, session.get(PropertyRecord, property_id))
    return StaffSlugResponse(data=result_dto)


@router.post("/{property_id}/publish", response_model=StaffSlugResponse)
def publish_staff_listing(
    property_id: str,
    payload: StaffListingPatch,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
) -> StaffSlugResponse:
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        record = session.get(PropertyRecord, property_id, with_for_update=True)
        if record is None:
            raise HTTPException(status_code=404, detail="Listing was not found")
        if settings.marketplace_enabled:
            raise HTTPException(409, "Marketplace listings must use revision moderation")
        if record.edit_version != payload.edit_version:
            raise HTTPException(status_code=409, detail="Listing changed; reload before publishing")
        assigned = (
            session.get(StaffUserRecord, record.assigned_staff_id)
            if record.assigned_staff_id
            else None
        )
        photo_count = (
            session.scalar(
                select(func.count())
                .select_from(PropertyMediaRecord)
                .where(
                    PropertyMediaRecord.property_id == property_id,
                    PropertyMediaRecord.is_public.is_(True),
                    PropertyMediaRecord.processing_status == "ready",
                    PropertyMediaRecord.derivative_object_path.is_not(None),
                    PropertyMediaRecord.public_url.is_not(None),
                )
            )
            or 0
        )
        confirmed_at = record.availability_confirmed_at
        if confirmed_at and confirmed_at.tzinfo is None:
            confirmed_at = confirmed_at.replace(tzinfo=UTC)
        complete = all(
            (
                record.title.strip(),
                len(record.description.strip()) >= 40,
                record.transaction_type in {"sale", "rent"},
                record.property_type
                in {"house", "apartment", "plot", "shop", "office", "warehouse", "other"},
                record.city.strip(),
                record.area.strip(),
                record.price_pkr > 0,
                record.size_sqft > 0,
                record.content_permission_confirmed_at is not None,
                assigned is not None and assigned.is_active,
                record.assigned_employee.strip(),
                confirmed_at is not None
                and confirmed_at >= now - AVAILABILITY_CONFIRMATION_MAX_AGE,
                record.availability_status in {"available", "unavailable", "reserved", "sold"},
                photo_count > 0,
            )
        )
        if not complete:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Listing needs complete facts, active staff assignment, current availability, "
                    "recorded content permission, and an approved public photo"
                ),
            )
        if record.latitude is not None and not -90 <= record.latitude <= 90:
            raise HTTPException(status_code=422, detail="Latitude is outside the valid range")
        if record.longitude is not None and not -180 <= record.longitude <= 180:
            raise HTTPException(status_code=422, detail="Longitude is outside the valid range")
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(
                publication_status="published",
                published_at=now,
                edit_version=payload.edit_version + 1,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Listing changed; reload before publishing")
        _audit(session, staff.subject, "published", property_id, "accepted")
        session.flush()
        result_dto = _staff_listing(session, session.get(PropertyRecord, property_id))
    return StaffSlugResponse(data=result_dto)


@router.post("/{property_id}/archive", response_model=StaffSlugResponse)
def archive_staff_listing(
    property_id: str,
    payload: StaffListingPatch,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
) -> StaffSlugResponse:
    with SessionLocal.begin() as session:
        record = session.get(PropertyRecord, property_id, with_for_update=True)
        if record is None:
            raise HTTPException(status_code=404, detail="Listing was not found")
        result = session.execute(
            update(PropertyRecord)
            .where(
                PropertyRecord.id == property_id,
                PropertyRecord.edit_version == payload.edit_version,
            )
            .values(publication_status="archived", edit_version=payload.edit_version + 1)
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Listing changed; reload before archiving")
        _audit(session, staff.subject, "archived", property_id, "accepted")
        session.flush()
        result_dto = _staff_listing(session, session.get(PropertyRecord, property_id))
    return StaffSlugResponse(data=result_dto)


_appointment_service = SqlAppointmentService(SqlPropertyRepository())


class StaffViewing(BaseModel):
    id: str
    reference: str
    property_id: str
    property_title: str | None
    employee: str
    starts_at: datetime
    client_name: str
    contact_email: EmailStr | None
    contact_phone: str | None
    status: str
    delivery_status: str


class StaffViewingPage(BaseModel):
    data: list[StaffViewing]
    pagination: dict[str, int]


class StaffViewingCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    reason: str = Field(default="", max_length=500)


class StaffViewingReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    new_starts_at: datetime


staff_viewings_router = APIRouter(prefix="/v1/staff/viewings", tags=["staff viewings"])


def _to_staff_viewing(session, record: AppointmentRecord) -> StaffViewing:
    cipher = ContactCipher()
    try:
        email = (
            cipher.decrypt(record.contact_email_ciphertext)
            if record.contact_email_ciphertext
            else None
        )
    except Exception:  # noqa: BLE001 - expired viewing contacts are intentionally erased
        email = None
    try:
        phone = (
            cipher.decrypt(record.contact_phone_ciphertext)
            if record.contact_phone_ciphertext
            else None
        )
    except Exception:  # noqa: BLE001 - expired viewing contacts are intentionally erased
        phone = None
    prop = session.get(PropertyRecord, record.property_id)
    prop_title = prop.title if prop else None
    delivery_status = "not_configured"
    if settings.google_token_path or settings.n8n_webhook_url:
        delivery_status = "delivered" if record.status in {"booked", "cancelled"} else "pending"
    return StaffViewing(
        id=record.id,
        reference=record.reference,
        property_id=record.property_id,
        property_title=prop_title,
        employee=record.employee,
        starts_at=record.starts_at
        if record.starts_at.tzinfo
        else record.starts_at.replace(tzinfo=UTC),
        client_name=record.client_name,
        contact_email=email,
        contact_phone=phone,
        status=record.status,
        delivery_status=delivery_status,
    )


@staff_viewings_router.get("", response_model=StaffViewingPage)
def list_staff_viewings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: str | None = None,
    property_id: str | None = None,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffViewingPage:
    statement = select(AppointmentRecord)
    if status:
        statement = statement.where(AppointmentRecord.status == status)
    if property_id:
        statement = statement.where(AppointmentRecord.property_id == property_id)
    if staff.role == "agent":
        statement = statement.where(AppointmentRecord.employee == staff.display_name)
    with SessionLocal() as session:
        total = (
            session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
            or 0
        )
        records = session.scalars(
            statement.order_by(AppointmentRecord.starts_at.desc(), AppointmentRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        data = [_to_staff_viewing(session, record) for record in records]
    return StaffViewingPage(
        data=data,
        pagination={"page": page, "page_size": page_size, "total": total},
    )


@staff_viewings_router.post("/{reference}/cancel", response_model=StaffViewing)
def cancel_staff_viewing(
    reference: str,
    payload: StaffViewingCancel,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffViewing:
    cipher = ContactCipher()
    with SessionLocal() as session:
        record = session.scalar(
            select(AppointmentRecord).where(AppointmentRecord.reference == reference)
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Viewing was not found")
        if record.status in {"cancelled", "completed"}:
            raise HTTPException(status_code=409, detail="Closed viewings cannot be changed")
        if staff.role == "agent" and record.employee.casefold() != staff.display_name.casefold():
            raise HTTPException(status_code=403, detail="Viewing is not assigned to this agent")
        decrypted_email = cipher.decrypt(record.contact_email_ciphertext)

    update_dto = AppointmentUpdate(
        reference=reference,
        contact_email=decrypted_email,
        idempotency_key=payload.idempotency_key,
        meeting_notes=payload.reason,
    )
    try:
        _appointment_service.update(update_dto, cancel=True, verified_contact=True)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))

    with SessionLocal() as session:
        rec = session.scalar(
            select(AppointmentRecord).where(AppointmentRecord.reference == reference)
        )
        return _to_staff_viewing(session, rec)


@staff_viewings_router.post("/{reference}/reschedule", response_model=StaffViewing)
def reschedule_staff_viewing(
    reference: str,
    payload: StaffViewingReschedule,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffViewing:
    cipher = ContactCipher()
    with SessionLocal() as session:
        record = session.scalar(
            select(AppointmentRecord).where(AppointmentRecord.reference == reference)
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Viewing was not found")
        if record.status in {"cancelled", "completed"}:
            raise HTTPException(status_code=409, detail="Closed viewings cannot be changed")
        if staff.role == "agent" and record.employee.casefold() != staff.display_name.casefold():
            raise HTTPException(status_code=403, detail="Viewing is not assigned to this agent")
        decrypted_email = cipher.decrypt(record.contact_email_ciphertext)

    update_dto = AppointmentUpdate(
        reference=reference,
        contact_email=decrypted_email,
        idempotency_key=payload.idempotency_key,
        starts_at=payload.new_starts_at,
    )
    try:
        _appointment_service.update(update_dto, cancel=False, verified_contact=True)
    except ValueError as err:
        err_msg = str(err)
        if "already booked" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        raise HTTPException(status_code=422, detail=err_msg)

    with SessionLocal() as session:
        rec = session.scalar(
            select(AppointmentRecord).where(AppointmentRecord.reference == reference)
        )
        return _to_staff_viewing(session, rec)


class StaffAreaGuideCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city_slug: str = Field(min_length=2, max_length=64)
    area_slug: str = Field(min_length=2, max_length=128)
    title: str = Field(min_length=3, max_length=255)
    overview_markdown: str = Field(default="", max_length=10000)
    amenities_summary: str = Field(default="", max_length=5000)
    transport_info: str = Field(default="", max_length=5000)
    investment_outlook: str = Field(default="", max_length=5000)
    sources: list[dict[str, object]] = Field(default_factory=list)


class StaffAreaGuide(BaseModel):
    id: str
    city_slug: str
    area_slug: str
    title: str
    overview_markdown: str
    amenities_summary: str
    transport_info: str
    investment_outlook: str
    publication_status: str
    reviewed_at: datetime | None
    reviewer_id: str | None
    sources: list[dict[str, object]]
    created_at: datetime
    updated_at: datetime


staff_areas_router = APIRouter(prefix="/v1/staff/areas", tags=["staff areas"])


@staff_areas_router.get("", response_model=list[StaffAreaGuide])
def list_staff_area_guides(
    staff: StaffPrincipal = Depends(require_staff),
) -> list[StaffAreaGuide]:
    with SessionLocal() as session:
        records = session.scalars(
            select(AreaGuideRecord).order_by(AreaGuideRecord.title.asc())
        ).all()
        return [
            StaffAreaGuide(
                id=rec.id,
                city_slug=rec.city_slug,
                area_slug=rec.area_slug,
                title=rec.title,
                overview_markdown=rec.overview_markdown,
                amenities_summary=rec.amenities_summary,
                transport_info=rec.transport_info,
                investment_outlook=rec.investment_outlook,
                publication_status=rec.publication_status,
                reviewed_at=rec.reviewed_at,
                reviewer_id=rec.reviewer_id,
                sources=rec.sources_json or [],
                created_at=rec.created_at,
                updated_at=rec.updated_at,
            )
            for rec in records
        ]


@staff_areas_router.post("", response_model=StaffAreaGuide, status_code=201)
def create_staff_area_guide(
    payload: StaffAreaGuideCreate,
    staff: StaffPrincipal = Depends(require_roles("administrator", "manager")),
) -> StaffAreaGuide:
    now = datetime.now(UTC)
    guide_id = str(uuid4())
    with SessionLocal.begin() as session:
        existing = session.scalar(
            select(AreaGuideRecord).where(
                AreaGuideRecord.city_slug == payload.city_slug.lower(),
                AreaGuideRecord.area_slug == payload.area_slug.lower(),
            )
        )
        if existing:
            raise HTTPException(
                status_code=409, detail="An area guide for this city and area already exists"
            )
        record = AreaGuideRecord(
            id=guide_id,
            city_slug=payload.city_slug.lower(),
            area_slug=payload.area_slug.lower(),
            title=payload.title,
            overview_markdown=payload.overview_markdown,
            amenities_summary=payload.amenities_summary,
            transport_info=payload.transport_info,
            investment_outlook=payload.investment_outlook,
            publication_status="published",
            reviewed_at=now,
            reviewer_id=staff.subject,
            sources_json=payload.sources,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.flush()
        return StaffAreaGuide(
            id=record.id,
            city_slug=record.city_slug,
            area_slug=record.area_slug,
            title=record.title,
            overview_markdown=record.overview_markdown,
            amenities_summary=record.amenities_summary,
            transport_info=record.transport_info,
            investment_outlook=record.investment_outlook,
            publication_status=record.publication_status,
            reviewed_at=record.reviewed_at,
            reviewer_id=record.reviewer_id,
            sources=record.sources_json or [],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
