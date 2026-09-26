from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.pii import ContactCipher
from app.domain.models import Appointment, AppointmentRequest, AppointmentUpdate
from app.repositories.database import SessionLocal
from app.repositories.properties import SqlPropertyRepository
from app.repositories.records import (
    AppointmentActionRecord,
    AppointmentRecord,
    OutboxEventRecord,
    ToolAuditEventRecord,
)
from app.services.appointments import redact_for_retention


class SqlAppointmentService:
    def __init__(self, properties: SqlPropertyRepository, session_factory=SessionLocal) -> None:
        self.properties = properties
        self.session_factory = session_factory
        self.cipher = ContactCipher()

    @staticmethod
    def _employee_email(request: AppointmentRequest) -> str | None:
        directory = {
            name.casefold(): str(email) for name, email in settings.employee_email_directory.items()
        }
        if directory:
            recipient = directory.get(request.employee.casefold())
            if not recipient:
                raise ValueError("Assigned employee has no configured notification address")
            return recipient
        # Legacy API callers may supply an address locally; voice bookings resolve
        # from the operator-managed directory when Gmail is enabled.
        if settings.gmail_sender:
            raise ValueError("Configure EMPLOYEE_EMAIL_DIRECTORY before enabling booking emails")
        return str(request.employee_email) if request.employee_email else None

    @staticmethod
    def _valid_slot(value: datetime) -> bool:
        local_aware = (
            value.astimezone(ZoneInfo("Asia/Karachi"))
            if value.tzinfo
            else value.replace(tzinfo=ZoneInfo("Asia/Karachi"))
        )
        local = local_aware.replace(tzinfo=None)
        return (
            local_aware.astimezone(UTC) > datetime.now(UTC)
            and local.weekday() < 6
            and time(10, 0) <= local.time() < time(18, 0)
            and local.minute in (0, 30)
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Asia/Karachi"))
        return value.astimezone(UTC)

    def available_slots(
        self,
        property_id: str,
        *,
        from_time: datetime | None = None,
        horizon_days: int = 7,
        limit: int = 3,
    ) -> list[datetime]:
        """Return the first free employee slots from SQL within PKT business hours."""
        if not 1 <= horizon_days <= 31 or not 1 <= limit <= 10:
            raise ValueError("Slot search bounds are invalid")
        property_item = self.properties.get_available(property_id)
        if property_item is None:
            return []
        now = from_time or datetime.now(UTC)
        now_local = (
            now.astimezone(ZoneInfo("Asia/Karachi"))
            if now.tzinfo
            else now.replace(tzinfo=ZoneInfo("Asia/Karachi"))
        )
        first_date = now_local.date()
        last_date = first_date + timedelta(days=horizon_days)
        utc = ZoneInfo("UTC")
        range_start = datetime.combine(
            first_date, time.min, tzinfo=ZoneInfo("Asia/Karachi")
        ).astimezone(utc)
        range_end = datetime.combine(
            last_date + timedelta(days=1), time.min, tzinfo=ZoneInfo("Asia/Karachi")
        ).astimezone(utc)
        with self.session_factory() as session:
            records = session.scalars(
                select(AppointmentRecord).where(
                    AppointmentRecord.employee == property_item.assigned_employee,
                    AppointmentRecord.starts_at >= range_start,
                    AppointmentRecord.starts_at < range_end,
                    AppointmentRecord.status.in_(("booked", "rescheduled")),
                )
            ).all()
        occupied = {
            record.starts_at.replace(tzinfo=UTC).astimezone(ZoneInfo("Asia/Karachi"))
            if record.starts_at.tzinfo is None
            else record.starts_at.astimezone(ZoneInfo("Asia/Karachi"))
            for record in records
        }
        slots: list[datetime] = []
        for day_offset in range(horizon_days + 1):
            slot_date = first_date + timedelta(days=day_offset)
            if slot_date.weekday() >= 6:
                continue
            for hour in range(10, 18):
                for minute in (0, 30):
                    slot = datetime.combine(
                        slot_date, time(hour, minute), tzinfo=ZoneInfo("Asia/Karachi")
                    )
                    if slot <= now_local or slot in occupied:
                        continue
                    slots.append(slot)
                    if len(slots) >= limit:
                        return slots
        return slots

    def _domain(self, record: AppointmentRecord) -> Appointment:
        contact_phone = None
        if record.contact_phone_ciphertext:
            try:
                contact_phone = self.cipher.decrypt(record.contact_phone_ciphertext)
            except Exception:  # noqa: BLE001 - optional legacy contact detail
                contact_phone = None
        return Appointment(
            id=UUID(record.id),
            reference=record.reference,
            property_id=record.property_id,
            employee=record.employee,
            employee_email=record.employee_email,
            starts_at=record.starts_at
            if record.starts_at.tzinfo
            else record.starts_at.replace(tzinfo=UTC),
            client_name=record.client_name,
            contact_email=self.cipher.decrypt(record.contact_email_ciphertext),
            contact_phone=contact_phone,
            status=record.status,
        )

    def get_for_contact(self, reference: str, contact_email: str) -> Appointment:
        """Read one appointment only after matching its consented contact identity."""
        with self.session_factory() as session:
            record = session.scalar(
                select(AppointmentRecord).where(AppointmentRecord.reference == reference)
            )
            if (
                record is None
                or self.cipher.decrypt(record.contact_email_ciphertext).casefold()
                != contact_email.casefold()
            ):
                raise ValueError("Appointment reference and contact email do not match")
            return self._domain(record)

    @staticmethod
    def _audit(
        session: object, action: str, status: str, reference: str | None, payload: dict[str, object]
    ) -> None:
        session.add(
            ToolAuditEventRecord(
                id=str(uuid4()), action=action, status=status, reference=reference, payload=payload
            )
        )

    def book(self, request: AppointmentRequest) -> Appointment:
        try:
            return self._book_once(request)
        except IntegrityError as error:
            # The preflight check is advisory; the database constraint is the
            # final arbiter when two workers race on a key or active slot.
            with self.session_factory() as session:
                existing = session.scalar(
                    select(AppointmentRecord).where(
                        AppointmentRecord.idempotency_key == str(request.idempotency_key)
                    )
                )
            if existing:
                return self._domain(existing)
            raise ValueError("The assigned employee is already booked for that slot") from error

    def _book_once(self, request: AppointmentRequest) -> Appointment:
        with self.session_factory.begin() as session:
            existing = session.scalar(
                select(AppointmentRecord).where(
                    AppointmentRecord.idempotency_key == str(request.idempotency_key)
                )
            )
            if existing:
                self._audit(
                    session,
                    "appointment.book",
                    "idempotent_replay",
                    existing.reference,
                    {"property_id": existing.property_id},
                )
                return self._domain(existing)
            if not self.properties.get_available(request.property_id):
                self._audit(
                    session,
                    "appointment.book",
                    "rejected_unavailable",
                    None,
                    {"property_id": request.property_id},
                )
                raise ValueError("Property is unavailable; the visit cannot be booked")
            property_item = self.properties.get_available(request.property_id)
            if (
                property_item is None
                or property_item.assigned_employee.casefold() != request.employee.casefold()
            ):
                self._audit(
                    session,
                    "appointment.book",
                    "rejected_employee",
                    None,
                    {"property_id": request.property_id},
                )
                raise ValueError("The selected employee is not assigned to this property")
            if not self._valid_slot(request.starts_at):
                self._audit(
                    session,
                    "appointment.book",
                    "rejected_slot",
                    None,
                    {"property_id": request.property_id},
                )
                raise ValueError(
                    "Visits are available Monday-Saturday, 10:00-18:00 PKT in 30-minute slots"
                )
            conflict = session.scalar(
                select(AppointmentRecord).where(
                    AppointmentRecord.employee == request.employee,
                    AppointmentRecord.starts_at == self._as_utc(request.starts_at),
                    AppointmentRecord.status.in_(("booked", "rescheduled")),
                )
            )
            if conflict:
                self._audit(
                    session,
                    "appointment.book",
                    "rejected_employee_busy",
                    None,
                    {"property_id": request.property_id},
                )
                raise ValueError("The assigned employee is already booked for that slot")
            record = AppointmentRecord(
                id=str(uuid4()),
                reference=f"AES-{uuid4().hex[:10].upper()}",
                property_id=request.property_id,
                employee=request.employee,
                employee_email=self._employee_email(request),
                starts_at=self._as_utc(request.starts_at),
                client_name=request.client_name,
                contact_email_ciphertext=self.cipher.encrypt(str(request.contact_email)),
                contact_phone_ciphertext=(
                    self.cipher.encrypt(request.contact_phone) if request.contact_phone else None
                ),
                status="booked",
                idempotency_key=str(request.idempotency_key),
            )
            session.add(record)
            payload = {
                "reference": record.reference,
                "property_id": record.property_id,
                "employee": record.employee,
                "employee_email": record.employee_email,
                "client_name": record.client_name,
                # Keep PII encrypted while it is persisted in the outbox. The worker
                # decrypts it only at the Google delivery boundary.
                "contact_email_ciphertext": record.contact_email_ciphertext,
                "contact_phone_ciphertext": record.contact_phone_ciphertext,
                "starts_at": record.starts_at.isoformat(),
                "event_type": "appointment.booked",
                "requirements": redact_for_retention(request.requirements),
                "meeting_notes": redact_for_retention(request.meeting_notes),
            }
            session.add(
                OutboxEventRecord(id=str(uuid4()), event_type="appointment.booked", payload=payload)
            )
            self._audit(
                session,
                "appointment.book",
                "accepted",
                record.reference,
                {"property_id": record.property_id, "status": record.status},
            )
            session.flush()
            return self._domain(record)

    def update(self, update: AppointmentUpdate, cancel: bool = False) -> Appointment:
        try:
            return self._update_once(update, cancel)
        except IntegrityError as error:
            raise ValueError("The assigned employee is already booked for that slot") from error

    def _update_once(self, update: AppointmentUpdate, cancel: bool = False) -> Appointment:
        with self.session_factory.begin() as session:
            action_name = "cancel" if cancel else "reschedule"
            existing_action = session.scalar(
                select(AppointmentActionRecord).where(
                    AppointmentActionRecord.idempotency_key == str(update.idempotency_key)
                )
            )
            if existing_action:
                existing_record = session.scalar(
                    select(AppointmentRecord).where(
                        AppointmentRecord.reference == existing_action.reference
                    )
                )
                if existing_record:
                    if (
                        existing_action.reference != update.reference
                        or existing_action.action != action_name
                        or self.cipher.decrypt(existing_record.contact_email_ciphertext).casefold()
                        != str(update.contact_email).casefold()
                    ):
                        raise ValueError("Appointment reference and contact email do not match")
                    self._audit(
                        session,
                        f"appointment.{action_name}",
                        "idempotent_replay",
                        existing_record.reference,
                        {},
                    )
                    return self._domain(existing_record)
            record = session.scalar(
                select(AppointmentRecord).where(AppointmentRecord.reference == update.reference)
            )
            if (
                not record
                or self.cipher.decrypt(record.contact_email_ciphertext).casefold()
                != str(update.contact_email).casefold()
            ):
                self._audit(
                    session,
                    "appointment.cancel" if cancel else "appointment.reschedule",
                    "rejected_identity",
                    update.reference,
                    {},
                )
                raise ValueError("Appointment reference and contact email do not match")
            if cancel:
                record.status, event_type = "cancelled", "appointment.cancelled"
            else:
                if record.status == "cancelled":
                    raise ValueError(
                        "Cancelled appointments cannot be rescheduled; create a new booking"
                    )
                if self.properties.get_available(record.property_id) is None:
                    raise ValueError("Property is unavailable; the visit cannot be rescheduled")
                if update.starts_at is None or not self._valid_slot(update.starts_at):
                    raise ValueError("Provide an eligible new appointment slot")
                conflict = session.scalar(
                    select(AppointmentRecord).where(
                        AppointmentRecord.employee == record.employee,
                        AppointmentRecord.starts_at == self._as_utc(update.starts_at),
                        AppointmentRecord.status.in_(("booked", "rescheduled")),
                        AppointmentRecord.reference != record.reference,
                    )
                )
                if conflict:
                    self._audit(
                        session,
                        "appointment.reschedule",
                        "rejected_employee_busy",
                        record.reference,
                        {},
                    )
                    raise ValueError("The assigned employee is already booked for that slot")
                record.starts_at, record.status, event_type = (
                    self._as_utc(update.starts_at),
                    "rescheduled",
                    "appointment.rescheduled",
                )
            previous_event = session.scalar(
                select(OutboxEventRecord)
                .where(OutboxEventRecord.payload["reference"].as_string() == record.reference)
                .order_by(OutboxEventRecord.created_at.desc())
                .limit(1)
            )
            previous_context = previous_event.payload if previous_event else {}
            payload = {
                "reference": record.reference,
                "property_id": record.property_id,
                "employee": record.employee,
                "employee_email": record.employee_email,
                "client_name": record.client_name,
                "contact_email_ciphertext": record.contact_email_ciphertext,
                "contact_phone_ciphertext": record.contact_phone_ciphertext,
                "starts_at": record.starts_at.isoformat(),
                "event_type": event_type,
                "requirements": previous_context.get("requirements", ""),
                "meeting_notes": previous_context.get("meeting_notes", ""),
            }
            session.add(OutboxEventRecord(id=str(uuid4()), event_type=event_type, payload=payload))
            session.add(
                AppointmentActionRecord(
                    id=str(uuid4()),
                    idempotency_key=str(update.idempotency_key),
                    reference=record.reference,
                    action=action_name,
                    result_status=record.status,
                )
            )
            self._audit(
                session,
                "appointment.cancel" if cancel else "appointment.reschedule",
                "accepted",
                record.reference,
                {"property_id": record.property_id, "status": record.status},
            )
            session.flush()
            return self._domain(record)
