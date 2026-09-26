from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.pii import ContactCipher
from app.integrations.google_auth import load_google_service


class GoogleCalendarHandler:
    """Idempotent Calendar event handler for internal outbox events."""

    def __init__(self, token_path: str, calendar_id: str = "primary") -> None:
        self.token_path = token_path
        self.calendar_id = calendar_id
        self.scopes = ["https://www.googleapis.com/auth/calendar.events"]

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        return await asyncio.to_thread(self._handle, payload)

    def _handle(self, payload: dict[str, object]) -> dict[str, object]:
        service = load_google_service("calendar", "v3", self.token_path, self.scopes)
        reference = str(payload["reference"])
        starts_at = datetime.fromisoformat(str(payload["starts_at"])).astimezone(
            ZoneInfo("Asia/Karachi")
        )
        ends_at = starts_at + timedelta(minutes=30)
        contact_email = ""
        ciphertext = payload.get("contact_email_ciphertext")
        if ciphertext:
            try:
                contact_email = ContactCipher().decrypt(str(ciphertext))
            except Exception:  # noqa: BLE001 - optional detail must not break calendar sync
                contact_email = ""
        contact_phone = ""
        phone_ciphertext = payload.get("contact_phone_ciphertext")
        if phone_ciphertext:
            try:
                contact_phone = ContactCipher().decrypt(str(phone_ciphertext))
            except Exception:  # noqa: BLE001 - optional detail must not break calendar sync
                contact_phone = ""
        existing = self._find(service, reference)
        event_type = str(payload.get("event_type", "appointment.booked"))
        if event_type == "appointment.cancelled":
            if existing:
                service.events().delete(
                    calendarId=self.calendar_id, eventId=existing["id"]
                ).execute()
            return {"provider": "google_calendar", "reference": reference, "status": "cancelled"}
        body = {
            "summary": f"Property visit {reference}",
            "description": (
                f"Awaaz Estate appointment for {reference}.\n"
                f"Client: {payload.get('client_name', 'unknown')}\n"
                f"Client contact: {contact_email or 'consented contact on file'}\n"
                f"Client phone: {contact_phone or 'consented contact on file'}\n"
                f"Assigned employee: {payload.get('employee', 'assigned employee')}\n"
                f"Property: {payload.get('property_id', 'unknown')}\n"
                f"Meeting notes: {payload.get('meeting_notes') or 'Property viewing appointment'}\n"
                f"Requirements: {payload.get('requirements') or 'See consented customer preferences in CRM'}"
            ),
            "start": {"dateTime": starts_at.isoformat(), "timeZone": "Asia/Karachi"},
            "end": {"dateTime": ends_at.isoformat(), "timeZone": "Asia/Karachi"},
            "extendedProperties": {"private": {"appointment_reference": reference}},
        }
        employee_email = payload.get("employee_email")
        if employee_email:
            body["attendees"] = [{"email": str(employee_email)}]
        if existing:
            event = (
                service.events()
                .update(
                    calendarId=self.calendar_id,
                    eventId=existing["id"],
                    body=body,
                    sendUpdates="all",
                )
                .execute()
            )
        else:
            event = (
                service.events()
                .insert(calendarId=self.calendar_id, body=body, sendUpdates="all")
                .execute()
            )
        return {"provider": "google_calendar", "event_id": event.get("id"), "reference": reference}

    def _find(self, service: object, reference: str) -> dict[str, object] | None:
        response = (
            service.events()
            .list(
                calendarId=self.calendar_id,
                privateExtendedProperty=f"appointment_reference={reference}",
                singleEvents=True,
            )
            .execute()
        )
        events = response.get("items", [])
        return events[0] if events else None
