"""Customer owned saved records; no contact identity is accepted from the model."""

# FastAPI resolves validated dependencies from endpoint signatures.
# ruff: noqa: B008
import secrets
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from app.catalog.identity import Identity, digest, require_identity
from app.catalog.public import PropertyType, PublicCatalogRepository, TransactionType
from app.core.config import settings
from app.repositories.database import SessionLocal
from app.repositories.records import (
    AppointmentRecord,
    CustomerFavoriteRecord,
    OutboxEventRecord,
    SavedSearchRecord,
)

router = APIRouter(prefix="/v1/me", tags=["customer records"])
public = APIRouter(prefix="/v1/public", tags=["notification consent"])


def enabled():
    if not settings.customer_features_enabled:
        raise HTTPException(503, "Customer features are not enabled")


class FavoriteMerge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slugs: list[str] = Field(max_length=100)


@router.get("/favorites")
def favorites(identity: Identity = Depends(require_identity)):
    enabled()
    with SessionLocal() as session:
        ids = session.scalars(
            select(CustomerFavoriteRecord.property_id).where(
                CustomerFavoriteRecord.subject == identity.subject
            )
        ).all()
    catalog = PublicCatalogRepository()
    data = []
    unavailable = 0
    for pid in ids:
        record = catalog.get_public_by_id(pid)
        if record:
            data.append(record)
        else:
            unavailable += 1
    return {"data": data, "unavailable_count": unavailable}


@router.post("/favorites/merge")
def merge(payload: FavoriteMerge, identity: Identity = Depends(require_identity)):
    enabled()
    catalog = PublicCatalogRepository()
    records = [catalog.get_public(slug) for slug in set(payload.slugs)]
    with SessionLocal.begin() as session:
        # Serialize merges for one session/customer, preventing duplicate concurrent inserts.
        from app.repositories.records import ApplicationSessionRecord

        session.scalar(
            select(ApplicationSessionRecord)
            .where(ApplicationSessionRecord.subject == identity.subject)
            .with_for_update()
        )
        for p in records:
            if p and not session.get(CustomerFavoriteRecord, (identity.subject, p.id)):
                session.add(CustomerFavoriteRecord(subject=identity.subject, property_id=p.id))
    return {"status": "merged"}


@router.delete("/favorites/{property_id}")
def remove_favorite(property_id: str, identity: Identity = Depends(require_identity)):
    enabled()
    with SessionLocal.begin() as session:
        session.execute(
            delete(CustomerFavoriteRecord).where(
                CustomerFavoriteRecord.subject == identity.subject,
                CustomerFavoriteRecord.property_id == property_id,
            )
        )
    return {"status": "removed"}


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str | None = Field(default=None, max_length=128)
    transaction_type: TransactionType | None = None
    property_type: PropertyType | None = None
    city: str | None = Field(default=None, max_length=64)
    area: str | None = Field(default=None, max_length=128)
    min_price_pkr: int | None = Field(default=None, gt=0)
    max_price_pkr: int | None = Field(default=None, gt=0)
    bedrooms: int | None = Field(default=None, ge=0, le=10)
    bathrooms: int | None = Field(default=None, ge=0, le=20)
    min_size_sqft: int | None = Field(default=None, gt=0)
    max_size_sqft: int | None = Field(default=None, gt=0)
    amenities: list[str] = Field(default_factory=list, max_length=10)


class SearchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    filters: SearchFilters
    notification_consent: bool = False
    consent_version: str | None = None


@router.get("/searches")
def searches(identity: Identity = Depends(require_identity)):
    enabled()
    with SessionLocal() as session:
        return {
            "data": [
                {
                    "id": s.id,
                    "name": s.name,
                    "filters": s.filters,
                    "notification_consent": s.notification_consent,
                    "active": s.active,
                }
                for s in session.scalars(
                    select(SavedSearchRecord).where(SavedSearchRecord.subject == identity.subject)
                ).all()
            ]
        }


@router.post("/searches", status_code=201)
def save_search(payload: SearchCreate, identity: Identity = Depends(require_identity)):
    enabled()
    if payload.notification_consent and payload.consent_version != "2026-10-04":
        raise HTTPException(422, "Current notification consent is required")
    filters = payload.filters.model_dump(exclude_none=True)
    try:
        PublicCatalogRepository().list_public(page_size=1, **filters)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    sid = str(uuid4())
    token = secrets.token_urlsafe(40)
    from app.core.pii import ContactCipher

    with SessionLocal.begin() as session:
        session.add(
            SavedSearchRecord(
                id=sid,
                subject=identity.subject,
                name=payload.name,
                filters=filters,
                notification_consent=payload.notification_consent,
                consent_version=payload.consent_version,
                active=True,
                unsubscribe_ciphertext=ContactCipher().encrypt(token),
                unsubscribe_hash=digest(token),
            )
        )
    # Capability is issued once; the worker stores it encrypted separately before sending.
    return {"id": sid, "unsubscribe_token": token, "status": "active"}


@router.delete("/searches/{search_id}")
def unsubscribe_owned(search_id: str, identity: Identity = Depends(require_identity)):
    enabled()
    with SessionLocal.begin() as session:
        row = session.get(SavedSearchRecord, search_id)
        if not row or row.subject != identity.subject:
            raise HTTPException(404, "Search was not found")
        row.active = False
        row.notification_consent = False
    return {"status": "unsubscribed"}


class Unsubscribe(BaseModel):
    token: str = Field(min_length=30, max_length=100)


@public.post("/alerts/unsubscribe")
def unsubscribe(payload: Unsubscribe):
    with SessionLocal.begin() as session:
        row = session.scalar(
            select(SavedSearchRecord).where(
                SavedSearchRecord.unsubscribe_hash == digest(payload.token)
            )
        )
        if not row:
            raise HTTPException(404, "Subscription was not found")
        row.active = False
        row.notification_consent = False
    return {"status": "unsubscribed"}


@router.get("/viewings")
def viewings(identity: Identity = Depends(require_identity)):
    from app.core.pii import ContactCipher

    cipher = ContactCipher()
    with SessionLocal() as session:
        # A verified identity must match the encrypted reservation contact. IDs alone grant nothing.
        records = []
        for r in session.scalars(
            select(AppointmentRecord)
            .where(
                AppointmentRecord.starts_at > datetime.now(UTC),
                AppointmentRecord.status.in_(("booked", "rescheduled")),
            )
            .order_by(AppointmentRecord.starts_at)
        ).all():
            try:
                owned = (
                    cipher.decrypt(r.contact_email_ciphertext).casefold()
                    == identity.email.casefold()
                )
            except ValueError:
                owned = False
            if owned:
                records.append(r)
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
                    "delivery_status": delivery.get(r.reference, "not_configured"),
                }
                for r in records
            ]
        }


class ViewingChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime | None = None
    cancel: bool = False
    idempotency_key: __import__("uuid").UUID


@router.patch("/viewings/{reference}")
def change_viewing(
    reference: str, payload: ViewingChange, identity: Identity = Depends(require_identity)
):
    from app.domain.models import AppointmentUpdate
    from app.repositories.appointments import SqlAppointmentService
    from app.repositories.properties import SqlPropertyRepository

    service = SqlAppointmentService(SqlPropertyRepository())
    try:
        service.get_for_contact(reference, identity.email)
        if not payload.cancel and not payload.starts_at:
            raise HTTPException(422, "Choose an available new slot")
        result = service.update(
            AppointmentUpdate(
                reference=reference,
                contact_email=identity.email,
                starts_at=payload.starts_at,
                idempotency_key=payload.idempotency_key,
            ),
            cancel=payload.cancel,
            verified_contact=True,
        )
        return {
            "reference": result.reference,
            "starts_at": result.starts_at,
            "status": result.status,
            "delivery_status": "pending",
        }
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
