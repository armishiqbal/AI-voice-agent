from __future__ import annotations

from collections.abc import Sequence

from app.core.config import Settings
from app.integrations.calendar import GoogleCalendarHandler
from app.integrations.gmail import GmailNotificationHandler
from app.integrations.n8n import N8nCrmHandler
from app.workers.outbox import OutboxHandler, PartialDeliveryError

APPOINTMENT_EVENTS = (
    "appointment.booked",
    "appointment.rescheduled",
    "appointment.cancelled",
)


class InternalCrmLeadHandler:
    """Local CRM-ready sink retaining the durable lead record."""

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


class CompositeOutboxHandler:
    """Deliver one appointment event to every configured external integration."""

    def __init__(self, handlers: Sequence[OutboxHandler]) -> None:
        self.handlers = tuple(handlers)

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        previous = payload.get("_delivery_receipts", {})
        receipts: dict[str, object] = dict(previous) if isinstance(previous, dict) else {}
        deliveries: list[dict[str, object] | None] = []
        for index, handler in enumerate(self.handlers):
            key = f"{index}:{type(handler).__name__}"
            if key not in receipts:
                try:
                    receipts[key] = await handler({**payload, "_delivery_receipts": receipts})
                except Exception as error:
                    raise PartialDeliveryError(receipts, error) from error
            deliveries.append(receipts[key])
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
    handlers: dict[str, OutboxHandler] = {}
    if integrations:
        if config.n8n_webhook_url and config.n8n_webhook_token:
            integrations.append(N8nCrmHandler(config.n8n_webhook_url, config.n8n_webhook_token))
        composite = CompositeOutboxHandler(integrations)
        handlers.update({event_type: composite for event_type in APPOINTMENT_EVENTS})
    if config.n8n_webhook_url and config.n8n_webhook_token:
        sink = N8nCrmHandler(config.n8n_webhook_url, config.n8n_webhook_token)
        handlers["lead.created"] = CompositeOutboxHandler((InternalCrmLeadHandler(), sink))
        handlers["voice.call_completed"] = CompositeOutboxHandler(
            (InternalCrmCallOutcomeHandler(), sink)
        )
    return handlers


def build_internal_handlers() -> dict[str, OutboxHandler]:
    """Handlers that do not require an external provider or OAuth credential."""
    return {
        "lead.created": InternalCrmLeadHandler(),
        "voice.call_completed": InternalCrmCallOutcomeHandler(),
    }
