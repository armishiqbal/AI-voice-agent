from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.fixtures import demo_properties
from app.domain.models import AppointmentRequest, AppointmentUpdate
from app.repositories.appointments import SqlAppointmentService
from app.repositories.database import Base
from app.repositories.properties import SqlPropertyRepository


def run_appointment_evaluation() -> dict[str, object]:
    """Exercise appointment invariants against an isolated SQL database."""

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    properties = SqlPropertyRepository(session_factory)
    properties.import_properties(demo_properties())
    service = SqlAppointmentService(properties, session_factory)
    slot_date = datetime.now(ZoneInfo("Asia/Karachi")).date() + timedelta(days=2)
    while slot_date.weekday() >= 6:
        slot_date += timedelta(days=1)
    valid_slot = datetime.combine(slot_date, time(10, 0), tzinfo=ZoneInfo("Asia/Karachi"))
    results: list[dict[str, object]] = []

    def check(
        case_id: str, expected_success: bool, operation: Callable[[], object]
    ) -> object | None:
        try:
            value = operation()
        except ValueError as error:
            results.append(
                {
                    "id": case_id,
                    "passed": not expected_success,
                    "outcome": "rejected",
                    "error": str(error),
                }
            )
            return None
        results.append({"id": case_id, "passed": expected_success, "outcome": "accepted"})
        return value

    request = AppointmentRequest(
        property_id="DEMO-001",
        employee="Ayesha Khan",
        starts_at=valid_slot,
        client_name="Ali Khan",
        contact_email="ali@example.com",
        idempotency_key=uuid4(),
        consent=True,
    )
    first = check("book-valid", True, lambda: service.book(request))
    replay = check("book-idempotent-replay", True, lambda: service.book(request))
    if first is not None and replay is not None:
        results[-1]["passed"] = first.reference == replay.reference
        results[-1]["same_reference"] = first.reference == replay.reference

    check(
        "book-unavailable",
        False,
        lambda: service.book(
            request.model_copy(update={"property_id": "DEMO-003", "idempotency_key": uuid4()})
        ),
    )
    check(
        "book-wrong-employee",
        False,
        lambda: service.book(
            request.model_copy(update={"employee": "Wrong Employee", "idempotency_key": uuid4()})
        ),
    )
    check(
        "book-invalid-slot",
        False,
        lambda: service.book(
            request.model_copy(
                update={"starts_at": valid_slot.replace(minute=15), "idempotency_key": uuid4()}
            )
        ),
    )
    check(
        "book-busy-slot",
        False,
        lambda: service.book(
            request.model_copy(update={"property_id": "DEMO-004", "idempotency_key": uuid4()})
        ),
    )

    if first is not None:
        moved = check(
            "reschedule-valid",
            True,
            lambda: service.update(
                AppointmentUpdate(
                    reference=first.reference,
                    contact_email="ali@example.com",
                    starts_at=valid_slot.replace(hour=11),
                    idempotency_key=uuid4(),
                )
            ),
        )
        if moved is not None:
            check(
                "reschedule-wrong-email",
                False,
                lambda: service.update(
                    AppointmentUpdate(
                        reference=first.reference,
                        contact_email="wrong@example.com",
                        starts_at=valid_slot.replace(hour=12),
                        idempotency_key=uuid4(),
                    )
                ),
            )
            check(
                "cancel-valid",
                True,
                lambda: service.update(
                    AppointmentUpdate(
                        reference=first.reference,
                        contact_email="ali@example.com",
                        idempotency_key=uuid4(),
                    ),
                    cancel=True,
                ),
            )

    passed = sum(1 for result in results if result["passed"])
    return {
        "mode": "sql-isolated-fixtures",
        "total": len(results),
        "passed": passed,
        "accuracy": round(passed / len(results), 4) if results else 0.0,
        "results": results,
    }
