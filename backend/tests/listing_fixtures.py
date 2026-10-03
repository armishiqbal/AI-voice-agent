"""Explicit test-only publication setup for synthetic repository fixtures."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.domain.fixtures import demo_properties
from app.repositories.database import SessionLocal
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import PropertyMediaRecord, PropertyRecord


def import_publishable_demo_properties(
    repository: SqlPropertyRepository,
) -> None:
    """Import evaluation fixtures, then explicitly model approved test inventory."""
    repository.import_properties(demo_properties(), source="test-only-evaluation-fixture")
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        records = session.scalars(
            select(PropertyRecord).where(
                PropertyRecord.available.is_(True),
                PropertyRecord.purpose.in_(("sale", "rent")),
            )
        ).all()
        for record in records:
            record.transaction_type = record.purpose
            record.property_type = "house"
            record.publication_status = "published"
            record.availability_status = "available"
            record.availability_confirmed_at = now
            record.content_permission_confirmed_at = now
            record.published_at = now
            record.slug = f"test-{record.id.lower()}"
            session.add(
                PropertyMediaRecord(
                    id=f"test-media-{record.id.lower()}",
                    property_id=record.id,
                    original_object_path="tests/private-original.jpg",
                    derivative_object_path="tests/processed-public.jpg",
                    public_url="https://example.test/listing-photo.jpg",
                    alt_text="Test fixture photo",
                    sort_order=0,
                    processing_status="ready",
                    is_public=True,
                )
            )
