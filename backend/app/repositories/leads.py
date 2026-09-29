from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.pii import ContactCipher
from app.domain.models import Lead, LeadCreate
from app.repositories.database import SessionLocal
from app.repositories.records import LeadRecord, OutboxEventRecord, ToolAuditEventRecord
from app.services.appointments import redact_for_retention


class LeadRepository:
    """Stores consented lead data and emits a CRM-ready internal event."""

    def __init__(self) -> None:
        self.cipher = ContactCipher()

    def create(self, request: LeadCreate) -> Lead:
        lead_id = str(uuid4())
        redacted_notes = redact_for_retention(request.notes)
        with SessionLocal.begin() as session:
            record = LeadRecord(
                id=lead_id,
                client_name=request.client_name,
                contact_email_ciphertext=self.cipher.encrypt(str(request.contact_email)),
                intent=request.intent,
                city=request.city,
                area=request.area,
                budget_pkr=request.budget_pkr,
                notes_redacted=redacted_notes,
                follow_up_at=request.follow_up_at,
                status="new",
            )
            session.add(record)
            session.add(
                OutboxEventRecord(
                    id=str(uuid4()),
                    event_type="lead.created",
                    payload={
                        "lead_id": lead_id,
                        "client_name": request.client_name,
                        "intent": request.intent,
                        "city": request.city,
                        "area": request.area,
                        "budget_pkr": request.budget_pkr,
                        "notes": redacted_notes,
                        "follow_up_at": request.follow_up_at.isoformat()
                        if request.follow_up_at
                        else None,
                    },
                )
            )
            session.add(
                ToolAuditEventRecord(
                    id=str(uuid4()),
                    action="lead.create",
                    status="accepted",
                    reference=lead_id,
                    payload={"intent": request.intent, "city": request.city, "area": request.area},
                )
            )
            session.flush()
            return Lead(
                id=UUID(lead_id),
                client_name=record.client_name,
                contact_email=request.contact_email,
                intent=record.intent,
                city=record.city,
                area=record.area,
                budget_pkr=record.budget_pkr,
                notes=record.notes_redacted,
                follow_up_at=record.follow_up_at,
                status=record.status,
            )

    @staticmethod
    def list_due_followups(now: datetime | None = None, limit: int = 100) -> list[dict[str, object]]:
        current_time = now or datetime.now(UTC)
        with SessionLocal() as session:
            records = session.scalars(
                select(LeadRecord)
                .where(
                    LeadRecord.status == "new",
                    LeadRecord.follow_up_at.is_not(None),
                    LeadRecord.follow_up_at <= current_time,
                )
                .order_by(LeadRecord.follow_up_at, LeadRecord.id)
                .limit(limit)
            ).all()
            return [
                {
                    "lead_id": record.id,
                    "intent": record.intent,
                    "city": record.city,
                    "area": record.area,
                    "budget_pkr": record.budget_pkr,
                    "follow_up_at": record.follow_up_at.isoformat()
                    if record.follow_up_at
                    else None,
                }
                for record in records
            ]

    @staticmethod
    def complete_due_followup(lead_id: str, now: datetime | None = None) -> dict[str, str]:
        current_time = now or datetime.now(UTC)
        with SessionLocal.begin() as session:
            record = session.scalar(
                select(LeadRecord).where(LeadRecord.id == lead_id).with_for_update()
            )
            if record is None:
                raise LookupError("Lead was not found")
            if record.status == "contacted":
                return {"lead_id": lead_id, "status": "contacted"}
            if record.status != "new" or record.follow_up_at is None:
                raise ValueError("Lead has no open follow-up reminder")
            scheduled_at = record.follow_up_at
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=UTC)
            if scheduled_at > current_time:
                raise ValueError("Follow-up reminder is not due yet")
            record.status = "contacted"
            session.add(
                ToolAuditEventRecord(
                    id=str(uuid4()),
                    action="lead.follow_up_completed",
                    status="accepted",
                    reference=lead_id,
                    payload={"intent": record.intent, "city": record.city, "area": record.area},
                )
            )
            return {"lead_id": lead_id, "status": "contacted"}
