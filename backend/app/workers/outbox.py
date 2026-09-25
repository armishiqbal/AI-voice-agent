from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select

from app.repositories.database import SessionLocal
from app.repositories.records import OutboxEventRecord


class OutboxHandler(Protocol):
    async def __call__(self, payload: dict[str, object]) -> dict[str, object] | None: ...


@dataclass(frozen=True)
class OutboxRunResult:
    claimed: int
    delivered: int
    failed: int


class OutboxWorker:
    """Retries integration events without requiring an external workflow tool."""

    def __init__(
        self, handlers: dict[str, OutboxHandler], max_attempts: int = 8, lease_seconds: int = 300
    ) -> None:
        self.handlers = handlers
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        self.worker_id = uuid4().hex

    async def process_once(self, limit: int = 25) -> OutboxRunResult:
        now = datetime.now(UTC)
        with SessionLocal() as session:
            records = list(
                session.scalars(
                    select(OutboxEventRecord)
                    .where(
                        OutboxEventRecord.delivered_at.is_(None),
                        OutboxEventRecord.attempts < self.max_attempts,
                        (
                            OutboxEventRecord.next_attempt_at.is_(None)
                            | (OutboxEventRecord.next_attempt_at <= now)
                        ),
                        (
                            OutboxEventRecord.claimed_at.is_(None)
                            | (
                                OutboxEventRecord.claimed_at
                                <= now - timedelta(seconds=self.lease_seconds)
                            )
                        ),
                    )
                    .order_by(OutboxEventRecord.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            for record in records:
                record.claimed_at = now
                record.claimed_by = self.worker_id
            session.commit()
            events = [(record.id, record.event_type, dict(record.payload)) for record in records]

        delivered = 0
        failed = 0
        for event_id, event_type, payload in events:
            handler = self.handlers.get(event_type)
            if handler is None:
                await self._fail(event_id, f"No handler registered for {event_type}")
                failed += 1
                continue
            try:
                result = await handler(payload)
            except Exception as error:  # noqa: BLE001 - worker must persist retry state
                await self._fail(event_id, str(error)[:500])
                failed += 1
            else:
                await self._succeed(event_id, result)
                delivered += 1
        return OutboxRunResult(claimed=len(events), delivered=delivered, failed=failed)

    async def _succeed(self, event_id: str, result: dict[str, object] | None) -> None:
        with SessionLocal.begin() as session:
            event = session.get(OutboxEventRecord, event_id)
            if (
                event is not None
                and event.delivered_at is None
                and event.claimed_by == self.worker_id
            ):
                event.delivered_at = datetime.now(UTC)
                event.last_error = None
                if result:
                    event.payload = {**event.payload, "delivery": result}
                event.claimed_at = None
                event.claimed_by = None

    async def _fail(self, event_id: str, message: str) -> None:
        with SessionLocal.begin() as session:
            event = session.get(OutboxEventRecord, event_id)
            if (
                event is None
                or event.delivered_at is not None
                or event.claimed_by != self.worker_id
            ):
                return
            event.attempts += 1
            event.last_error = message
            delay = min(3600, 2 ** min(event.attempts, 10))
            event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
            event.claimed_at = None
            event.claimed_by = None

    async def run_forever(
        self,
        stop: asyncio.Event,
        poll_seconds: float = 1.0,
        limit: int = 25,
        on_error: Callable[[Exception], Awaitable[None]] | None = None,
    ) -> None:
        while not stop.is_set():
            try:
                await self.process_once(limit=limit)
            except Exception as error:  # noqa: BLE001 - keep worker alive
                if on_error is not None:
                    await on_error(error)
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except TimeoutError:
                continue
