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


def test_calendar_retry_updates_the_event_for_its_reference_and_keeps_pk_time(monkeypatch) -> None:
    events_by_id: dict[str, dict[str, object]] = {}
    inserts: list[dict[str, object]] = []
    updates: list[str] = []

    class Request:
        def __init__(self, action):
            self.action = action

        def execute(self):
            return self.action()

    class Events:
        def list(self, **kwargs):
            reference_filter = kwargs["privateExtendedProperty"]
            reference = reference_filter.split("=", maxsplit=1)[1]
            return Request(
                lambda: {
                    "items": [
                        event
                        for event in events_by_id.values()
                        if event["extendedProperties"]["private"]["appointment_reference"]
                        == reference
                    ]
                }
            )

        def insert(self, *, calendarId, body, sendUpdates):
            del calendarId, sendUpdates
            inserts.append(body)

            def create_event():
                event = {"id": "event-1", **body}
                events_by_id[event["id"]] = event
                return event

            return Request(create_event)

        def update(self, *, calendarId, eventId, body, sendUpdates):
            del calendarId, sendUpdates
            updates.append(eventId)

            def update_event():
                event = {"id": eventId, **body}
                events_by_id[eventId] = event
                return event

            return Request(update_event)

    class Service:
        def events(self):
            return Events()

    monkeypatch.setattr(calendar_module, "load_google_service", lambda *args, **kwargs: Service())
    payload = {
        "reference": "AES-IDEMPOTENT",
        "property_id": "OWNER-PROPERTY-1",
        "starts_at": "2026-09-28T06:00:00+00:00",
        "event_type": "appointment.booked",
    }
    handler = GoogleCalendarHandler("token.json")

    first = handler._handle(payload)
    replay = handler._handle(payload)

    assert first["event_id"] == replay["event_id"] == "event-1"
    assert len(inserts) == 1
    assert updates == ["event-1"]
    assert events_by_id["event-1"]["start"] == {
        "dateTime": "2026-09-28T11:00:00+05:00",
        "timeZone": "Asia/Karachi",
    }


def test_internal_handlers_do_not_claim_fake_whatsapp_delivery() -> None:
    from app.workers.handlers import build_internal_handlers

    assert "appointment.whatsapp_confirmation" not in build_internal_handlers()


@pytest.mark.asyncio
async def test_delivery_graph_executes_real_tools_and_records_transitions(caplog) -> None:
    import logging

    calls: list[str] = []

    class Calendar:
        async def __call__(self, payload):
            calls.append("calendar")
            return {"provider": "google_calendar"}

    class Email:
        async def __call__(self, payload):
            assert payload["_delivery_receipts"]["0:Calendar"]["provider"] == "google_calendar"
            calls.append("email")
            return {"provider": "gmail"}

    class CRM:
        async def __call__(self, payload):
            assert "1:Email" in payload["_delivery_receipts"]
            calls.append("crm")
            return {"provider": "n8n"}

    handler = CompositeOutboxHandler((Calendar(), Email(), CRM()))
    assert {"deliver_0_Calendar", "deliver_1_Email", "deliver_2_CRM"}.issubset(
        handler.graph.get_graph().nodes
    )
    with caplog.at_level(logging.INFO, logger="awaaz.delivery_graph"):
        result = await handler({"reference": "PRIVATE-REFERENCE"})
    assert calls == ["calendar", "email", "crm"]
    assert len(result["integrations"]) == 3
    assert "node=deliver_1_Email status=delivered" in caplog.text
    assert "PRIVATE-REFERENCE" not in caplog.text


@pytest.mark.asyncio
async def test_empty_delivery_graph_preserves_empty_result() -> None:
    assert await CompositeOutboxHandler(())({}) == {"integrations": []}
