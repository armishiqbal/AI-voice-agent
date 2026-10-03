"""Shared SQL visibility and viewing eligibility rules for catalog and voice paths."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.repositories.records import PropertyMediaRecord, PropertyRecord

AVAILABILITY_CONFIRMATION_MAX_AGE = timedelta(days=30)
PUBLIC_PROPERTY_TYPES = ("house", "apartment", "plot", "shop", "office", "warehouse", "other")


def public_listing_conditions() -> tuple[object, ...]:
    approved_photo = (
        select(PropertyMediaRecord.id)
        .where(
            PropertyMediaRecord.property_id == PropertyRecord.id,
            PropertyMediaRecord.is_public.is_(True),
            PropertyMediaRecord.processing_status == "ready",
            PropertyMediaRecord.derivative_object_path.is_not(None),
            PropertyMediaRecord.public_url.is_not(None),
        )
        .exists()
    )
    return (
        PropertyRecord.publication_status == "published",
        PropertyRecord.slug.is_not(None),
        PropertyRecord.transaction_type.in_(("sale", "rent")),
        PropertyRecord.property_type.in_(PUBLIC_PROPERTY_TYPES),
        approved_photo,
    )


def viewing_eligibility_conditions(now: datetime | None = None) -> tuple[object, ...]:
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    cutoff = current_time - AVAILABILITY_CONFIRMATION_MAX_AGE
    return (
        *public_listing_conditions(),
        PropertyRecord.available.is_(True),
        PropertyRecord.availability_status == "available",
        PropertyRecord.availability_confirmed_at.is_not(None),
        PropertyRecord.availability_confirmed_at >= cutoff,
    )
