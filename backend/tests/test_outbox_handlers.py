from __future__ import annotations

import base64

import pytest

from app.core.config import Settings
from app.core.pii import ContactCipher
from app.integrations import calendar as calendar_module
from app.integrations import gmail as gmail_module
from app.integrations.calendar import GoogleCalendarHandler
from app.integrations.gmail import GmailNotificationHandler
from app.workers.handlers import APPOINTMENT_EVENTS, CompositeOutboxHandler, build_outbox_handlers


@pytest.mark.asyncio
async def test_composite_handler_returns_each_delivery() -> None:
    calls: list[str] = []

    async def first(payload: dict[str, object]) -> dict[str, object]:
        calls.append(str(payload["reference"]))
        return {"provider": "calendar"}

    async def second(payload: dict[str, object]) -> dict[str, object]:
        calls.append(str(payload["reference"]))
        return {"provider": "gmail"}

    result = await CompositeOutboxHandler((first, second))({"reference": "AES-1"})
    assert calls == ["AES-1", "AES-1"]
    assert result == {"integrations": [{"provider": "calendar"}, {"provider": "gmail"}]}


def test_google_handlers_are_not_faked_without_oauth_token() -> None:
    config = Settings(google_token_path=None, gmail_sender="agent@example.com")
    assert build_outbox_handlers(config) == {}


def test_google_handlers_cover_all_appointment_events() -> None:
    config = Settings(google_token_path="token.json", gmail_sender="agent@example.com")
    handlers = build_outbox_handlers(config)
    assert set(handlers) == set(APPOINTMENT_EVENTS)


def test_gmail_delivery_includes_client_details_without_raw_outbox_email(monkeypatch) -> None:
    sent: dict[str, object] = {}

    class Messages:
        def send(self, **kwargs):
            sent.update(kwargs)
            return self

        def execute(self):
            return {"id": "gmail-1"}

    class Users:
        def messages(self):
            return Messages()

    class Service:
        def users(self):
            return Users()

    monkeypatch.setattr(gmail_module, "load_google_service", lambda *args, **kwargs: Service())
    encrypted = ContactCipher().encrypt("ali@example.com")
    phone_encrypted = ContactCipher().encrypt("+923001234567")
    result = GmailNotificationHandler("token.json", "agent@example.com")._handle(
        {
            "reference": "AES-1",
            "employee_email": "employee@example.com",
            "client_name": "Ali Khan",
            "contact_email_ciphertext": encrypted,
            "contact_phone_ciphertext": phone_encrypted,
            "event_type": "appointment.rescheduled",
            "property_id": "PROP-001",
            "starts_at": "2026-09-22T10:30:00+00:00",
            "employee": "Ayesha Khan",
        }
    )
    raw = base64.urlsafe_b64decode(str(sent["body"]["raw"]) + "===")
    message = raw.decode("utf-8")
    assert result["message_id"] == "gmail-1"
    assert "Appointment rescheduled AES-1" in message
    assert "Ali Khan" in message
    assert "ali@example.com" in message
    assert "+923001234567" in message


def test_calendar_delivery_contains_client_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Events:
        def list(self, **kwargs):
            return self

        def insert(self, **kwargs):
            captured.update(kwargs)
            return self

        def execute(self):
            if captured:
                return {"id": "event-1"}
            return {"items": []}

    class Service:
        def events(self):
            return Events()

    monkeypatch.setattr(calendar_module, "load_google_service", lambda *args, **kwargs: Service())
    encrypted = ContactCipher().encrypt("ali@example.com")
    phone_encrypted = ContactCipher().encrypt("+923001234567")
    result = GoogleCalendarHandler("token.json")._handle(
        {
            "reference": "AES-1",
            "client_name": "Ali Khan",
            "contact_email_ciphertext": encrypted,
            "contact_phone_ciphertext": phone_encrypted,
            "property_id": "PROP-001",
            "starts_at": "2026-09-22T10:30:00+00:00",
            "employee": "Ayesha Khan",
            "event_type": "appointment.booked",
        }
    )
    body = captured["body"]
    assert result["event_id"] == "event-1"
    assert "Ali Khan" in body["description"]
    assert "ali@example.com" in body["description"]
    assert "+923001234567" in body["description"]


@pytest.mark.asyncio
async def test_instant_whatsapp_booking_handler() -> None:
    from app.workers.handlers import InstantWhatsAppBookingHandler

    cipher = ContactCipher()
    phone_enc = cipher.encrypt("+923001234567")
    handler = InstantWhatsAppBookingHandler(cipher=cipher)

    payload = {
        "reference": "AES-CONFIRM-99",
        "property_id": "PROP-001",
        "employee": "Ayesha Khan",
        "client_name": "Haroon Shahid",
        "contact_phone_ciphertext": phone_enc,
        "starts_at": "2026-09-25T11:00:00+05:00",
    }

    result = await handler(payload)
    assert result["status"] == "delivered"
    assert result["reference"] == "AES-CONFIRM-99"
    assert result["recipient"] == "+923001234567"
    assert "AES-CONFIRM-99" in result["message"]
    assert "PROP-001" in result["message"]
    assert "maps.google.com" in result["message"]
