from __future__ import annotations

# FastAPI declares validated query and dependency objects in endpoint signatures.
# ruff: noqa: B008
from datetime import UTC, datetime
from math import ceil
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from app.repositories.appointments import SqlAppointmentService
from app.repositories.database import SessionLocal
from app.repositories.listing_visibility import (
    AVAILABILITY_CONFIRMATION_MAX_AGE,
    public_listing_conditions,
    viewing_eligibility_conditions,
)
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    ListingVerificationRecord,
    PropertyMediaRecord,
    PropertyRecord,
)

TransactionType = Literal["sale", "rent"]
PropertyType = Literal["house", "apartment", "plot", "shop", "office", "warehouse", "other"]
SortOrder = Literal[
    "relevance", "price_asc", "price_desc", "bedrooms_desc", "size_desc", "newest"
]
AvailabilityStatus = Literal[
    "available", "needs_confirmation", "unavailable", "reserved", "sold"
]

class PublicPhoto(BaseModel):
    url: str
    alt_text: str
    sort_order: int

    @field_validator("url")
    @classmethod
    def public_derivative_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if value.startswith("/") and not value.startswith("//"):
            return value
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Public media URLs must be HTTPS or same-origin paths")
        return value


class PublicCoordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PublicVerification(BaseModel):
    status: Literal["not_reviewed", "reviewed", "verified"] = "not_reviewed"
    reviewed_at: datetime | None = None
    scope: str | None = None
    source_url: AnyHttpUrl | None = None

    @field_validator("source_url")
    @classmethod
    def verified_source_is_https(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (value.scheme != "https" or value.username or value.password):
            raise ValueError("Public verification sources must use HTTPS")
        return value


class PublicListing(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    transaction_type: TransactionType
    property_type: PropertyType
    city: str
    area: str
    price_pkr: int = Field(gt=0)
    bedrooms: int = Field(ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    size_sqft: int = Field(gt=0)
    amenities: list[str]
    photos: list[PublicPhoto]
    availability_status: AvailabilityStatus
    availability_confirmed_at: datetime | None
    verification: PublicVerification
    coordinates: PublicCoordinates | None


class PublicListingPagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PublicListingListResponse(BaseModel):
    data: list[PublicListing]
    pagination: PublicListingPagination


class PublicSlotsResponse(BaseModel):
    data: list[datetime]


class PublicCatalogRepository:
    """Database-backed read model that only serializes published public fields."""

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    @classmethod
    def _public_listing_predicate(cls):
        return public_listing_conditions()

    @staticmethod
    def _amenity_filter(statement, amenity: str, dialect: str):
        expected = amenity.casefold()
        if dialect == "postgresql":
            return statement.where(cast(PropertyRecord.amenities, JSONB).contains([amenity]))
        if dialect == "sqlite":
            elements = func.json_each(PropertyRecord.amenities).table_valued(
                "key", "value"
            ).alias(f"amenity_{abs(hash(expected))}")
            match = (
                select(1)
                .select_from(elements)
                .where(func.lower(elements.c.value) == expected)
                .exists()
            )
            return statement.where(match)
        return statement.where(func.lower(cast(PropertyRecord.amenities, String)).like(f'%"{expected}"%'))

    def _records_to_listings(
        self,
        session,
        records: list[PropertyRecord],
        now: datetime,
    ) -> list[PublicListing]:
        if not records:
            return []
        ids = [record.id for record in records]
        media_records = session.scalars(
            select(PropertyMediaRecord)
            .where(
                PropertyMediaRecord.property_id.in_(ids),
                PropertyMediaRecord.is_public.is_(True),
                PropertyMediaRecord.processing_status == "ready",
                PropertyMediaRecord.derivative_object_path.is_not(None),
                PropertyMediaRecord.public_url.is_not(None),
            )
            .order_by(PropertyMediaRecord.sort_order.asc(), PropertyMediaRecord.id.asc())
        ).all()
        photos_by_property: dict[str, list[PublicPhoto]] = {property_id: [] for property_id in ids}
        for media in media_records:
            photos_by_property[media.property_id].append(
                PublicPhoto(
                    url=media.public_url,
                    alt_text=media.alt_text,
                    sort_order=media.sort_order,
                )
            )

        verifications = session.scalars(
            select(ListingVerificationRecord)
            .where(ListingVerificationRecord.property_id.in_(ids))
            .order_by(ListingVerificationRecord.reviewed_at.desc(), ListingVerificationRecord.id)
        ).all()
        verification_by_property: dict[str, PublicVerification] = {}
        for review in verifications:
            if review.property_id in verification_by_property:
                continue
            expiry = self._aware(review.expires_at) if review.expires_at else None
            if review.result not in {"reviewed", "verified"} or (expiry and expiry <= now):
                continue
            verification_by_property[review.property_id] = PublicVerification(
                status=review.result,
                reviewed_at=self._aware(review.reviewed_at),
                scope=review.review_scope,
                source_url=review.public_source_url,
            )

        response: list[PublicListing] = []
        for record in records:
            confirmed_at = self._aware(record.availability_confirmed_at) if record.availability_confirmed_at else None
            if record.availability_status == "available":
                fresh = confirmed_at is not None and confirmed_at >= now - AVAILABILITY_CONFIRMATION_MAX_AGE
                availability: AvailabilityStatus = "available" if fresh else "needs_confirmation"
            elif record.availability_status == "unconfirmed":
                availability = "needs_confirmation"
            else:
                # A false legacy flag is authoritative even if older website metadata says available.
                availability = record.availability_status if record.available else "unavailable"
            coordinates = None
            if record.latitude is not None and record.longitude is not None:
                coordinates = PublicCoordinates(latitude=record.latitude, longitude=record.longitude)
            response.append(
                PublicListing(
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
                    photos=photos_by_property[record.id],
                    availability_status=availability,
                    availability_confirmed_at=confirmed_at,
                    verification=verification_by_property.get(record.id, PublicVerification()),
                    coordinates=coordinates,
                )
            )
        return response

    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def list_public(
        self,
        *,
        page: int = 1,
        page_size: int = 24,
        q: str | None = None,
        transaction_type: TransactionType | None = None,
        property_type: PropertyType | None = None,
        city: str | None = None,
        area: str | None = None,
        min_price_pkr: int | None = None,
        max_price_pkr: int | None = None,
        bedrooms: int | None = None,
        min_size_sqft: int | None = None,
        max_size_sqft: int | None = None,
        amenities: list[str] | None = None,
        sort: SortOrder = "newest",
        now: datetime | None = None,
    ) -> PublicListingListResponse:
        if min_price_pkr is not None and max_price_pkr is not None and min_price_pkr > max_price_pkr:
            raise ValueError("Minimum price cannot exceed maximum price")
        if min_size_sqft is not None and max_size_sqft is not None and min_size_sqft > max_size_sqft:
            raise ValueError("Minimum size cannot exceed maximum size")
        current_time = self._aware(now or datetime.now(UTC))
        statement = select(PropertyRecord).where(*self._public_listing_predicate())
        if q:
            pattern = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    PropertyRecord.title.ilike(pattern),
                    PropertyRecord.description.ilike(pattern),
                    PropertyRecord.city.ilike(pattern),
                    PropertyRecord.area.ilike(pattern),
                )
            )
        if transaction_type:
            statement = statement.where(PropertyRecord.transaction_type == transaction_type)
        if property_type:
            statement = statement.where(PropertyRecord.property_type == property_type)
        if city:
            statement = statement.where(PropertyRecord.city.ilike(city.strip()))
        if area:
            statement = statement.where(PropertyRecord.area.ilike(f"%{area.strip()}%"))
        if min_price_pkr is not None:
            statement = statement.where(PropertyRecord.price_pkr >= min_price_pkr)
        if max_price_pkr is not None:
            statement = statement.where(PropertyRecord.price_pkr <= max_price_pkr)
        if bedrooms is not None:
            statement = statement.where(PropertyRecord.bedrooms >= bedrooms)
        if min_size_sqft is not None:
            statement = statement.where(PropertyRecord.size_sqft >= min_size_sqft)
        if max_size_sqft is not None:
            statement = statement.where(PropertyRecord.size_sqft <= max_size_sqft)

        requested_amenities = list(dict.fromkeys((amenities or [])[:10]))
        with self.session_factory() as session:
            for amenity in requested_amenities:
                statement = self._amenity_filter(statement, amenity, session.bind.dialect.name)
            total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
            orderings = {
                "relevance": (PropertyRecord.imported_at.desc(), PropertyRecord.id.asc()),
                "newest": (PropertyRecord.imported_at.desc(), PropertyRecord.id.asc()),
                "price_asc": (PropertyRecord.price_pkr.asc(), PropertyRecord.id.asc()),
                "price_desc": (PropertyRecord.price_pkr.desc(), PropertyRecord.id.asc()),
                "bedrooms_desc": (PropertyRecord.bedrooms.desc(), PropertyRecord.id.asc()),
                "size_desc": (PropertyRecord.size_sqft.desc(), PropertyRecord.id.asc()),
            }
            records = session.scalars(
                statement.order_by(*orderings[sort]).offset((page - 1) * page_size).limit(page_size)
            ).all()
            data = self._records_to_listings(session, records, current_time)
        return PublicListingListResponse(
            data=data,
            pagination=PublicListingPagination(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=ceil(total / page_size) if total else 0,
            ),
        )

    def get_public(self, slug: str, *, now: datetime | None = None) -> PublicListing | None:
        current_time = self._aware(now or datetime.now(UTC))
        with self.session_factory() as session:
            record = session.scalar(
                select(PropertyRecord).where(
                    PropertyRecord.slug == slug,
                    *self._public_listing_predicate(),
                )
            )
            if not record:
                return None
            return self._records_to_listings(session, [record], current_time)[0]

    def get_public_by_id(self, property_id: str, *, now: datetime | None = None) -> PublicListing | None:
        current_time = self._aware(now or datetime.now(UTC))
        with self.session_factory() as session:
            record = session.scalar(
                select(PropertyRecord).where(
                    PropertyRecord.id == property_id,
                    *self._public_listing_predicate(),
                )
            )
            if not record:
                return None
            return self._records_to_listings(session, [record], current_time)[0]

    def can_reserve(self, property_id: str, *, now: datetime | None = None) -> bool:
        current_time = self._aware(now or datetime.now(UTC))
        with self.session_factory() as session:
            return bool(
                session.scalar(
                    select(PropertyRecord.id)
                    .where(
                        PropertyRecord.id == property_id,
                        *viewing_eligibility_conditions(current_time),
                    )
                    .limit(1)
                )
            )


def get_public_catalog() -> PublicCatalogRepository:
    return PublicCatalogRepository()


router = APIRouter(prefix="/v1/public", tags=["public catalog"])
_appointment_service = SqlAppointmentService(SqlPropertyRepository())


@router.get("/listings", response_model=PublicListingListResponse)
def list_public_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    q: str | None = Query(default=None, max_length=120),
    transaction_type: TransactionType | None = None,
    property_type: PropertyType | None = None,
    city: str | None = Query(default=None, max_length=64),
    area: str | None = Query(default=None, max_length=128),
    min_price_pkr: int | None = Query(default=None, gt=0),
    max_price_pkr: int | None = Query(default=None, gt=0),
    bedrooms: int | None = Query(default=None, ge=0, le=10),
    min_size_sqft: int | None = Query(default=None, gt=0),
    max_size_sqft: int | None = Query(default=None, gt=0),
    amenities: list[str] | None = Query(default=None, max_length=10),
    sort: SortOrder = "newest",
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
) -> PublicListingListResponse:
    if min_price_pkr is not None and max_price_pkr is not None and min_price_pkr > max_price_pkr:
        raise HTTPException(422, "Minimum price cannot exceed maximum price")
    if min_size_sqft is not None and max_size_sqft is not None and min_size_sqft > max_size_sqft:
        raise HTTPException(422, "Minimum size cannot exceed maximum size")
    if amenities and (len(amenities) > 10 or any(len(item) > 64 for item in amenities)):
        raise HTTPException(422, "At most ten amenities of up to 64 characters may be requested")
    return catalog.list_public(
        page=page,
        page_size=page_size,
        q=q,
        transaction_type=transaction_type,
        property_type=property_type,
        city=city,
        area=area,
        min_price_pkr=min_price_pkr,
        max_price_pkr=max_price_pkr,
        bedrooms=bedrooms,
        min_size_sqft=min_size_sqft,
        max_size_sqft=max_size_sqft,
        amenities=amenities,
        sort=sort,
    )


@router.get("/listings/{property_id}/slots", response_model=PublicSlotsResponse)
def public_listing_slots(
    property_id: str,
    horizon_days: int = Query(default=7, ge=1, le=31),
    limit: int = Query(default=3, ge=1, le=10),
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
) -> PublicSlotsResponse:
    if catalog.get_public_by_id(property_id) is None:
        raise HTTPException(404, "Published property was not found")
    if not catalog.can_reserve(property_id):
        return PublicSlotsResponse(data=[])
    return PublicSlotsResponse(
        data=_appointment_service.available_slots(
            property_id, horizon_days=horizon_days, limit=limit
        )
    )


@router.get("/listings/{slug}", response_model=PublicListing)
def get_public_listing(
    slug: str,
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
) -> PublicListing:
    listing = catalog.get_public(slug)
    if listing is None:
        raise HTTPException(404, "Published property was not found")
    return listing
