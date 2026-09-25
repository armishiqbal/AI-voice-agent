from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.records import OutboxEventRecord
from app.workers.outbox import OutboxWorker


@pytest.mark.asyncio
async def test_outbox_worker_delivers_registered_event() -> None:
    create_schema_for_local_development()
    event_id = str(uuid4())
    with SessionLocal.begin() as session:
        session.add(
            OutboxEventRecord(
                id=event_id,
                event_type="test.event",
                payload={"reference": "AES-TEST"},
                created_at=datetime.now(UTC),
            )
        )
    received: list[dict[str, object]] = []

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        received.append(payload)
        return {"provider": "test"}

    result = await OutboxWorker({"test.event": handler}).process_once()
    with SessionLocal() as session:
        event = session.scalar(select(OutboxEventRecord).where(OutboxEventRecord.id == event_id))
    assert result.delivered == 1
    assert received == [{"reference": "AES-TEST"}]
    assert event is not None and event.delivered_at is not None and event.claimed_by is None
    assert event.payload["delivery"] == {"provider": "test"}
    Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_outbox_worker_persists_retry_state_on_failure() -> None:
    create_schema_for_local_development()
    event_id = str(uuid4())
    with SessionLocal.begin() as session:
        session.add(OutboxEventRecord(id=event_id, event_type="test.event", payload={}))

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        del payload
        raise RuntimeError("calendar unavailable")

    result = await OutboxWorker({"test.event": handler}).process_once()
    with SessionLocal() as session:
        event = session.scalar(select(OutboxEventRecord).where(OutboxEventRecord.id == event_id))
    assert result.failed == 1
    assert event is not None and event.attempts == 1
    assert event.last_error == "calendar unavailable"
    assert event.next_attempt_at is not None and event.claimed_by is None
    Base.metadata.drop_all(bind=engine)
