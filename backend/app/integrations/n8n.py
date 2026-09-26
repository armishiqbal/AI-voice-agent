"""Authenticated delivery of redacted business events to an n8n CRM workflow."""

from __future__ import annotations

import hashlib
import json

import httpx


class N8nCrmHandler:
    def __init__(self, url: str, token: str) -> None:
        self.url, self.token = url, token

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        # An allowlist prevents encrypted contacts or internal model state from
        # accidentally being forwarded to a third-party workflow.
        fields = (
            "reference",
            "event_type",
            "property_id",
            "employee",
            "starts_at",
            "lead_id",
            "call_id",
            "status",
            "intent",
            "city",
            "area",
            "budget_pkr",
            "follow_up_at",
        )
        event = {key: payload[key] for key in fields if key in payload}
        if "event_type" not in event:
            if "lead_id" in event:
                event["event_type"] = "lead.created"
            elif "call_id" in event:
                event["event_type"] = "voice.call_completed"
        canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
        event_id = hashlib.sha256(canonical.encode()).hexdigest()
        stored_receipts = payload.get("_delivery_receipts", {})
        receipts = {
            str(key): {"provider": receipt.get("provider"), "status": "delivered"}
            for key, receipt in (
                stored_receipts.items() if isinstance(stored_receipts, dict) else []
            )
            if isinstance(receipt, dict)
        }
        envelope = {"event_id": event_id, "event": event, "upstream_deliveries": receipts}
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.post(
                self.url,
                json=envelope,
                headers={
                    "X-Awaaz-Token": self.token,
                    "Idempotency-Key": event_id,
                },
            )
        if response.status_code != 200:
            raise RuntimeError(f"n8n delivery failed (HTTP {response.status_code})")
        try:
            acknowledgement = response.json()
        except ValueError as error:
            raise RuntimeError("n8n returned an invalid acknowledgement") from error
        if (
            not isinstance(acknowledgement, dict)
            or acknowledgement.get("event_id") != event_id
            or acknowledgement.get("status") != "delivered"
        ):
            raise RuntimeError("n8n did not confirm completion for this event")
        return {"provider": "n8n", "event_id": event_id, "status": "delivered"}
