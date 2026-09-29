from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain.models import (
    Appointment,
    AppointmentRequest,
    AppointmentUpdate,
    Property,
    PropertyQuery,
)


class PropertyRepository:
    def __init__(self, properties: Iterable[Property] = ()) -> None:
        """Build an in-memory repository from explicitly supplied records.

        Empty by default so a newly constructed repository cannot accidentally
        expose evaluation fixtures as live inventory.
        """
        self._properties = {item.id: item for item in properties}

    def list(self, query: PropertyQuery | None = None) -> list[Property]:
        values = list(self._properties.values())
        if not query:
            return values
        return [
            p
            for p in values
            if (not query.city or p.city.lower() == query.city.lower())
            and (not query.area or query.area.lower() in p.area.lower())
            and (not query.purpose or p.purpose == query.purpose)
            and (not query.max_budget_pkr or p.price_pkr <= query.max_budget_pkr)
            and (query.bedrooms is None or p.bedrooms >= query.bedrooms)
            and (
                not query.amenities
                or {item.lower() for item in query.amenities}.issubset(
                    {item.lower() for item in p.amenities}
                )
            )
            and (
                not query.investment_goal
                or any(query.investment_goal.lower() in item.lower() for item in p.investment_goals)
            )
        ]

    def get_available(self, property_id: str) -> Property | None:
        item = self._properties.get(property_id)
        return item if item and item.available else None

    def import_properties(self, values: list[Property]) -> None:
        self._properties.update({item.id: item for item in values})


class AppointmentService:
    def __init__(self, properties: PropertyRepository) -> None:
        self.properties = properties
        self._appointments: dict[str, Appointment] = {}
        self._idempotency: dict[UUID, Appointment] = {}

    @staticmethod
    def _valid_slot(starts_at: datetime) -> bool:
        local = (
            starts_at.astimezone(ZoneInfo("Asia/Karachi")).replace(tzinfo=None)
            if starts_at.tzinfo
            else starts_at
        )
        return (
            local.weekday() < 6
            and time(10, 0) <= local.time() < time(18, 0)
            and local.minute in (0, 30)
        )

    def book(self, request: AppointmentRequest) -> Appointment:
        if request.idempotency_key in self._idempotency:
            return self._idempotency[request.idempotency_key]
        property_item = self.properties.get_available(request.property_id)
        if not property_item:
            raise ValueError("Property is unavailable; the visit cannot be booked")
        if not self._valid_slot(request.starts_at):
            raise ValueError(
                "Visits are available Monday-Saturday, 10:00-18:00 PKT in 30-minute slots"
            )
        reference = f"AES-{len(self._appointments) + 1001}"
        result = Appointment(
            reference=reference,
            property_id=request.property_id,
            employee=request.employee,
            starts_at=request.starts_at,
            client_name=request.client_name,
            employee_email=request.employee_email,
            contact_email=request.contact_email,
        )
        self._appointments[reference] = result
        self._idempotency[request.idempotency_key] = result
        return result

    def update(self, update: AppointmentUpdate, cancel: bool = False) -> Appointment:
        appointment = self._appointments.get(update.reference)
        if (
            not appointment
            or str(appointment.contact_email).lower() != str(update.contact_email).lower()
        ):
            raise ValueError("Appointment reference and contact email do not match")
        if cancel:
            appointment.status = "cancelled"
        else:
            if update.starts_at is None or not self._valid_slot(update.starts_at):
                raise ValueError("Provide an eligible new appointment slot")
            appointment.starts_at, appointment.status = update.starts_at, "rescheduled"
        return appointment


def redact_for_retention(text: str) -> str:
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email redacted]", text)
    return re.sub(r"\b(?:\+92|0)3\d{9}\b", "[phone redacted]", text)
