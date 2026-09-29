from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.n8n import N8nCrmHandler
from app.services.voice_booking import VoiceBookingFlow
from app.workers.handlers import CompositeOutboxHandler, build_outbox_handlers
from app.workers.outbox import PartialDeliveryError


@pytest.mark.parametrize(
    "text", ["no do not book it", "haan nahi kar do", "don't confirm", "not yes"]
)
def test_negation_cannot_authorize_voice_booking(text):
    assert not VoiceBookingFlow._is_confirmation(text)


def test_n8n_configuration_requires_https_and_paired_token():
    with pytest.raises(ValidationError):
        Settings(n8n_webhook_url="https://example.com/webhook", n8n_webhook_token=None)
    with pytest.raises(ValidationError):
        Settings(n8n_webhook_url="http://example.com/webhook", n8n_webhook_token="secret")
    settings = Settings(
        n8n_webhook_url="http://localhost:5678/webhook",
        n8n_webhook_token="secret",
        google_token_path=None,
    )
    assert set(build_outbox_handlers(settings)) == {
        "lead.created",
        "lead.follow_up_due",
        "voice.call_completed",
    }


@pytest.mark.asyncio
async def test_partial_delivery_retry_skips_already_completed_provider():
    calls = []

    async def calendar(payload):
        calls.append("calendar")
        return {"provider": "calendar"}

    async def email(payload):
        calls.append("email")
        if calls.count("email") == 1:
            raise RuntimeError("transient email failure")
        return {"provider": "gmail"}

    composite = CompositeOutboxHandler((calendar, email))
    with pytest.raises(PartialDeliveryError) as failure:
        await composite({"reference": "AES-1"})
    await composite({"reference": "AES-1", "_delivery_receipts": failure.value.receipts})
    assert calls == ["calendar", "email", "email"]


@pytest.mark.asyncio
async def test_n8n_requires_matching_completion_and_redacts_contacts(monkeypatch):
    captured = []
    valid = False

    def respond(request):
        event = json.loads(request.content)
        captured.append(event)
        assert request.headers["X-Awaaz-Token"] == "secret"
        return httpx.Response(
            200,
            json={"event_id": event["event_id"], "status": "delivered" if valid else "accepted"},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "app.integrations.n8n.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    handler = N8nCrmHandler("https://workflow.example/webhook", "secret")
    payload = {
        "lead_id": "lead-1",
        "client_name": "Private Name",
        "contact_email_ciphertext": "ciphertext",
    }
    with pytest.raises(RuntimeError, match="did not confirm"):
        await handler(payload)
    valid = True
    await handler(payload)
    assert captured[0]["event_id"] == captured[1]["event_id"]
    assert captured[0]["event"] == {"lead_id": "lead-1", "event_type": "lead.created"}


@pytest.mark.asyncio
async def test_n8n_follow_up_event_forwards_only_approved_reminder_fields(monkeypatch):
    captured = []

    def respond(request):
        event = json.loads(request.content)
        captured.append(event)
        return httpx.Response(
            200,
            json={"event_id": event["event_id"], "status": "delivered"},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "app.integrations.n8n.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    await N8nCrmHandler("https://workflow.example/webhook", "secret")({
        "event_type": "lead.follow_up_due",
        "lead_id": "lead-1",
        "intent": "sell",
        "city": "Karachi",
        "area": "DHA Phase 6",
        "follow_up_at": "2026-09-29T12:00:00+00:00",
        "client_name": "Private Name",
        "contact_email": "private@example.com",
        "notes": "private notes",
    })

    assert captured[0]["event"] == {
        "event_type": "lead.follow_up_due",
        "lead_id": "lead-1",
        "intent": "sell",
        "city": "Karachi",
        "area": "DHA Phase 6",
        "follow_up_at": "2026-09-29T12:00:00+00:00",
    }


def test_n8n_export_has_auth_and_requires_completed_crm():
    workflow = json.loads(
        (Path(__file__).parents[2] / "workflows/n8n/awaaz-business-events.json").read_text()
    )
    nodes = {node["name"]: node for node in workflow["nodes"]}
    webhook = nodes["After Call Intent Property Appointment"]
    validate = nodes["Validate Calendar and Email Receipts"]
    crm = nodes["Idempotent CRM Update"]
    confirm = nodes["Require Durable CRM Acknowledgement"]
    respond = nodes["Acknowledge Outbox"]

    assert webhook["parameters"]["authentication"] == "headerAuth"
    assert webhook["parameters"]["responseMode"] == "responseNode"
    assert "Calendar delivery not confirmed" in validate["parameters"]["jsCode"]
    assert "Employee email delivery not confirmed" in validate["parameters"]["jsCode"]
    assert crm["retryOnFail"] is True and crm["maxTries"] == 3
    assert crm["parameters"]["url"] == "={{ $env.AWAAZ_CRM_WEBHOOK_URL }}"
    headers = crm["parameters"]["headerParameters"]["parameters"]
    assert {header["name"] for header in headers} == {"Idempotency-Key"}
    assert crm["parameters"]["options"]["redirect"]["redirect"]["followRedirects"] is False
    assert "delivered" in confirm["parameters"]["jsCode"]
    assert respond["parameters"]["options"]["responseCode"] == 200
    assert workflow["active"] is False
    assert workflow["settings"]["saveDataSuccessExecution"] == "none"
    assert workflow["settings"]["saveDataErrorExecution"] == "none"
    assert all(not node.get("credentials") for node in workflow["nodes"])


def test_employee_recipient_resolved_from_operator_directory(monkeypatch):
    from datetime import UTC, datetime

    from app.core.config import settings
    from app.domain.models import AppointmentRequest
    from app.repositories.appointments import SqlAppointmentService

    request = AppointmentRequest(
        property_id="PROP-1",
        employee="Ayesha Khan",
        employee_email="untrusted@example.com",
        starts_at=datetime.now(UTC),
        client_name="Ali Khan",
        contact_email="ali@example.com",
        consent=True,
    )
    monkeypatch.setattr(
        settings, "employee_email_directory", {"Ayesha Khan": "employee@example.com"}
    )
    assert SqlAppointmentService._employee_email(request) == "employee@example.com"
    monkeypatch.setattr(settings, "employee_email_directory", {})
    monkeypatch.setattr(settings, "gmail_sender", "sender@example.com")
    with pytest.raises(ValueError, match="EMPLOYEE_EMAIL_DIRECTORY"):
        SqlAppointmentService._employee_email(request)


@pytest.mark.asyncio
async def test_worker_persists_partial_receipts_before_retry():
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from app.repositories.bootstrap import create_schema_for_local_development
    from app.repositories.database import Base, SessionLocal, engine
    from app.repositories.records import OutboxEventRecord
    from app.workers.outbox import OutboxWorker

    Base.metadata.drop_all(bind=engine)
    create_schema_for_local_development()
    event_id = str(uuid4())
    calls = []

    async def calendar(payload):
        calls.append("calendar")
        return {"provider": "google_calendar"}

    async def email(payload):
        calls.append("email")
        if calls.count("email") == 1:
            raise RuntimeError("retry me")
        return {"provider": "gmail"}

    try:
        with SessionLocal.begin() as session:
            session.add(
                OutboxEventRecord(
                    id=event_id, event_type="appointment.booked", payload={"reference": "AES-1"}
                )
            )
        worker = OutboxWorker({"appointment.booked": CompositeOutboxHandler((calendar, email))})
        assert (await worker.process_once()).failed == 1
        with SessionLocal.begin() as session:
            event = session.get(OutboxEventRecord, event_id)
            assert event.payload["_delivery_receipts"]
            event.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        assert (await worker.process_once()).delivered == 1
        assert calls == ["calendar", "email", "email"]
    finally:
        Base.metadata.drop_all(bind=engine)
