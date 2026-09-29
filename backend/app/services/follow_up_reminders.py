from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.repositories.database import SessionLocal
from app.repositories.records import LeadRecord, OutboxEventRecord


class LeadFollowUpScheduler:
    """Atomically turn due lead follow-ups into durable, PII-minimized outbox events."""

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def enqueue_due(self, now: datetime | None = None, limit: int = 100) -> int:
        current_time = now or datetime.now(UTC)
        with self.session_factory.begin() as session:
            leads = list(
                session.scalars(
                    select(LeadRecord)
                    .where(
                        LeadRecord.follow_up_at.is_not(None),
                        LeadRecord.status == "new",
                        LeadRecord.follow_up_at <= current_time,
                        LeadRecord.follow_up_enqueued_at.is_(None),
                    )
                    .order_by(LeadRecord.follow_up_at, LeadRecord.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            for lead in leads:
                scheduled_at = lead.follow_up_at
                if scheduled_at is None:
                    continue
                if scheduled_at.tzinfo is None:
                    scheduled_at = scheduled_at.replace(tzinfo=UTC)
                event_id = str(
                    uuid5(NAMESPACE_URL, f"awaaz:lead.follow_up_due:{lead.id}:{scheduled_at.isoformat()}")
                )
                session.add(
                    OutboxEventRecord(
                        id=event_id,
                        event_type="lead.follow_up_due",
                        payload={
                            "event_type": "lead.follow_up_due",
                            "lead_id": lead.id,
                            "intent": lead.intent,
                            "city": lead.city,
                            "area": lead.area,
                            "budget_pkr": lead.budget_pkr,
                            "follow_up_at": scheduled_at.isoformat(),
                        },
                    )
                )
                lead.follow_up_enqueued_at = current_time
            return len(leads)
