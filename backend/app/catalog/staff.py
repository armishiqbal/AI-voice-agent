from __future__ import annotations

# FastAPI declares validated request and role dependencies in endpoint signatures.
# ruff: noqa: B008
import re
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update

from app.catalog.staff_auth import StaffPrincipal, require_roles, require_staff
from app.repositories.database import SessionLocal
from app.repositories.listing_visibility import AVAILABILITY_CONFIRMATION_MAX_AGE
from app.repositories.records import (
    PropertyMediaRecord,
    PropertyRecord,
    StaffUserRecord,
    ToolAuditEventRecord,
)

StaffTransactionType = Literal["sale", "rent"]
StaffPropertyType = Literal[
    "house", "apartment", "plot", "shop", "office", "warehouse", "other"
]
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
        total = session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ) or 0
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
        if record.edit_version != payload.edit_version:
            raise HTTPException(status_code=409, detail="Listing changed; reload before publishing")
        assigned = (
            session.get(StaffUserRecord, record.assigned_staff_id)
            if record.assigned_staff_id
            else None
        )
        photo_count = session.scalar(
            select(func.count()).select_from(PropertyMediaRecord).where(
                PropertyMediaRecord.property_id == property_id,
                PropertyMediaRecord.is_public.is_(True),
                PropertyMediaRecord.processing_status == "ready",
                PropertyMediaRecord.derivative_object_path.is_not(None),
                PropertyMediaRecord.public_url.is_not(None),
            )
        ) or 0
        confirmed_at = record.availability_confirmed_at
        if confirmed_at and confirmed_at.tzinfo is None:
            confirmed_at = confirmed_at.replace(tzinfo=UTC)
        complete = all(
            (
                record.title.strip(),
                len(record.description.strip()) >= 40,
                record.transaction_type in {"sale", "rent"},
                record.property_type in {
                    "house", "apartment", "plot", "shop", "office", "warehouse", "other"
                },
                record.city.strip(),
                record.area.strip(),
                record.price_pkr > 0,
                record.size_sqft > 0,
                record.content_permission_confirmed_at is not None,
                assigned is not None and assigned.is_active,
                record.assigned_employee.strip(),
                confirmed_at is not None and confirmed_at >= now - AVAILABILITY_CONFIRMATION_MAX_AGE,
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
