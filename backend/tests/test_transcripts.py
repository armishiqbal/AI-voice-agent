from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.records import ConversationTranscriptRecord
from app.repositories.transcripts import TranscriptStore


def test_transcript_store_redacts_and_sets_thirty_day_expiry() -> None:
    create_schema_for_local_development()
    store = TranscriptStore()
    store.append("conversation-1", "user", "email ali@example.com phone 03001234567")
    with SessionLocal() as session:
        record = session.scalar(select(ConversationTranscriptRecord))
    assert record is not None
    assert "ali@example.com" not in record.text_redacted
    assert "[email redacted]" in record.text_redacted
    assert record.expires_at - record.created_at == timedelta(days=30)
    Base.metadata.drop_all(bind=engine)


def test_transcript_store_purges_expired_records() -> None:
    create_schema_for_local_development()
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        session.add(
            ConversationTranscriptRecord(
                id="expired",
                conversation_id="c",
                role="user",
                text_redacted="old",
                created_at=now - timedelta(days=31),
                expires_at=now - timedelta(days=1),
            )
        )
    assert TranscriptStore().purge_expired() == 1
    Base.metadata.drop_all(bind=engine)
