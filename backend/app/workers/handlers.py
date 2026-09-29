from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

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


class InternalCrmFollowUpHandler:
    """Make a due follow-up visible in the durable operator outbox without contacting clients."""

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        lead_id = payload.get("lead_id")
        follow_up_at = payload.get("follow_up_at")
        if not lead_id or not follow_up_at:
            raise ValueError("lead.follow_up_due payload requires lead_id and follow_up_at")
        return {
            "provider": "internal_crm_log",
            "lead_id": lead_id,
            "status": "reminder_due",
        }


class InternalCrmCallOutcomeHandler:
    """Record a structured, PII-free call outcome in the CRM-ready outbox log."""

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        call_id = payload.get("call_id")
        if not call_id or payload.get("status") != "completed":
            raise ValueError("voice.call_completed payload is invalid")
        return {"provider": "internal_crm_log", "call_id": call_id, "status": "recorded"}


class DeliveryState(TypedDict):
    payload: dict[str, object]
    receipts: dict[str, object]


_delivery_logger = logging.getLogger("awaaz.delivery_graph")


class CompositeOutboxHandler:
    """Execute configured integration tools as an ordered LangGraph delivery graph.

    SQL outbox leases/retry metadata remain authoritative. The graph consumes
    saved provider receipts so downstream retries do not repeat completed tools.
    """

    def __init__(self, handlers: Sequence[OutboxHandler]) -> None:
        self.handlers = tuple(handlers)
        graph = StateGraph(DeliveryState)
        previous = START
        for index, handler in enumerate(self.handlers):
            node_name = f"deliver_{index}_{type(handler).__name__}"
            receipt_key = f"{index}:{type(handler).__name__}"
            graph.add_node(node_name, self._delivery_node(handler, receipt_key, node_name))
            graph.add_edge(previous, node_name)
            previous = node_name
        graph.add_edge(previous, END)
        self.graph = graph.compile()

    @staticmethod
    def _delivery_node(
        handler: OutboxHandler, key: str, node_name: str
    ) -> Callable[[DeliveryState], Awaitable[DeliveryState]]:
        async def deliver(state: DeliveryState) -> DeliveryState:
            receipts = dict(state["receipts"])
            if key in receipts:
                _delivery_logger.info("delivery_node node=%s status=replayed_receipt", node_name)
                return {"payload": state["payload"], "receipts": receipts}
            try:
                receipts[key] = await handler({**state["payload"], "_delivery_receipts": receipts})
            except Exception as error:
                _delivery_logger.warning("delivery_node node=%s status=failed", node_name)
                raise PartialDeliveryError(receipts, error) from error
            _delivery_logger.info("delivery_node node=%s status=delivered", node_name)
            return {"payload": state["payload"], "receipts": receipts}

        return deliver

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        previous = payload.get("_delivery_receipts", {})
        receipts: dict[str, object] = dict(previous) if isinstance(previous, dict) else {}
        result = await self.graph.ainvoke({"payload": payload, "receipts": receipts})
        return {
            "integrations": [
                result["receipts"][f"{index}:{type(handler).__name__}"]
                for index, handler in enumerate(self.handlers)
            ]
        }


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
        handlers["lead.follow_up_due"] = CompositeOutboxHandler(
            (InternalCrmFollowUpHandler(), sink)
        )
        handlers["voice.call_completed"] = CompositeOutboxHandler(
            (InternalCrmCallOutcomeHandler(), sink)
        )
    return handlers


def build_internal_handlers() -> dict[str, OutboxHandler]:
    """Handlers that do not require an external provider or OAuth credential."""
    return {
        "lead.created": InternalCrmLeadHandler(),
        "lead.follow_up_due": InternalCrmFollowUpHandler(),
        "voice.call_completed": InternalCrmCallOutcomeHandler(),
    }
