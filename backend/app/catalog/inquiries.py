from __future__ import annotations

# FastAPI declares validated request and identity dependencies in endpoint signatures.
# ruff: noqa: B008
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.catalog.public import PublicCatalogRepository
from app.catalog.staff_auth import StaffPrincipal, require_staff
from app.core.config import settings
from app.core.pii import ContactCipher
from app.repositories.database import SessionLocal
from app.repositories.records import (
    StaffUserRecord,
    WebsiteInquiryActivityRecord,
    WebsiteInquiryRecord,
)
from app.services.appointments import redact_for_retention

PUBLIC_INQUIRY_CONSENT_VERSION = "2026-10-03"
PUBLIC_INQUIRY_RETENTION = timedelta(days=365)

RequestType = Literal["property", "callback", "seller", "general"]
ContactPreference = Literal["email", "phone", "whatsapp"]
InquiryStatus = Literal["new", "contacted", "qualified", "viewing_scheduled", "closed"]


class PublicInquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: str | None = Field(default=None, min_length=1, max_length=64)
    request_type: RequestType
    client_name: str = Field(min_length=2, max_length=100)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, min_length=7, max_length=32)
    contact_preference: ContactPreference
    message: str = Field(default="", max_length=2000)
    consent: bool
    consent_version: str = Field(min_length=1, max_length=64)
    idempotency_key: UUID

    @field_validator("consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required before storing an inquiry")
        return value

    @model_validator(mode="after")
    def validate_contact_and_version(self) -> PublicInquiryCreate:
        if not self.contact_email and not self.contact_phone:
            raise ValueError("Provide an email address or phone number")
        if self.contact_preference == "email" and not self.contact_email:
            raise ValueError("Email contact preference requires an email address")
        if self.contact_preference in {"phone", "whatsapp"} and not self.contact_phone:
            raise ValueError("Phone or WhatsApp preference requires a phone number")
        if self.request_type == "property" and not self.property_id:
            raise ValueError("Property inquiries require a published listing")
        if self.consent_version != PUBLIC_INQUIRY_CONSENT_VERSION:
            raise ValueError("The consent wording version is no longer current")
        return self


class PublicInquiryReceipt(BaseModel):
    inquiry_id: UUID
    status: str
    created_at: datetime
    delivery_status: str


class StaffInquiryActivity(BaseModel):
    action: str
    details: str
    actor_staff_id: str
    created_at: datetime


class StaffInquiry(BaseModel):
    inquiry_id: UUID
    property_id: str | None
    request_type: str
    client_name: str
    contact_email: EmailStr | None
    contact_phone: str | None
    contact_preference: str
    message: str
    consent_version: str
    consent_purpose: str
    consented_at: datetime
    workflow_status: str
    delivery_status: str
    assigned_staff_id: str | None
    follow_up_at: datetime | None
    closing_outcome: str | None
    edit_version: int
    created_at: datetime
    expires_at: datetime
    activity: list[StaffInquiryActivity]


class StaffInquiryPage(BaseModel):
    data: list[StaffInquiry]
    pagination: dict[str, int]


class StaffInquiryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_version: int = Field(ge=1)
    workflow_status: InquiryStatus | None = None
    assigned_staff_id: str | None = Field(default=None, max_length=128)
    follow_up_at: datetime | None = None
    closing_outcome: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("follow_up_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Follow-up time must include a timezone")
        return value.astimezone(UTC) if value else None


def _inquiry_access(record: WebsiteInquiryRecord, staff: StaffPrincipal) -> None:
    if staff.role == "agent" and record.assigned_staff_id != staff.subject:
        raise HTTPException(status_code=403, detail="Inquiry is not assigned to this agent")


def _staff_inquiry(session, record: WebsiteInquiryRecord) -> StaffInquiry:
    if not settings.pii_encryption_key:
        raise HTTPException(status_code=503, detail="Inquiry decryption is not configured")
    cipher = ContactCipher()
    try:
        client_name = cipher.decrypt(record.client_name_ciphertext)
        email = (
            cipher.decrypt(record.contact_email_ciphertext)
            if record.contact_email_ciphertext
            else None
        )
        phone = (
            cipher.decrypt(record.contact_phone_ciphertext)
            if record.contact_phone_ciphertext
            else None
        )
    except Exception as error:  # key rotation must not return partial/corrupt contact data
        raise HTTPException(status_code=503, detail="Inquiry encryption key cannot decrypt this record") from error
    activities = session.scalars(
        select(WebsiteInquiryActivityRecord)
        .where(WebsiteInquiryActivityRecord.inquiry_id == record.id)
        .order_by(WebsiteInquiryActivityRecord.created_at.asc())
    ).all()
    return StaffInquiry(
        inquiry_id=UUID(record.id),
        property_id=record.property_id,
        request_type=record.request_type,
        client_name=client_name,
        contact_email=email,
        contact_phone=phone,
        contact_preference=record.contact_preference,
        message=record.message_redacted,
        consent_version=record.consent_version,
        consent_purpose=record.consent_purpose,
        consented_at=record.consented_at,
        workflow_status=record.workflow_status,
        delivery_status=record.delivery_status,
        assigned_staff_id=record.assigned_staff_id,
        follow_up_at=record.follow_up_at,
        closing_outcome=record.closing_outcome,
        edit_version=record.edit_version,
        created_at=record.created_at,
        expires_at=record.expires_at,
        activity=[
            StaffInquiryActivity(
                action=item.action,
                details=item.details_redacted,
                actor_staff_id=item.actor_staff_id,
                created_at=item.created_at,
            )
            for item in activities
        ],
    )


def _require_public_inquiry_ready(session) -> None:
    if not settings.pii_encryption_key:
        raise HTTPException(status_code=503, detail="Inquiry encryption is not configured")
    if not settings.supabase_url:
        raise HTTPException(status_code=503, detail="Staff identity provider is not configured")
    active_staff = session.scalar(
        select(func.count()).select_from(StaffUserRecord).where(StaffUserRecord.is_active.is_(True))
    ) or 0
    if active_staff == 0:
        raise HTTPException(status_code=503, detail="Inquiry processing staff are not configured")


def _fingerprint(payload: PublicInquiryCreate) -> str:
    secret = settings.pii_encryption_key
    if not secret:
        raise HTTPException(status_code=503, detail="Inquiry encryption is not configured")
    normalized = payload.model_dump(mode="json", exclude={"idempotency_key"})
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hmac.new(hashlib.sha256(secret.encode()).digest(), serialized.encode(), hashlib.sha256).hexdigest()


def _receipt(record: WebsiteInquiryRecord) -> PublicInquiryReceipt:
    return PublicInquiryReceipt(
        inquiry_id=UUID(record.id),
        status=record.workflow_status,
        created_at=record.created_at,
        delivery_status=record.delivery_status,
    )


public_router = APIRouter(prefix="/v1/public", tags=["public inquiries"])
staff_router = APIRouter(prefix="/v1/staff/inquiries", tags=["staff inquiries"])


@public_router.post("/inquiries", response_model=PublicInquiryReceipt, status_code=201)
def create_public_inquiry(payload: PublicInquiryCreate) -> PublicInquiryReceipt:
    fingerprint = _fingerprint(payload)
    key = str(payload.idempotency_key)
    with SessionLocal() as session:
        _require_public_inquiry_ready(session)
        existing = session.scalar(
            select(WebsiteInquiryRecord).where(WebsiteInquiryRecord.idempotency_key == key)
        )
        if existing:
            if not hmac.compare_digest(existing.request_fingerprint, fingerprint):
                raise HTTPException(status_code=409, detail="Idempotency key was used for another request")
            return _receipt(existing)

    if payload.property_id and PublicCatalogRepository().get_public_by_id(payload.property_id) is None:
        raise HTTPException(status_code=404, detail="Published property was not found")
    from app.repositories.records import PropertyRecord
    with SessionLocal() as session:
        property_record=session.get(PropertyRecord,payload.property_id) if payload.property_id else None
        org_id=property_record.organization_id if property_record else "awaaz"
        agent_id=property_record.assigned_staff_id if property_record else None
    cipher = ContactCipher()
    now = datetime.now(UTC)
    inquiry_id = str(uuid4())
    record = WebsiteInquiryRecord(
        id=inquiry_id,
        organization_id=org_id,agent_subject=agent_id,assigned_staff_id=agent_id,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        property_id=payload.property_id,
        request_type=payload.request_type,
        client_name_ciphertext=cipher.encrypt(payload.client_name),
        contact_email_ciphertext=cipher.encrypt(str(payload.contact_email)) if payload.contact_email else None,
        contact_phone_ciphertext=cipher.encrypt(payload.contact_phone) if payload.contact_phone else None,
        contact_preference=payload.contact_preference,
        message_redacted=redact_for_retention(payload.message),
        consent_version=payload.consent_version,
        consent_purpose=f"website_{payload.request_type}",
        consent_channel="website",
        consented_at=now,
        workflow_status="new",
        delivery_status="not_configured",
        edit_version=1,
        created_at=now,
        expires_at=now + PUBLIC_INQUIRY_RETENTION,
    )
    try:
        with SessionLocal.begin() as session:
            _require_public_inquiry_ready(session)
            session.add(record)
            session.flush()
            receipt = _receipt(record)
    except IntegrityError:
        # A concurrent retry can win the unique idempotency index. Only the opaque receipt is replayed.
        with SessionLocal() as session:
            existing = session.scalar(
                select(WebsiteInquiryRecord).where(WebsiteInquiryRecord.idempotency_key == key)
            )
            if existing and hmac.compare_digest(existing.request_fingerprint, fingerprint):
                return _receipt(existing)
            if existing:
                raise HTTPException(status_code=409, detail="Idempotency key was used for another request")
        raise
    return receipt


@staff_router.get("", response_model=StaffInquiryPage)
def list_staff_inquiries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: InquiryStatus | None = None,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffInquiryPage:
    statement = select(WebsiteInquiryRecord).where(WebsiteInquiryRecord.expires_at > datetime.now(UTC))
    if status:
        statement = statement.where(WebsiteInquiryRecord.workflow_status == status)
    if staff.role == "agent":
        statement = statement.where(WebsiteInquiryRecord.assigned_staff_id == staff.subject)
    with SessionLocal() as session:
        total = session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ) or 0
        records = session.scalars(
            statement.order_by(WebsiteInquiryRecord.created_at.desc(), WebsiteInquiryRecord.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        data = [_staff_inquiry(session, record) for record in records]
    return StaffInquiryPage(
        data=data,
        pagination={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    )


@staff_router.get("/{inquiry_id}", response_model=StaffInquiry)
def get_staff_inquiry(
    inquiry_id: UUID,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffInquiry:
    with SessionLocal() as session:
        record = session.get(WebsiteInquiryRecord, str(inquiry_id))
        if record is None or record.expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=404, detail="Inquiry was not found")
        _inquiry_access(record, staff)
        return _staff_inquiry(session, record)


@staff_router.patch("/{inquiry_id}", response_model=StaffInquiry)
def update_staff_inquiry(
    inquiry_id: UUID,
    payload: StaffInquiryUpdate,
    staff: StaffPrincipal = Depends(require_staff),
) -> StaffInquiry:
    changes = payload.model_dump(exclude={"edit_version", "note"}, exclude_unset=True)
    if any(value is None for key, value in changes.items() if key != "follow_up_at"):
        raise HTTPException(status_code=422, detail="Assignment and closing outcome cannot be cleared")
    if "assigned_staff_id" in changes and staff.role not in {"administrator", "manager"}:
        raise HTTPException(status_code=403, detail="Only managers can assign inquiries")
    if changes.get("assigned_staff_id"):
        with SessionLocal() as session:
            assignee = session.get(StaffUserRecord, changes["assigned_staff_id"])
            if assignee is None or not assignee.is_active or assignee.role not in {"manager", "agent"}:
                raise HTTPException(status_code=422, detail="Choose an active manager or agent")
    with SessionLocal.begin() as session:
        record = session.get(WebsiteInquiryRecord, str(inquiry_id), with_for_update=True)
        if record is None or record.expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=404, detail="Inquiry was not found")
        _inquiry_access(record, staff)
        if changes.get("workflow_status") == "closed" and not (
            changes.get("closing_outcome") or record.closing_outcome
        ):
            raise HTTPException(status_code=422, detail="Closing an inquiry requires an outcome")
        changes["edit_version"] = payload.edit_version + 1
        result = session.execute(
            update(WebsiteInquiryRecord)
            .where(
                WebsiteInquiryRecord.id == str(inquiry_id),
                WebsiteInquiryRecord.edit_version == payload.edit_version,
            )
            .values(**changes)
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Inquiry changed; reload before updating")
        note = redact_for_retention(payload.note or "")
        actions = []
        if "workflow_status" in changes:
            actions.append("status_changed")
        if "assigned_staff_id" in changes:
            actions.append("assigned")
        if "follow_up_at" in changes:
            actions.append("follow_up_changed")
        if note:
            actions.append("note_added")
        for action in actions:
            session.add(
                WebsiteInquiryActivityRecord(
                    id=str(uuid4()),
                    inquiry_id=str(inquiry_id),
                    actor_staff_id=staff.subject,
                    action=action,
                    details_redacted=note if action == "note_added" else "",
                    created_at=datetime.now(UTC),
                )
            )
        session.flush()
        updated = session.get(WebsiteInquiryRecord, str(inquiry_id))
        return _staff_inquiry(session, updated)
