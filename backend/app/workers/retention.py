"""Remove expired inquiry, completed-viewing and delivered-notification contacts."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from app.repositories.database import SessionLocal
from app.repositories.records import AppointmentRecord, OutboxEventRecord, WebsiteInquiryRecord

INQUIRY_RETENTION = timedelta(days=365)
DELIVERED_PAYLOAD_RETENTION = timedelta(days=30)
_CONTACT_PAYLOAD_FIELDS = {
    "client_name",
    "contact_email",
    "contact_phone",
    "contact_email_ciphertext",
    "contact_phone_ciphertext",
    "email",
    "phone",
    "name",
    "unsubscribe_token",
}


def purge_expired_customer_data(now: datetime | None = None) -> dict[str, int]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    payload_cutoff = current - DELIVERED_PAYLOAD_RETENTION
    counts = {"inquiry_contacts": 0, "viewing_contacts": 0, "delivered_payloads": 0}

    with SessionLocal.begin() as session:
        inquiries = session.scalars(
            select(WebsiteInquiryRecord)
            .where(
                WebsiteInquiryRecord.expires_at <= current,
                or_(
                    WebsiteInquiryRecord.client_name_ciphertext != "",
                    WebsiteInquiryRecord.contact_email_ciphertext.is_not(None),
                    WebsiteInquiryRecord.contact_phone_ciphertext.is_not(None),
                ),
            )
            .limit(500)
        ).all()
        for inquiry in inquiries:
            inquiry.client_name_ciphertext = ""
            inquiry.contact_email_ciphertext = None
            inquiry.contact_phone_ciphertext = None
            inquiry.message_redacted = ""
            counts["inquiry_contacts"] += 1

        appointments = session.scalars(
            select(AppointmentRecord)
            .where(
                AppointmentRecord.status.in_(("cancelled", "completed")),
                AppointmentRecord.closed_at.is_not(None),
                AppointmentRecord.closed_at <= current - INQUIRY_RETENTION,
                or_(
                    AppointmentRecord.client_name != "",
                    AppointmentRecord.contact_email_ciphertext != "",
                    AppointmentRecord.contact_phone_ciphertext.is_not(None),
                ),
            )
            .limit(500)
        ).all()
        for appointment in appointments:
            appointment.client_name = ""
            appointment.contact_email_ciphertext = ""
            appointment.contact_phone_ciphertext = None
            counts["viewing_contacts"] += 1

        delivered_events = session.scalars(
            select(OutboxEventRecord)
            .where(
                OutboxEventRecord.delivered_at.is_not(None),
                OutboxEventRecord.delivered_at <= payload_cutoff,
            )
            .limit(500)
        ).all()
        for event in delivered_events:
            payload = dict(event.payload or {})
            remaining = {
                key: value for key, value in payload.items() if key not in _CONTACT_PAYLOAD_FIELDS
            }
            if len(remaining) != len(payload):
                event.payload = remaining
                counts["delivered_payloads"] += 1

    return counts
