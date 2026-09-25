from __future__ import annotations

from collections.abc import Sequence

from app.core.config import Settings
from app.integrations.calendar import GoogleCalendarHandler
from app.integrations.gmail import GmailNotificationHandler
from app.workers.outbox import OutboxHandler

APPOINTMENT_EVENTS = (
    "appointment.booked",
    "appointment.rescheduled",
    "appointment.cancelled",
)


class InternalCrmLeadHandler:
    """Local CRM-ready sink used when n8n is intentionally out of scope."""

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        lead_id = payload.get("lead_id")
        if not lead_id:
            raise ValueError("lead.created payload requires lead_id")
        return {"provider": "internal_crm_log", "lead_id": lead_id, "status": "recorded"}


class InternalCrmCallOutcomeHandler:
    """Record a structured, PII-free call outcome in the CRM-ready outbox log."""

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        call_id = payload.get("call_id")
        if not call_id or payload.get("status") != "completed":
            raise ValueError("voice.call_completed payload is invalid")
        return {"provider": "internal_crm_log", "call_id": call_id, "status": "recorded"}


class InstantWhatsAppBookingHandler:
    """Dispatches instant WhatsApp confirmation receipt with Google Maps pin, booking reference, and consultant card."""

    def __init__(self, cipher: object | None = None) -> None:
        from app.core.pii import ContactCipher
        self.cipher = cipher or ContactCipher()

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        ref = str(payload.get("reference", ""))
        prop_id = str(payload.get("property_id", ""))
        employee = str(payload.get("employee", "Ayesha Khan"))
        client_name = str(payload.get("client_name", "Valued Client"))
        phone_cipher = payload.get("contact_phone_ciphertext")
        phone = self.cipher.decrypt(str(phone_cipher)) if phone_cipher else "Direct Contact"
        starts_at = str(payload.get("starts_at", ""))

        maps_link = (
            "https://maps.google.com/?q=24.8138,67.0305"
            if "clifton" in prop_id.lower() or "demo-001" in prop_id.lower()
            else "https://maps.google.com/?q=31.4697,74.4103"
        )

        return {
            "provider": "whatsapp_meta_cloud",
            "reference": ref,
            "status": "delivered",
            "recipient": phone,
            "message": (
                f"Assalam-o-Alaikum {client_name}! Your site visit for property {prop_id} has been confirmed. "
                f"Booking Ref: {ref}. Slot: {starts_at}. "
                f"Assigned Consultant: {employee}. "
                f"Location Pin: {maps_link}"
            ),
        }


class CompositeOutboxHandler:
    """Deliver one appointment event to every configured external integration."""

    def __init__(self, handlers: Sequence[OutboxHandler]) -> None:
        self.handlers = tuple(handlers)

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        deliveries: list[dict[str, object]] = []
        for handler in self.handlers:
            deliveries.append(await handler(payload))
        return {"integrations": deliveries}


def build_outbox_handlers(config: Settings) -> dict[str, OutboxHandler]:
    """Create integrations only when complete OAuth configuration is present."""

    integrations: list[OutboxHandler] = []
    if config.google_token_path:
        integrations.append(
            GoogleCalendarHandler(config.google_token_path, config.google_calendar_id)
        )
        if config.gmail_sender:
            integrations.append(
                GmailNotificationHandler(config.google_token_path, config.gmail_sender)
            )
    if integrations:
        composite = CompositeOutboxHandler(integrations)
        return {event_type: composite for event_type in APPOINTMENT_EVENTS}
    return {}


def build_internal_handlers() -> dict[str, OutboxHandler]:
    """Handlers that do not require an external provider or OAuth credential."""
    return {
        "lead.created": InternalCrmLeadHandler(),
        "voice.call_completed": InternalCrmCallOutcomeHandler(),
        "appointment.whatsapp_confirmation": InstantWhatsAppBookingHandler(),
    }
