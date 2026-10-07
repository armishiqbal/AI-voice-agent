from __future__ import annotations

# FastAPI declares validated query and dependency objects in endpoint signatures.
# ruff: noqa: B008
import hashlib
import hmac
import re
import secrets
import smtplib
import time
from datetime import UTC, datetime
from email.mime.text import MIMEText
from math import ceil
from smtplib import SMTP_SSL
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.domain.models import AppointmentRequest
from app.repositories.appointments import SqlAppointmentService
from app.repositories.database import SessionLocal
from app.repositories.listing_visibility import (
    AVAILABILITY_CONFIRMATION_MAX_AGE,
    public_listing_conditions,
    viewing_eligibility_conditions,
)
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    AreaGuideRecord,
    ListingVerificationRecord,
    LocationRecord,
    OrganizationRecord,
    PropertyMediaRecord,
    PropertyRecord,
)

TransactionType = Literal["sale", "rent"]
PropertyType = Literal["house", "apartment", "plot", "shop", "office", "warehouse", "other"]
SortOrder = Literal["relevance", "price_asc", "price_desc", "bedrooms_desc", "size_desc", "newest"]
AvailabilityStatus = Literal["available", "needs_confirmation", "unavailable", "reserved", "sold"]


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
    publisher: dict[str, str] | None = None
    classification: str | None = None
    rental_period: str | None = None
    sqft_per_marla: int | None = None


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


PUBLIC_VIEWING_CONSENT_VERSION = "2026-10-03"


class PublicAreaGuide(BaseModel):
    id: str
    city_slug: str
    area_slug: str
    title: str
    overview_markdown: str
    amenities_summary: str
    transport_info: str
    investment_outlook: str
    reviewed_at: datetime | None
    sources: list[dict[str, object]]


class ViewingOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class ViewingOtpRequestResponse(BaseModel):
    email: str
    expires_in_seconds: int = 600
    message: str = "A 6-digit verification code has been sent to your email."
    debug_otp: str | None = None


class ViewingOtpVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class ViewingOtpVerifyResponse(BaseModel):
    email: str
    verification_token: str
    expires_in_seconds: int = 900


class PublicViewingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: str = Field(min_length=1, max_length=64)
    starts_at: datetime
    client_name: str = Field(min_length=2, max_length=100)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, min_length=7, max_length=32)
    verification_token: str = Field(min_length=10)
    consent: bool
    consent_version: str = Field(min_length=1, max_length=64)
    idempotency_key: UUID


class PublicViewingReceipt(BaseModel):
    reference: str
    property_id: str
    starts_at: datetime
    client_name: str
    status: str
    delivery_status: str


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
            elements = (
                func.json_each(PropertyRecord.amenities)
                .table_valued("key", "value")
                .alias(f"amenity_{abs(hash(expected))}")
            )
            match = (
                select(1)
                .select_from(elements)
                .where(func.lower(elements.c.value) == expected)
                .exists()
            )
            return statement.where(match)
        return statement.where(
            func.lower(cast(PropertyRecord.amenities, String)).like(f'%"{expected}"%')
        )

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

        organizations = {
            o.id: o
            for o in session.scalars(
                select(OrganizationRecord).where(
                    OrganizationRecord.id.in_(
                        [r.organization_id for r in records if r.organization_id]
                    ),
                    OrganizationRecord.status == "approved",
                )
            ).all()
        }
        locations = {
            (l.city, l.area): l
            for l in session.scalars(
                select(LocationRecord).where(
                    LocationRecord.city.in_([r.city for r in records]),
                    LocationRecord.reviewed.is_(True),
                )
            ).all()
        }
        response: list[PublicListing] = []
        for record in records:
            confirmed_at = (
                self._aware(record.availability_confirmed_at)
                if record.availability_confirmed_at
                else None
            )
            if record.availability_status == "available":
                fresh = (
                    confirmed_at is not None
                    and confirmed_at >= now - AVAILABILITY_CONFIRMATION_MAX_AGE
                )
                availability: AvailabilityStatus = "available" if fresh else "needs_confirmation"
            elif record.availability_status == "unconfirmed":
                availability = "needs_confirmation"
            else:
                # A false legacy flag is authoritative even if older website metadata says available.
                availability = record.availability_status if record.available else "unavailable"
            if record.availability_status == "available" and not record.available:
                availability = "unavailable"
            coordinates = None
            if (
                record.latitude is not None
                and record.longitude is not None
                and record.coordinates_approved_at is not None
            ):
                coordinates = PublicCoordinates(
                    latitude=record.latitude, longitude=record.longitude
                )
            response.append(
                PublicListing(
                    publisher={
                        "id": organizations[record.organization_id].id,
                        "slug": organizations[record.organization_id].slug,
                        "name": organizations[record.organization_id].name,
                    }
                    if record.organization_id in organizations
                    else None,
                    classification=record.classification,
                    rental_period=record.rental_period,
                    sqft_per_marla=locations[(record.city, record.area)].sqft_per_marla
                    if (record.city, record.area) in locations
                    else None,
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

    @staticmethod
    def _monthly_price():
        from sqlalchemy import case

        return case(
            (PropertyRecord.rental_period == "yearly", PropertyRecord.price_pkr / 12),
            else_=PropertyRecord.price_pkr,
        )

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
        bathrooms: int | None = None,
        classification: str | None = None,
        organization_id: str | None = None,
        west: float | None = None,
        south: float | None = None,
        east: float | None = None,
        north: float | None = None,
        sort: SortOrder = "newest",
        now: datetime | None = None,
    ) -> PublicListingListResponse:
        if (
            min_price_pkr is not None
            and max_price_pkr is not None
            and min_price_pkr > max_price_pkr
        ):
            raise ValueError("Minimum price cannot exceed maximum price")
        if (
            min_size_sqft is not None
            and max_size_sqft is not None
            and min_size_sqft > max_size_sqft
        ):
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
            raw_area = area.strip()
            clean_area = raw_area.replace("-", " ")
            clean_no_city = re.sub(r"\b(islamabad|rawalpindi|lahore|karachi)\b", "", clean_area, flags=re.IGNORECASE).strip()
            if "," in raw_area:
                area_name, qualified_city = raw_area.rsplit(",", 1)
                clean_name = area_name.strip().replace("-", " ")
                clean_name_no_city = re.sub(r"\b(islamabad|rawalpindi|lahore|karachi)\b", "", clean_name, flags=re.IGNORECASE).strip()
                area_predicates = [
                    PropertyRecord.area.ilike(f"%{area_name.strip()}%"),
                    PropertyRecord.area.ilike(f"%{clean_name}%"),
                ]
                if clean_name_no_city:
                    area_predicates.append(PropertyRecord.area.ilike(f"%{clean_name_no_city}%"))
                statement = statement.where(
                    and_(
                        or_(*area_predicates),
                        PropertyRecord.city.ilike(qualified_city.strip()),
                    )
                )
            else:
                area_predicates = [
                    PropertyRecord.area.ilike(f"%{raw_area}%"),
                    PropertyRecord.area.ilike(f"%{clean_area}%"),
                ]
                if clean_no_city:
                    area_predicates.append(PropertyRecord.area.ilike(f"%{clean_no_city}%"))
                statement = statement.where(or_(*area_predicates))
        if min_price_pkr is not None:
            statement = statement.where(self._monthly_price() >= min_price_pkr)
        if max_price_pkr is not None:
            statement = statement.where(self._monthly_price() <= max_price_pkr)
        if bathrooms is not None:
            statement = statement.where(PropertyRecord.bathrooms >= bathrooms)
        if classification:
            statement = statement.where(PropertyRecord.classification == classification)
        if organization_id:
            statement = statement.where(PropertyRecord.organization_id == organization_id)
        if all(v is not None for v in (west, south, east, north)):
            if west >= east or south >= north:
                raise ValueError("Invalid map bounds")
            statement = statement.where(
                PropertyRecord.longitude.between(west, east),
                PropertyRecord.latitude.between(south, north),
                PropertyRecord.coordinates_approved_at.is_not(None),
            )
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
            total = (
                session.scalar(
                    select(func.count()).select_from(statement.order_by(None).subquery())
                )
                or 0
            )
            orderings = {
                "relevance": (
                    func.coalesce(PropertyRecord.published_at, PropertyRecord.imported_at).desc(),
                    PropertyRecord.id.asc(),
                ),
                "newest": (
                    func.coalesce(PropertyRecord.published_at, PropertyRecord.imported_at).desc(),
                    PropertyRecord.id.asc(),
                ),
                "price_asc": (self._monthly_price().asc(), PropertyRecord.id.asc()),
                "price_desc": (self._monthly_price().desc(), PropertyRecord.id.asc()),
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

    def get_public_by_id(
        self, property_id: str, *, now: datetime | None = None
    ) -> PublicListing | None:
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

    def get_area_guide(self, city_slug: str, area_slug: str) -> PublicAreaGuide | None:
        clean_slug = area_slug.casefold().replace(" ", "-").replace("%20", "-")
        clean_spaced = area_slug.casefold().replace("-", " ").replace("%20", " ")
        with self.session_factory() as session:
            record = session.scalar(
                select(AreaGuideRecord).where(
                    func.lower(AreaGuideRecord.city_slug) == city_slug.casefold(),
                    or_(
                        func.lower(AreaGuideRecord.area_slug) == area_slug.casefold(),
                        func.lower(AreaGuideRecord.area_slug) == clean_slug,
                        func.replace(func.lower(AreaGuideRecord.area_slug), "-", " ") == clean_spaced,
                    ),
                    AreaGuideRecord.publication_status == "published",
                )
            )
            if not record:
                return None
            return PublicAreaGuide(
                id=record.id,
                city_slug=record.city_slug,
                area_slug=record.area_slug,
                title=record.title,
                overview_markdown=record.overview_markdown,
                amenities_summary=record.amenities_summary,
                transport_info=record.transport_info,
                investment_outlook=record.investment_outlook,
                reviewed_at=self._aware(record.reviewed_at),
                sources=record.sources_json or [],
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
    bathrooms: int | None = Query(default=None, ge=0, le=20),
    classification: Literal["residential", "commercial"] | None = None,
    organization_id: str | None = Query(default=None, max_length=36),
    west: float | None = Query(default=None, ge=-180, le=180),
    east: float | None = Query(default=None, ge=-180, le=180),
    south: float | None = Query(default=None, ge=-90, le=90),
    north: float | None = Query(default=None, ge=-90, le=90),
    sort: SortOrder = "newest",
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
) -> PublicListingListResponse:
    if min_price_pkr is not None and max_price_pkr is not None and min_price_pkr > max_price_pkr:
        raise HTTPException(422, "Minimum price cannot exceed maximum price")
    if min_size_sqft is not None and max_size_sqft is not None and min_size_sqft > max_size_sqft:
        raise HTTPException(422, "Minimum size cannot exceed maximum size")
    if amenities and (len(amenities) > 10 or any(len(item) > 64 for item in amenities)):
        raise HTTPException(422, "At most ten amenities of up to 64 characters may be requested")
    if any(v is not None for v in (west, east, south, north)) and (
        not all(v is not None for v in (west, east, south, north)) or west >= east or south >= north
    ):
        raise HTTPException(422, "Provide four valid map bounds")
    return catalog.list_public(
        bathrooms=bathrooms,
        classification=classification,
        organization_id=organization_id,
        west=west,
        east=east,
        south=south,
        north=north,
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


@router.get("/listings/by-id/{property_id}", response_model=PublicListing)
def get_public_listing_by_id(
    property_id: str,
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
) -> PublicListing:
    listing = catalog.get_public_by_id(property_id)
    if listing is None:
        raise HTTPException(404, "Published property was not found")
    if not catalog.can_reserve(property_id):
        raise HTTPException(409, "Property is no longer eligible for assistant recommendations")
    return listing


@router.get("/listings/{slug}", response_model=PublicListing)
def get_public_listing(
    slug: str,
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
) -> PublicListing:
    listing = catalog.get_public(slug)
    if listing is None:
        raise HTTPException(404, "Published property was not found")
    return listing


_VIEWING_OTP_STORE: dict[str, tuple[str, float, int]] = {}


def _otp_secret() -> bytes:
    if settings.app_env != "development" and not settings.pii_encryption_key:
        raise HTTPException(503, "Viewing verification is not configured")
    key = settings.pii_encryption_key or "default-awaaz-viewing-secret-key-32bytes"
    return key.encode()


def _create_otp(email: str) -> tuple[str | None, str]:
    _otp_secret()  # Fail before sending if production signing is not configured.
    code = f"{secrets.randbelow(900000) + 100000:06d}"
    development_code: str | None = None
    delivery_message: str
    if not settings.smtp_host:
        if settings.app_env != "development":
            raise HTTPException(status_code=503, detail="Viewing email delivery is not configured")
        development_code = code
        delivery_message = "Development code generated. No email was sent."
    else:
        if not settings.smtp_from_email:
            raise HTTPException(status_code=503, detail="Viewing email delivery is not configured")
        msg = MIMEText(
            f"Your Awaaz Estate viewing verification code is: {code}\n\n"
            "This code expires in 10 minutes.\n"
            "If you did not request a viewing, please ignore this email."
        )
        msg["Subject"] = "Awaaz Estate Viewing Verification Code"
        msg["From"] = str(settings.smtp_from_email)
        msg["To"] = email
        try:
            if settings.smtp_ssl:
                with SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=5.0) as smtp:
                    if settings.smtp_username and settings.smtp_password:
                        smtp.login(settings.smtp_username, settings.smtp_password)
                    if smtp.send_message(msg):
                        raise RuntimeError("Email provider rejected the recipient")
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5.0) as smtp:
                    if settings.smtp_starttls:
                        smtp.starttls()
                    if settings.smtp_username and settings.smtp_password:
                        smtp.login(settings.smtp_username, settings.smtp_password)
                    if smtp.send_message(msg):
                        raise RuntimeError("Email provider rejected the recipient")
        except (OSError, smtplib.SMTPException, RuntimeError) as error:
            raise HTTPException(
                status_code=503, detail="Viewing verification email could not be sent"
            ) from error
        delivery_message = "Verification email accepted by the configured mail server."

    hashed = hashlib.sha256(f"{code}:{email.casefold()}".encode()).hexdigest()
    if settings.marketplace_enabled:
        from datetime import timedelta

        from app.repositories.records import ViewingOtpRecord

        key = hashlib.sha256(email.casefold().encode()).hexdigest()
        with SessionLocal.begin() as session:
            row = session.get(ViewingOtpRecord, key, with_for_update=True)
            if not row:
                row = ViewingOtpRecord(email_hash=key)
                session.add(row)
            row.code_hash = hmac.new(
                _otp_secret(), f"{code}:{email.casefold()}".encode(), hashlib.sha256
            ).hexdigest()
            row.expires_at = datetime.now(UTC) + timedelta(minutes=10)
            row.attempts = 0
    else:
        _VIEWING_OTP_STORE[email.casefold()] = (hashed, time.time() + 600, 0)
    return development_code, delivery_message


def _verify_otp_code(email: str, code: str) -> str:
    if settings.marketplace_enabled:

        from app.repositories.records import ViewingOtpRecord

        key = hashlib.sha256(email.casefold().encode()).hexdigest()
        error = None
        status = 400
        with SessionLocal.begin() as session:
            row = session.get(ViewingOtpRecord, key, with_for_update=True)
            if not row:
                error = "Request a verification code first"
            elif row.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
                session.delete(row)
                error = "Verification code expired"
            elif row.attempts >= 5:
                session.delete(row)
                error = "Too many verification attempts"
                status = 429
            else:
                expected = hmac.new(
                    _otp_secret(), f"{code.strip()}:{email.casefold()}".encode(), hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(expected, row.code_hash):
                    row.attempts += 1
                    error = "Invalid verification code"
                else:
                    session.delete(row)
        if error:
            raise HTTPException(status, error)
        expiry = int(time.time()) + 900
        payload = f"{email.casefold()}:{expiry}"
        signature = hmac.new(_otp_secret(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}:{signature}"
    stored = _VIEWING_OTP_STORE.get(email.casefold())
    if not stored:
        raise HTTPException(
            status_code=400, detail="No verification code was requested for this email"
        )
    hashed, expires_at, attempts = stored
    if time.time() > expires_at:
        _VIEWING_OTP_STORE.pop(email.casefold(), None)
        raise HTTPException(
            status_code=400, detail="Verification code has expired. Request a new one."
        )
    if attempts >= 5:
        _VIEWING_OTP_STORE.pop(email.casefold(), None)
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new code.")

    current_hash = hashlib.sha256(f"{code.strip()}:{email.casefold()}".encode()).hexdigest()
    if not hmac.compare_digest(hashed, current_hash):
        _VIEWING_OTP_STORE[email.casefold()] = (hashed, expires_at, attempts + 1)
        raise HTTPException(status_code=400, detail="Invalid verification code")

    _VIEWING_OTP_STORE.pop(email.casefold(), None)
    token_expiry = int(time.time()) + 900
    payload = f"{email.casefold()}:{token_expiry}"
    signature = hmac.new(_otp_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def _check_verification_token(email: str, token: str) -> None:
    parts = token.split(":")
    if len(parts) != 3:
        raise HTTPException(status_code=403, detail="Invalid viewing verification token format")
    token_email, expiry_str, signature = parts
    try:
        expiry_ts = int(expiry_str)
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid viewing verification token")
    if token_email.casefold() != email.casefold():
        raise HTTPException(
            status_code=403, detail="Verification token was not issued for this email"
        )
    if time.time() > expiry_ts:
        raise HTTPException(status_code=403, detail="Verification token has expired")
    expected_sig = hmac.new(
        _otp_secret(), f"{token_email}:{expiry_str}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=403, detail="Invalid verification token signature")


@router.get("/areas/{city_slug}/{area_slug}", response_model=PublicAreaGuide)
def get_public_area_guide(
    city_slug: str,
    area_slug: str,
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
) -> PublicAreaGuide:
    guide = catalog.get_area_guide(city_slug, area_slug)
    if guide is None:
        raise HTTPException(404, "Published area guide was not found")
    return guide


@router.post("/viewings/request-otp", response_model=ViewingOtpRequestResponse)
def request_viewing_otp(payload: ViewingOtpRequest) -> ViewingOtpRequestResponse:
    debug_otp, message = _create_otp(str(payload.email))
    return ViewingOtpRequestResponse(
        email=str(payload.email),
        expires_in_seconds=600,
        message=message,
        debug_otp=debug_otp,
    )


@router.post("/viewings/verify-otp", response_model=ViewingOtpVerifyResponse)
def verify_viewing_otp(payload: ViewingOtpVerify) -> ViewingOtpVerifyResponse:
    token = _verify_otp_code(str(payload.email), payload.otp)
    return ViewingOtpVerifyResponse(
        email=str(payload.email),
        verification_token=token,
        expires_in_seconds=900,
    )


@router.post("/viewings", response_model=PublicViewingReceipt, status_code=201)
def create_public_viewing(payload: PublicViewingCreate) -> PublicViewingReceipt:
    if not payload.consent:
        raise HTTPException(status_code=422, detail="Consent is required to book a viewing")
    if payload.consent_version != PUBLIC_VIEWING_CONSENT_VERSION:
        raise HTTPException(
            status_code=422, detail="The consent wording version is no longer current"
        )
    _check_verification_token(str(payload.contact_email), payload.verification_token)

    with SessionLocal() as session:
        prop = session.get(PropertyRecord, payload.property_id)
        if prop is None or prop.publication_status != "published" or not prop.available:
            raise HTTPException(status_code=404, detail="Published property was not found")
        assigned_employee = prop.assigned_employee
        if not assigned_employee:
            raise HTTPException(
                status_code=422, detail="Property has no assigned employee for viewings"
            )

    appointment_req = AppointmentRequest(
        property_id=payload.property_id,
        employee=assigned_employee,
        starts_at=payload.starts_at,
        client_name=payload.client_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        consent=True,
        idempotency_key=payload.idempotency_key,
    )
    try:
        appointment = _appointment_service.book(appointment_req, verified_contact=True)
    except ValueError as err:
        err_msg = str(err)
        if "already booked" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        raise HTTPException(status_code=422, detail=err_msg)

    delivery_status = "not_configured"
    if settings.google_token_path or settings.n8n_webhook_url:
        delivery_status = "pending"

    return PublicViewingReceipt(
        reference=appointment.reference,
        property_id=appointment.property_id,
        starts_at=appointment.starts_at,
        client_name=appointment.client_name,
        status=appointment.status,
        delivery_status=delivery_status,
    )
