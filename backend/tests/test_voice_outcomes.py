from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.domain.models import Intent
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.records import OutboxEventRecord
from app.repositories.voice_outcomes import record_voice_call_outcome
from app.workers.handlers import build_internal_handlers
from app.workers.outbox import OutboxRunResult, OutboxWorker


@pytest.mark.asyncio
async def test_completed_voice_call_outcome_is_pii_free_and_idempotent() -> None:
    Base.metadata.drop_all(bind=engine)
    create_schema_for_local_development()
    state = SimpleNamespace(
        intent=Intent.BOOK,
        lead_profile={"qualified_intent": "buy"},
        detected_language="ur-Latn",
        city="Karachi",
        area="DHA +1 415 555 0100 ali@example.com",
        budget=50_000_000,
        selected_property_ids=["DEMO-001"],
        retrieved_sources=["property:DEMO-001:demo-v1"],
        tool_results={
            "budget_vs_listing": {
                "below_list": True,
                "lowest_matching_price_pkr": 72_000_000,
            }
        },
        escalation_reason=None,
    )
    try:
        event_id = record_voice_call_outcome(
            conversation_id="CA-test-call-1",
            channel="twilio",
            duration_ms=42_000,
            state=state,
        )
        repeated_id = record_voice_call_outcome(
            conversation_id="CA-test-call-1",
            channel="twilio",
            duration_ms=42_000,
            state=state,
        )
        assert repeated_id == event_id
        with SessionLocal() as session:
            events = session.scalars(
                select(OutboxEventRecord).where(
                    OutboxEventRecord.event_type == "voice.call_completed"
                )
            ).all()
        assert len(events) == 1
        payload = events[0].payload
        assert payload["call_id"] == "CA-test-call-1"
        assert payload["intent"] == "buy"
        assert payload["budget_below_list"] is True
        assert payload["area"] == "DHA [phone redacted] [email redacted]"
        assert "cheapest matching" in payload["summary"]
        serialized = str(payload).casefold()
        assert not any(value in serialized for value in ("@", "+92", "transcript", "audio"))

        assert await OutboxWorker(build_internal_handlers()).process_once() == OutboxRunResult(
            claimed=1, delivered=1, failed=0
        )
        with SessionLocal() as session:
            delivered_event = session.get(OutboxEventRecord, event_id)
            assert delivered_event is not None
            assert delivered_event.delivered_at is not None
            assert delivered_event.payload["delivery"] == {
                "provider": "internal_crm_log",
                "call_id": "CA-test-call-1",
                "status": "recorded",
            }
    finally:
        Base.metadata.drop_all(bind=engine)
