from datetime import UTC, datetime

from sqlalchemy import select

from app.domain.models import LeadCreate
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.leads import LeadRepository
from app.repositories.records import LeadRecord, OutboxEventRecord


def test_lead_persists_consented_contact_encrypted_and_emits_redacted_outbox() -> None:
    create_schema_for_local_development()
    lead = LeadRepository().create(
        LeadCreate(
            client_name="Ali Khan",
            contact_email="ali@example.com",
            intent="sell",
            city="Karachi",
            notes="Call 03001234567 about the plot",
            follow_up_at=datetime(2026, 9, 25, 9, 0, tzinfo=UTC),
            consent=True,
        )
    )
    with SessionLocal() as session:
        record = session.get(LeadRecord, str(lead.id))
        event = session.scalar(
            select(OutboxEventRecord).where(OutboxEventRecord.event_type == "lead.created")
        )
    assert record is not None
    assert "ali@example.com" not in record.contact_email_ciphertext
    assert "[phone redacted]" in record.notes_redacted
    assert event is not None
    assert "contact_email" not in event.payload
    assert event.payload["follow_up_at"] == "2026-09-25T09:00:00+00:00"
    Base.metadata.drop_all(bind=engine)
