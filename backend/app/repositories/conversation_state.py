from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.repositories.database import SessionLocal
from app.repositories.records import ConversationStateRecord


class ConversationStateStore:
    """Durable LangGraph conversation snapshots with bounded JSON fields."""

    retention_days = 30

    def load(self, conversation_id: str) -> dict[str, object] | None:
        with SessionLocal() as session:
            record = session.scalar(
                select(ConversationStateRecord).where(
                    ConversationStateRecord.conversation_id == conversation_id
                )
            )
            if record is None:
                return None
            expires_at = record.expires_at
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at is None or expires_at <= datetime.now(UTC):
                session.delete(record)
                session.commit()
                return None
            return {
                "history": list(record.history or [])[-20:],
                "detected_language": record.detected_language,
                "lead_profile": dict(record.lead_profile or {}),
                "budget": record.budget,
                "city": record.city,
                "area": record.area,
                "bedrooms": record.bedrooms,
                "amenities": list(record.amenities or []),
                "investment_goal": record.investment_goal,
                "intent": record.intent,
                "retrieved_sources": list(record.retrieved_sources or [])[:5],
                "selected_property_ids": list(record.selected_property_ids or [])[:3],
                "tool_results": dict(record.tool_results or {}),
                "appointment_status": record.appointment_status,
                "escalation_reason": record.escalation_reason,
            }

    def save(self, conversation_id: str, state: object) -> None:
        now = datetime.now(UTC)
        payload = {
            "history": list(getattr(state, "history", []))[-20:],
            "detected_language": str(getattr(state, "detected_language", "en")),
            "lead_profile": dict(getattr(state, "lead_profile", {})),
            "budget": getattr(state, "budget", None),
            "city": getattr(state, "city", None),
            "area": getattr(state, "area", None),
            "bedrooms": getattr(state, "bedrooms", None),
            "amenities": list(getattr(state, "amenities", []))[:10],
            "investment_goal": getattr(state, "investment_goal", None),
            "intent": getattr(getattr(state, "intent", None), "value", "unknown"),
            "retrieved_sources": list(getattr(state, "retrieved_sources", []))[:5],
            "selected_property_ids": list(getattr(state, "selected_property_ids", []))[:3],
            "tool_results": dict(getattr(state, "tool_results", {})),
            "appointment_status": getattr(state, "appointment_status", None),
            "escalation_reason": getattr(state, "escalation_reason", None),
            "updated_at": now,
            "expires_at": now + timedelta(days=self.retention_days),
        }
        with SessionLocal.begin() as session:
            record = session.get(ConversationStateRecord, conversation_id)
            if record is None:
                session.add(ConversationStateRecord(conversation_id=conversation_id, **payload))
            else:
                for key, value in payload.items():
                    setattr(record, key, value)

    def purge_expired(self) -> int:
        now = datetime.now(UTC)
        with SessionLocal.begin() as session:
            result = session.execute(
                delete(ConversationStateRecord).where(
                    ConversationStateRecord.expires_at.is_not(None),
                    ConversationStateRecord.expires_at <= now,
                )
            )
            return int(result.rowcount or 0)
