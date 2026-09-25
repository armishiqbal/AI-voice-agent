from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.domain.models import Property, PropertyQuery
from app.repositories.database import SessionLocal
from app.repositories.records import PropertyImportBatchRecord, PropertyRecord


def _to_domain(record: PropertyRecord) -> Property:
    return Property(
        id=record.id,
        title=record.title,
        city=record.city,
        area=record.area,
        purpose=record.purpose,
        price_pkr=record.price_pkr,
        bedrooms=record.bedrooms,
        size_sqft=record.size_sqft,
        amenities=record.amenities,
        investment_goals=record.investment_goals or [],
        nearby_schools=record.nearby_schools or [],
        nearby_hospitals=record.nearby_hospitals or [],
        developer=record.developer,
        payment_plan=record.payment_plan,
        available=record.available,
        assigned_employee=record.assigned_employee,
        source_version=record.source_version,
        source=record.source,
        imported_at=record.imported_at,
    )


class SqlPropertyRepository:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def list(self, query: PropertyQuery | None = None) -> list[Property]:
        statement = select(PropertyRecord)
        if query:
            if query.city:
                statement = statement.where(PropertyRecord.city.ilike(query.city))
            if query.area:
                statement = statement.where(PropertyRecord.area.ilike(f"%{query.area}%"))
            if query.purpose:
                statement = statement.where(PropertyRecord.purpose == query.purpose)
            if query.max_budget_pkr:
                statement = statement.where(PropertyRecord.price_pkr <= query.max_budget_pkr)
            if query.bedrooms is not None:
                statement = statement.where(PropertyRecord.bedrooms >= query.bedrooms)
        with self.session_factory() as session:
            values = [_to_domain(record) for record in session.scalars(statement).all()]
        if query and query.amenities:
            required = {item.casefold() for item in query.amenities}
            values = [
                item
                for item in values
                if required.issubset({amenity.casefold() for amenity in item.amenities})
            ]
        if query and query.investment_goal:
            goal = query.investment_goal.casefold()
            values = [
                item
                for item in values
                if any(goal in value.casefold() for value in item.investment_goals)
            ]
        return values

    def get_available(self, property_id: str) -> Property | None:
        normalized_id = property_id.replace("DEMO-", "PROP-") if property_id.startswith("DEMO-") else property_id
        with self.session_factory() as session:
            record = session.scalar(
                select(PropertyRecord).where(
                    (PropertyRecord.id == property_id) | (PropertyRecord.id == normalized_id),
                    PropertyRecord.available.is_(True),
                )
            )
            return _to_domain(record) if record else None

    def import_properties(
        self,
        values: list[Property],
        source: str = "demo-fixture",
        validation_errors: list[dict[str, object]] | None = None,
    ) -> str:
        imported_at = datetime.now(UTC)
        batch_id = str(uuid4())
        with self.session_factory.begin() as session:
            session.add(
                PropertyImportBatchRecord(
                    id=batch_id,
                    source=source,
                    imported_at=imported_at,
                    record_count=len(values),
                    validation_errors=validation_errors or [],
                )
            )
            for value in values:
                record = session.get(PropertyRecord, value.id)
                payload = value.model_dump()
                payload.pop("source", None)
                payload.pop("imported_at", None)
                if record:
                    for key, item in payload.items():
                        setattr(record, key, item)
                    record.source = source
                    record.imported_at = imported_at
                else:
                    session.add(PropertyRecord(**payload, source=source, imported_at=imported_at))
        return batch_id

    def count(self) -> int:
        with self.session_factory() as session:
            return len(session.scalars(select(PropertyRecord.id)).all())
