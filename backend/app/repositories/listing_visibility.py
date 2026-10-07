"""Shared SQL visibility and viewing eligibility rules for catalog and voice paths."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, or_
from app.core.config import settings

from app.repositories.records import PropertyMediaRecord, PropertyRecord, OrganizationRecord, MembershipRecord

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
        .correlate(PropertyRecord)
        .exists()
    )
    publisher = select(OrganizationRecord.id).where(OrganizationRecord.id == PropertyRecord.organization_id, OrganizationRecord.status == "approved").exists()
    ownership = (or_(PropertyRecord.organization_id.is_(None),publisher),)
    marketplace = ()
    if settings.marketplace_enabled:
        publisher = select(OrganizationRecord.id).where(OrganizationRecord.id == PropertyRecord.organization_id, OrganizationRecord.status == "approved").exists()
        agent = select(MembershipRecord.id).where(MembershipRecord.organization_id == PropertyRecord.organization_id, MembershipRecord.subject == PropertyRecord.assigned_staff_id, MembershipRecord.active.is_(True)).exists()
        marketplace = (publisher, agent, PropertyRecord.classification.in_(("residential", "commercial")), ((PropertyRecord.transaction_type == "sale") | PropertyRecord.rental_period.in_(("monthly", "yearly"))),)
    production = () if settings.app_env == "development" else (~PropertyRecord.source.in_(("development-fixture", "test-only-evaluation-fixture")),)
    return (
        *ownership, *marketplace, *production,
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
