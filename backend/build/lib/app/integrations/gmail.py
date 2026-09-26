from __future__ import annotations

import asyncio
import base64
from email.message import EmailMessage

from app.core.pii import ContactCipher
from app.integrations.google_auth import load_google_service


class GmailNotificationHandler:
    """Sends appointment notifications through Gmail from the internal outbox."""

    def __init__(self, token_path: str, sender: str) -> None:
        self.token_path = token_path
        self.sender = sender
        self.scopes = ["https://www.googleapis.com/auth/gmail.send"]

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        return await asyncio.to_thread(self._handle, payload)

    def _handle(self, payload: dict[str, object]) -> dict[str, object]:
        recipient = str(payload.get("employee_email") or "")
        if not recipient:
            raise ValueError("employee_email is required for Gmail notification")
        service = load_google_service("gmail", "v1", self.token_path, self.scopes)
        contact_email = ""
        ciphertext = payload.get("contact_email_ciphertext")
        if ciphertext:
            try:
                contact_email = ContactCipher().decrypt(str(ciphertext))
            except Exception:  # noqa: BLE001 - do not block delivery on optional contact detail
                contact_email = ""
        contact_phone = ""
        phone_ciphertext = payload.get("contact_phone_ciphertext")
        if phone_ciphertext:
            try:
                contact_phone = ContactCipher().decrypt(str(phone_ciphertext))
            except Exception:  # noqa: BLE001 - do not block delivery on optional contact detail
                contact_phone = ""
        event_type = str(payload.get("event_type", "appointment.booked"))
        if event_type == "appointment.cancelled":
            subject = f"Appointment cancelled {payload['reference']}"
            opening = "Appointment cancelled."
        elif event_type == "appointment.rescheduled":
            subject = f"Appointment rescheduled {payload['reference']}"
            opening = "Appointment rescheduled."
        else:
            subject = f"Appointment confirmed {payload['reference']}"
            opening = "Appointment confirmed."
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = self.sender
        message["Subject"] = subject
        message.set_content(
            f"{opening}\n\n"
            f"Reference: {payload['reference']}\n"
            f"Property: {payload.get('property_id', 'unknown')}\n"
            f"Client: {payload.get('client_name', 'unknown')}\n"
            f"Client contact: {contact_email or 'consented contact on file'}\n"
            f"Client phone: {contact_phone or 'consented contact on file'}\n"
            f"Start: {payload.get('starts_at', 'unknown')}\n"
            f"Employee: {payload.get('employee', 'unknown')}\n"
            f"Requirements: {payload.get('requirements') or 'See consented customer preferences in CRM'}\n"
            f"Meeting notes: {payload.get('meeting_notes') or 'Property viewing appointment'}\n"
        )
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"provider": "gmail", "message_id": result.get("id"), "recipient": recipient}
