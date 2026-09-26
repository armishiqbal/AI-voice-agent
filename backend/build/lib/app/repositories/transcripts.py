from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete

from app.repositories.database import SessionLocal
from app.repositories.records import ConversationTranscriptRecord
from app.services.appointments import redact_for_retention


class TranscriptStore:
    """Stores only redacted text and gives every turn a fixed 30-day expiry."""

    retention_days = 30

    def append(self, conversation_id: str, role: str, text: str) -> None:
        now = datetime.now(UTC)
        with SessionLocal.begin() as session:
            session.execute(
                delete(ConversationTranscriptRecord).where(
                    ConversationTranscriptRecord.expires_at <= now
                )
            )
            session.add(
                ConversationTranscriptRecord(
                    id=str(uuid4()),
                    conversation_id=conversation_id,
                    role=role,
                    text_redacted=redact_for_retention(text),
                    created_at=now,
                    expires_at=now + timedelta(days=self.retention_days),
                )
            )

    def purge_expired(self) -> int:
        now = datetime.now(UTC)
        with SessionLocal.begin() as session:
            result = session.execute(
                delete(ConversationTranscriptRecord).where(
                    ConversationTranscriptRecord.expires_at <= now
                )
            )
            return int(result.rowcount or 0)
