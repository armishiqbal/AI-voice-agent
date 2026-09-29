from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.models import LeadCreate
from app.repositories.database import Base
from app.repositories.leads import LeadRepository
from app.repositories.records import LeadRecord, OutboxEventRecord, ToolAuditEventRecord
from app.services.follow_up_reminders import LeadFollowUpScheduler
from app.workers.handlers import build_internal_handlers
from app.workers.outbox import OutboxWorker


def _database() -> tuple[sessionmaker, object]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    return factory, engine


def _lead(
    lead_id: str,
    follow_up_at: datetime,
    *,
    status: str = "new",
    enqueued_at: datetime | None = None,
) -> LeadRecord:
    return LeadRecord(
        id=lead_id,
        client_name="Test Person",
        contact_email_ciphertext="encrypted-test-value",
        intent="sell",
        city="Karachi",
        area="DHA Phase 6",
        budget_pkr=25_000_000,
        notes_redacted="",
        follow_up_at=follow_up_at,
        follow_up_enqueued_at=enqueued_at,
        status=status,
    )


def test_lead_follow_up_time_requires_timezone_and_normalizes_to_utc() -> None:
    base = {
        "client_name": "Test Person",
        "contact_email": "test@example.com",
        "intent": "sell",
        "consent": True,
    }
    local_time = datetime(2026, 9, 29, 17, 0, tzinfo=timezone(timedelta(hours=5)))
    lead = LeadCreate(**base, follow_up_at=local_time)
    assert lead.follow_up_at == datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="must include a timezone"):
        LeadCreate(**base, follow_up_at=datetime.fromisoformat("2026-09-29T12:00:00"))


def test_due_follow_up_is_enqueued_once_and_delivered_to_internal_crm(monkeypatch) -> None:
    factory, engine = _database()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    with factory.begin() as session:
        session.add_all(
            [
                _lead("due-1", now - timedelta(minutes=5)),
                _lead("future-1", now + timedelta(minutes=5)),
                _lead("already-queued", now - timedelta(minutes=2), enqueued_at=now),
                _lead("contacted-1", now - timedelta(minutes=1), status="contacted"),
            ]
        )

    scheduler = LeadFollowUpScheduler(factory)
    monkeypatch.setattr("app.workers.outbox.SessionLocal", factory)
    try:
        assert scheduler.enqueue_due(now=now) == 1
        assert scheduler.enqueue_due(now=now) == 0

        with factory() as session:
            event = session.scalar(
                select(OutboxEventRecord).where(
                    OutboxEventRecord.event_type == "lead.follow_up_due"
                )
            )
            lead = session.get(LeadRecord, "due-1")
        assert event is not None
        assert event.payload == {
            "event_type": "lead.follow_up_due",
            "lead_id": "due-1",
            "intent": "sell",
            "city": "Karachi",
            "area": "DHA Phase 6",
            "budget_pkr": 25_000_000,
            "follow_up_at": (now - timedelta(minutes=5)).isoformat(),
        }
        assert "client_name" not in event.payload
        assert "contact_email" not in event.payload
        assert lead is not None and lead.follow_up_enqueued_at is not None

        result = asyncio.run(OutboxWorker(build_internal_handlers()).process_once())
        assert result.claimed == 1
        assert result.delivered == 1
        with factory() as session:
            delivered = session.get(OutboxEventRecord, event.id)
        assert delivered is not None and delivered.delivered_at is not None
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_due_follow_up_list_and_completion_are_pii_minimized_and_idempotent(
    monkeypatch,
) -> None:
    factory, engine = _database()
    now = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    with factory.begin() as session:
        session.add(_lead("due-2", now - timedelta(minutes=1)))
        session.add(_lead("future-2", now + timedelta(minutes=1)))

    monkeypatch.setattr("app.repositories.leads.SessionLocal", factory)
    try:
        due = LeadRepository.list_due_followups(now=now)
        assert len(due) == 1
        assert due[0]["lead_id"] == "due-2"
        assert "client_name" not in due[0]
        assert "contact_email" not in due[0]

        with pytest.raises(ValueError, match="not due yet"):
            LeadRepository.complete_due_followup("future-2", now=now)
        with pytest.raises(LookupError, match="not found"):
            LeadRepository.complete_due_followup("missing-lead", now=now)
        assert LeadRepository.complete_due_followup("due-2", now=now) == {
            "lead_id": "due-2",
            "status": "contacted",
        }
        assert LeadRepository.complete_due_followup("due-2", now=now)["status"] == "contacted"
        assert LeadRepository.list_due_followups(now=now) == []

        with factory() as session:
            audits = session.scalars(
                select(ToolAuditEventRecord).where(
                    ToolAuditEventRecord.action == "lead.follow_up_completed"
                )
            ).all()
        assert len(audits) == 1
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
