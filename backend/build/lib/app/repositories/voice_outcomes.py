from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from app.repositories.database import SessionLocal
from app.repositories.records import OutboxEventRecord


def record_voice_call_outcome(
    *,
    conversation_id: str,
    channel: str,
    duration_ms: int,
    state: object | None,
    appointment_reference: str | None = None,
) -> str:
    """Persist a PII-free call outcome and CRM-ready outbox event exactly once."""
    if channel not in {"browser", "twilio"}:
        raise ValueError("Unsupported voice call channel")
    if not conversation_id or len(conversation_id) > 128:
        raise ValueError("Conversation identifier is invalid")
    if duration_ms < 0:
        raise ValueError("Call duration cannot be negative")

    intent_value = getattr(getattr(state, "intent", None), "value", "unknown")
    lead_profile = getattr(state, "lead_profile", {}) or {}
    qualified_intent = (
        lead_profile.get("qualified_intent", intent_value)
        if isinstance(lead_profile, dict)
        else intent_value
    )
    tool_results = getattr(state, "tool_results", {}) or {}
    budget_signal = (
        tool_results.get("budget_vs_listing", {}) if isinstance(tool_results, dict) else {}
    )
    selected_ids = list(getattr(state, "selected_property_ids", []) or [])[:3]
    sources = list(getattr(state, "retrieved_sources", []) or [])[:5]
    city = _safe_label(getattr(state, "city", None))
    area = _safe_label(getattr(state, "area", None))
    payload: dict[str, object] = {
        "call_id": conversation_id,
        "channel": channel,
        "status": "completed",
        "duration_ms": duration_ms,
        "language": str(getattr(state, "detected_language", "unknown"))[:16],
        "intent": str(qualified_intent)[:32],
        "city": city,
        "area": area,
        "budget_pkr": getattr(state, "budget", None),
        "budget_below_list": bool(budget_signal.get("below_list", False)),
        "lowest_matching_price_pkr": budget_signal.get("lowest_matching_price_pkr"),
        "property_ids": [str(value)[:64] for value in selected_ids],
        "source_ids": [str(value)[:128] for value in sources],
        "appointment_reference": appointment_reference,
        "escalation_reason": _safe_label(getattr(state, "escalation_reason", None)),
        "completed_at": datetime.now(UTC).isoformat(),
        "summary": _summary(
            intent=str(qualified_intent),
            city=city,
            area=area,
            budget=getattr(state, "budget", None),
            property_ids=selected_ids,
            appointment_reference=appointment_reference,
            budget_below_list=bool(budget_signal.get("below_list", False)),
        ),
    }
    event_id = str(uuid5(NAMESPACE_URL, f"awaaz:voice.call_completed:{conversation_id}"))
    with SessionLocal.begin() as session:
        existing = session.get(OutboxEventRecord, event_id)
        if existing is None:
            session.add(
                OutboxEventRecord(
                    id=event_id,
                    event_type="voice.call_completed",
                    payload=payload,
                )
            )
    return event_id


def _safe_label(value: object) -> str | None:
    """Keep free-form model/state labels useful without retaining contact PII."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email redacted]", value)
    value = re.sub(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)", "[phone redacted]", value)
    return value[:128]


def _summary(
    *,
    intent: str,
    city: str | None,
    area: str | None,
    budget: int | None,
    property_ids: list[object],
    appointment_reference: str | None,
    budget_below_list: bool,
) -> str:
    parts = [f"Intent: {intent}"]
    if city or area:
        parts.append("Location: " + ", ".join(value for value in (area, city) if value))
    if budget is not None:
        parts.append(f"Budget PKR {budget:,}")
    if property_ids:
        parts.append("Discussed properties: " + ", ".join(str(value) for value in property_ids[:3]))
    if budget_below_list:
        parts.append("Budget below the cheapest matching available listing")
    if appointment_reference:
        parts.append(f"Appointment reference: {appointment_reference}")
    return ". ".join(parts)[:700]
