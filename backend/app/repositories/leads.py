from __future__ import annotations

from uuid import UUID, uuid4

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
