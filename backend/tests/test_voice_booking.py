from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domain.fixtures import demo_properties
from app.domain.models import AgentDecision, AppointmentContactContext, AppointmentRequest
from app.repositories.appointments import SqlAppointmentService
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, engine
from app.repositories.properties import SqlPropertyRepository
from app.services.voice_booking import VoiceBookingFlow


def _setup() -> tuple[SqlPropertyRepository, SqlAppointmentService]:
    Base.metadata.drop_all(bind=engine)
    create_schema_for_local_development()
    properties = SqlPropertyRepository()
    properties.import_properties(demo_properties())
    return properties, SqlAppointmentService(properties)


def _teardown() -> None:
    Base.metadata.drop_all(bind=engine)


def test_voice_booking_requires_consent_slot_choice_and_explicit_confirmation() -> None:
    properties, appointments = _setup()
    try:
        flow = VoiceBookingFlow(properties, appointments)
        contact = AppointmentContactContext(
            client_name="Ali Khan", contact_email="ali@example.com", consent=True
        )
        decision = AgentDecision(kind="book", spoken_text="book")
        started = flow.handle("book visit", decision, ["PROP-001"], contact, "conversation-a")
        assert started is not None and "verified available times" in started.decision.spoken_text
        assert flow.phase == "slots"

        selected = flow.handle("second", decision, ["PROP-001"], contact, "conversation-a")
        assert selected is not None and flow.phase == "confirm"
        assert selected.appointment is None

        declined = flow.handle("maybe later", decision, ["PROP-001"], contact, "conversation-a")
        assert declined is not None and "clear confirmation" in declined.decision.spoken_text
        assert flow.phase == "confirm"

        confirmed = flow.handle("haan", decision, ["PROP-001"], contact, "conversation-a")
        assert confirmed is not None and confirmed.appointment is not None
        assert confirmed.appointment["status"] == "test_booked"
        assert "test visit" in confirmed.decision.spoken_text
        assert flow.phase == "idle"
    finally:
        _teardown()


def test_voice_booking_cannot_book_without_session_contact_or_verified_property() -> None:
    properties, appointments = _setup()
    try:
        flow = VoiceBookingFlow(properties, appointments)
        decision = AgentDecision(kind="book", spoken_text="book")
        missing_contact = flow.handle("book visit", decision, ["PROP-001"], None, "conversation-b")
        assert (
            missing_contact is not None
            and "consented email" in missing_contact.decision.spoken_text
        )
        assert flow.phase == "contact"

        no_inventory = VoiceBookingFlow(properties, appointments).handle(
            "book visit", decision, ["PROP-003"], None, "conversation-c"
        )
        assert no_inventory is not None
        assert "verified available property" in no_inventory.decision.spoken_text
    finally:
        _teardown()


def test_voice_booking_confirmation_uses_existing_idempotent_service() -> None:
    properties, appointments = _setup()
    try:
        flow = VoiceBookingFlow(properties, appointments)
        fixed_slot = appointments.available_slots("PROP-001")[0]
        appointments.available_slots = lambda property_id: [fixed_slot]  # type: ignore[method-assign]
        contact = AppointmentContactContext(
            client_name="Sara Khan", contact_email="sara@example.com", consent=True
        )
        decision = AgentDecision(kind="book", spoken_text="book")
        flow.handle("book visit", decision, ["PROP-001"], contact, "conversation-d")
        flow.handle("1", decision, ["PROP-001"], contact, "conversation-d")
        first = flow.handle("yes", decision, ["PROP-001"], contact, "conversation-d")
        assert first is not None and first.appointment is not None
        assert first.appointment["reference"].startswith("AES-")

        # Replaying the same voice session and confirmed slot maps to the same
        # server-generated idempotency key, so retries cannot make a duplicate.
        flow.handle("book visit", decision, ["PROP-001"], contact, "conversation-d")
        flow.handle("1", decision, ["PROP-001"], contact, "conversation-d")
        second = flow.handle("yes", decision, ["PROP-001"], contact, "conversation-d")
        assert second is not None and second.appointment is not None
        assert second.appointment["reference"] == first.appointment["reference"]
    finally:
        _teardown()


def test_slot_lookup_returns_pk_time_and_skips_existing_employee_booking() -> None:
    _, appointments = _setup()
    try:
        tomorrow_pkt = datetime.now(ZoneInfo("Asia/Karachi")).date() + timedelta(days=1)
        before_work = datetime.combine(tomorrow_pkt, time(9), tzinfo=ZoneInfo("Asia/Karachi"))
        first = appointments.available_slots("PROP-001", from_time=before_work)
        assert first
        assert first[0].hour == 10 and first[0].minute == 0
        assert first[0].weekday() < 6

        appointments.book(
            AppointmentRequest(
                property_id="PROP-001",
                employee="Ayesha Khan",
                starts_at=first[0],
                client_name="Noor Ali",
                contact_email="noor@example.com",
                idempotency_key=uuid4(),
                consent=True,
            )
        )
        refreshed = appointments.available_slots("PROP-001", from_time=before_work)
        assert refreshed
        assert refreshed[0] != first[0]
        assert refreshed[0].hour == 10 and refreshed[0].minute == 30
        assert appointments.available_slots("PROP-003", from_time=before_work) == []
    finally:
        _teardown()


def test_booking_service_rejects_stale_but_otherwise_valid_slot() -> None:
    _, appointments = _setup()
    try:
        stale_slot = datetime.now(ZoneInfo("Asia/Karachi")).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        while stale_slot.weekday() >= 6:
            stale_slot -= timedelta(days=1)
        with pytest.raises(ValueError, match="Visits are available"):
            appointments.book(
                AppointmentRequest(
                    property_id="PROP-001",
                    employee="Ayesha Khan",
                    starts_at=stale_slot,
                    client_name="Ali Khan",
                    contact_email="ali@example.com",
                    idempotency_key=uuid4(),
                    consent=True,
                )
            )
    finally:
        _teardown()


def test_voice_booking_resolves_property_by_area_and_colloquial_confirmation() -> None:
    properties, appointments = _setup()
    try:
        flow = VoiceBookingFlow(properties, appointments)
        contact = AppointmentContactContext(
            client_name="Farhan Ali", contact_email="farhan@example.com", consent=True
        )
        decision = AgentDecision(kind="book", spoken_text="book")

        # When 2 properties are candidates, flow enters 'property' phase
        started = flow.handle("book visit", decision, ["PROP-001", "PROP-002"], contact, "conv-natural")
        assert started is not None
        assert flow.phase == "property"

        # User refers to property by area: 'Clifton wala'
        selected = flow.handle("Clifton wala", decision, ["PROP-001", "PROP-002"], contact, "conv-natural")
        assert selected is not None
        assert flow.phase == "slots"
        assert flow.property_id == "PROP-002"

        # User selects slot using colloquial Urdu ordinal: 'pehla wala'
        slot_chosen = flow.handle("pehla wala option", decision, ["PROP-001", "PROP-002"], contact, "conv-natural")
        assert slot_chosen is not None
        assert flow.phase == "confirm"

        # User confirms using natural Urdu phrase: 'ji haan bilkul'
        confirmed = flow.handle("ji haan bilkul", decision, ["PROP-001", "PROP-002"], contact, "conv-natural")
        assert confirmed is not None and confirmed.appointment is not None
        assert confirmed.appointment["status"] == "test_booked"
        assert flow.phase == "idle"
    finally:
        _teardown()

