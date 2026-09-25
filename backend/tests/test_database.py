from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from threading import Barrier, local
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.domain.fixtures import demo_properties
from app.domain.models import AppointmentRequest, AppointmentUpdate
from app.repositories.appointments import SqlAppointmentService
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    AppointmentRecord,
    OutboxEventRecord,
    ToolAuditEventRecord,
    VoiceSessionLeaseRecord,
    VoiceSessionRateLimitRecord,
    VoiceSessionTicketRecord,
)
from app.services.voice_sessions import VoiceSessionConsumeResult, VoiceSessionService


def _future_pk_slot(hour: int = 10) -> datetime:
    zone = ZoneInfo("Asia/Karachi")
    now = datetime.now(zone)
    candidate = datetime.combine(now.date(), time(hour, 0), tzinfo=zone)
    if candidate <= now:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 6:
        candidate += timedelta(days=1)
    return candidate


def test_database_schema_contains_core_records() -> None:
    create_schema_for_local_development()
    assert {"properties", "appointments", "outbox_events"}.issubset(Base.metadata.tables)
    assert "uq_appointments_active_employee_slot" in {
        index.name for index in AppointmentRecord.__table__.indexes
    }
    Base.metadata.drop_all(bind=engine)


def test_sql_property_repository_imports_and_filters() -> None:
    create_schema_for_local_development()
    repository = SqlPropertyRepository()
    repository.import_properties(demo_properties())
    assert repository.get_available("DEMO-001") is not None
    assert all(item.city == "Karachi" for item in repository.list()) is False
    Base.metadata.drop_all(bind=engine)


def test_property_import_persists_source_and_timestamp() -> None:
    create_schema_for_local_development()
    repository = SqlPropertyRepository()
    batch_id = repository.import_properties(
        demo_properties()[:1],
        source="crm-export-v1",
        validation_errors=[{"row": 4, "field": "price_pkr", "message": "invalid"}],
    )
    item = repository.list()[0]
    assert batch_id
    assert item.source == "crm-export-v1"
    assert item.imported_at is not None
    Base.metadata.drop_all(bind=engine)


def test_sql_appointment_is_idempotent_and_writes_outbox() -> None:
    create_schema_for_local_development()
    properties = SqlPropertyRepository()
    properties.import_properties(demo_properties())
    service = SqlAppointmentService(properties)
    request = AppointmentRequest(
        property_id="DEMO-001",
        employee="Ayesha Khan",
        starts_at=_future_pk_slot(),
        client_name="Ali",
        contact_email="ali@example.com",
        contact_phone="+923001234567",
        idempotency_key=uuid4(),
        consent=True,
    )
    first = service.book(request)
    second = service.book(request)
    assert first.reference == second.reference
    assert first.client_name == "Ali"
    assert first.contact_phone == "+923001234567"
    cancelled = service.update(
        AppointmentUpdate(
            reference=first.reference, contact_email="ali@example.com", idempotency_key=uuid4()
        ),
        cancel=True,
    )
    assert cancelled.status == "cancelled"
    with SessionLocal() as session:
        audit_events = session.query(ToolAuditEventRecord).all()
        appointment_record = session.scalar(
            select(AppointmentRecord).where(AppointmentRecord.reference == first.reference)
        )
        outbox_event = session.scalar(
            select(OutboxEventRecord).where(OutboxEventRecord.event_type == "appointment.booked")
        )
    assert {event.status for event in audit_events} >= {"accepted"}
    assert appointment_record is not None and appointment_record.client_name == "Ali"
    assert outbox_event is not None
    assert outbox_event.payload["client_name"] == "Ali"
    assert outbox_event.payload["contact_email_ciphertext"] != "ali@example.com"
    assert outbox_event.payload["contact_phone_ciphertext"] != "+923001234567"
    Base.metadata.drop_all(bind=engine)


def test_sql_appointment_rejects_wrong_employee_and_busy_slot() -> None:
    create_schema_for_local_development()
    properties = SqlPropertyRepository()
    properties.import_properties(demo_properties())
    service = SqlAppointmentService(properties)
    starts_at = _future_pk_slot()
    with pytest.raises(ValueError, match="assigned"):
        service.book(
            AppointmentRequest(
                property_id="DEMO-001",
                employee="Wrong",
                starts_at=starts_at,
                client_name="Ali",
                contact_email="ali@example.com",
                idempotency_key=uuid4(),
                consent=True,
            )
        )
    service.book(
        AppointmentRequest(
            property_id="DEMO-001",
            employee="Ayesha Khan",
            starts_at=starts_at,
            client_name="Ali",
            contact_email="ali@example.com",
            idempotency_key=uuid4(),
            consent=True,
        )
    )
    with pytest.raises(ValueError, match="already booked"):
        service.book(
            AppointmentRequest(
                property_id="DEMO-004",
                employee="Ayesha Khan",
                starts_at=starts_at,
                client_name="Sara",
                contact_email="sara@example.com",
                idempotency_key=uuid4(),
                consent=True,
            )
        )
    Base.metadata.drop_all(bind=engine)


def test_sql_update_idempotency_does_not_duplicate_outbox_event() -> None:
    create_schema_for_local_development()
    properties = SqlPropertyRepository()
    properties.import_properties(demo_properties())
    service = SqlAppointmentService(properties)
    appointment = service.book(
        AppointmentRequest(
            property_id="DEMO-001",
            employee="Ayesha Khan",
            starts_at=_future_pk_slot(),
            client_name="Ali",
            contact_email="ali@example.com",
            idempotency_key=uuid4(),
            consent=True,
        )
    )
    key = uuid4()
    update = AppointmentUpdate(
        reference=appointment.reference, contact_email="ali@example.com", idempotency_key=key
    )
    service.update(update, cancel=True)
    service.update(update, cancel=True)
    with SessionLocal() as session:
        cancelled_events = session.scalars(
            select(OutboxEventRecord).where(OutboxEventRecord.event_type == "appointment.cancelled")
        ).all()
    assert len(cancelled_events) == 1
    Base.metadata.drop_all(bind=engine)


def test_sql_reschedule_validates_slot_and_persists_transition() -> None:
    create_schema_for_local_development()
    properties = SqlPropertyRepository()
    properties.import_properties(demo_properties())
    service = SqlAppointmentService(properties)
    appointment = service.book(
        AppointmentRequest(
            property_id="DEMO-001",
            employee="Ayesha Khan",
            starts_at=_future_pk_slot(),
            client_name="Ali",
            contact_email="ali@example.com",
            idempotency_key=uuid4(),
            consent=True,
        )
    )
    moved = service.update(
        AppointmentUpdate(
            reference=appointment.reference,
            contact_email="ali@example.com",
            starts_at=_future_pk_slot(11),
            idempotency_key=uuid4(),
        )
    )
    assert moved.status == "rescheduled"
    assert moved.starts_at.astimezone(ZoneInfo("Asia/Karachi")).hour == 11
    Base.metadata.drop_all(bind=engine)


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requires PostgreSQL concurrency")
def test_postgres_concurrent_bookings_cannot_claim_same_employee_slot() -> None:
    create_schema_for_local_development()
    importer = SqlPropertyRepository()
    importer.import_properties(demo_properties())

    barrier = Barrier(2)
    thread_state = local()

    class RacingProperties(SqlPropertyRepository):
        def get_available(self, property_id: str):
            result = super().get_available(property_id)
            if not getattr(thread_state, "checked_availability", False):
                thread_state.checked_availability = True
                barrier.wait(timeout=10)
            return result

    service = SqlAppointmentService(RacingProperties())
    starts_at = datetime(2026, 9, 28, 10, 0, tzinfo=UTC)

    def attempt(property_id: str, client_name: str):
        request = AppointmentRequest(
            property_id=property_id,
            employee="Ayesha Khan",
            starts_at=starts_at,
            client_name=client_name,
            contact_email=f"{client_name.casefold()}@example.com",
            idempotency_key=uuid4(),
            consent=True,
        )
        try:
            return service.book(request)
        except ValueError:
            return None

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda arguments: attempt(*arguments),
                    [("DEMO-001", "Ali"), ("DEMO-004", "Sara")],
                )
            )

        assert sum(result is not None for result in results) == 1
        with SessionLocal() as session:
            appointments = session.scalars(
                select(AppointmentRecord).where(
                    AppointmentRecord.employee == "Ayesha Khan",
                    AppointmentRecord.starts_at == starts_at,
                )
            ).all()
            booking_events = session.scalars(
                select(OutboxEventRecord).where(
                    OutboxEventRecord.event_type == "appointment.booked"
                )
            ).all()
        assert len(appointments) == 1
        assert len(booking_events) == 1
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requires PostgreSQL concurrency")
def test_postgres_concurrent_voice_ticket_issuance_obeys_shared_limit() -> None:
    create_schema_for_local_development()
    service = VoiceSessionService(
        "postgres-voice-session-test-key-0000000000000000",
        issue_limit=1,
    )
    barrier = Barrier(2)

    def attempt() -> tuple[str, datetime] | None:
        barrier.wait(timeout=10)
        return service.issue("198.51.100.8", "https://voice.example.com")

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))

        assert sum(result is not None for result in results) == 1
        with SessionLocal() as session:
            tickets = session.scalars(select(VoiceSessionTicketRecord)).all()
            limits = session.scalars(select(VoiceSessionRateLimitRecord)).all()
        assert len(tickets) == 1
        assert len(limits) == 1
        assert limits[0].request_count == 2
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requires PostgreSQL concurrency")
def test_postgres_concurrent_voice_call_reservation_obeys_global_limit() -> None:
    create_schema_for_local_development()
    service = VoiceSessionService(
        "postgres-active-session-test-key-0000000000000000",
        max_active_total=1,
    )
    tickets = [
        service.issue(address, "https://voice.example.com")
        for address in ("198.51.100.21", "198.51.100.22")
    ]
    assert all(ticket is not None for ticket in tickets)
    barrier = Barrier(2)

    def consume(index: int) -> VoiceSessionConsumeResult:
        barrier.wait(timeout=10)
        assert tickets[index] is not None
        return service.consume(
            tickets[index][0],
            ("198.51.100.21", "198.51.100.22")[index],
            "https://voice.example.com",
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(consume, range(2)))

        assert sorted(result.value for result in results) == ["accepted", "capacity"]
        with SessionLocal() as session:
            leases = session.scalars(select(VoiceSessionLeaseRecord)).all()
        assert len(leases) == 1
        accepted = tickets[results.index(VoiceSessionConsumeResult.ACCEPTED)]
        assert accepted is not None
        service.release(accepted[0])
    finally:
        Base.metadata.drop_all(bind=engine)
