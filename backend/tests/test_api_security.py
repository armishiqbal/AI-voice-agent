import asyncio
from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.api.app import app, require_admin_api_key, voice_origin_allowed
from app.core.config import settings
from app.domain.models import AgentDecision
from app.integrations.stt.deepgram import STTEvent
from app.integrations.tts.router import AudioChunk, TTSProviderError
from app.repositories.database import SessionLocal
from app.repositories.records import OutboxEventRecord
from app.services.voice_sessions import VoiceSessionService


def _voice_ticket(origin: str = "http://localhost:5173") -> str:
    import app.api.app as api

    issued = api.voice_sessions.issue("testclient", origin)
    assert issued is not None
    return issued[0]


def _authenticate_voice_socket(
    websocket, ticket: str, language: str = "ur-Latn"
) -> dict[str, object]:
    websocket.send_json({"type": "authenticate", "ticket": ticket, "language": language})
    return websocket.receive_json()


def _receive_json_timeout(websocket, timeout_seconds: float = 5) -> dict[str, object]:
    async def receive() -> dict[str, object]:
        async with asyncio.timeout(timeout_seconds):
            return await websocket._send_rx.receive()

    message = websocket.portal.call(receive)
    websocket._raise_on_close(message)
    import json

    return json.loads(message["text"])


def test_text_turn_returns_sanitized_structured_reasoning_status(monkeypatch) -> None:
    import app.api.app as api

    decision = AgentDecision(kind="ask_clarification", spoken_text="Which area do you prefer?")
    monkeypatch.setattr(
        api,
        "agent",
        SimpleNamespace(decision_provider=object(), respond=lambda *_args: decision),
    )
    monkeypatch.setattr(api, "_structured_reasoning_status", lambda: {
        "configured": True,
        "status": "provider_error",
        "fallback": "deterministic",
        "cooldown_remaining_seconds": 0.0,
        "last_failure_category": "rate_limited",
    })

    class Traces:
        def observe(self, *_args):
            return None

    class Transcripts:
        def append(self, *_args):
            return None

    monkeypatch.setattr(api, "traces", Traces())
    monkeypatch.setattr(api, "transcripts", Transcripts())
    response = TestClient(api.app).post(
        "/v1/conversations/test-conversation/turn",
        json={"text": "I need a home in Karachi", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["decision"]["spoken_text"] == decision.spoken_text
    assert response.json()["reasoning_status"] == "provider_error"
    assert response.json()["reasoning_failure_category"] == "rate_limited"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("OpenAI speech request failed with HTTP 429", "rate_limited"),
        ("OpenAI speech request failed with HTTP 402", "insufficient_credits"),
        ("Fish Audio has insufficient API credits", "insufficient_credits"),
        ("OpenAI Realtime speech generation timed out", "provider_timeout"),
        ("OpenAI Realtime did not produce first audio before its deadline", "first_audio_deadline"),
        ("OpenAI Realtime speech did not match the approved text", "speech_integrity_rejected"),
    ],
)
def test_voice_tts_failure_metrics_use_safe_provider_categories(message: str, expected: str) -> None:
    import app.api.app as api

    assert api._voice_tts_failure_code(TTSProviderError(message)) == expected


def test_voice_tts_failure_metrics_classify_wrapped_provider_cause() -> None:
    import app.api.app as api

    try:
        raise TimeoutError("provider request timed out")
    except TimeoutError as cause:
        error = TTSProviderError("Speech synthesis failed")
        error.__cause__ = cause

    assert api._voice_tts_failure_code(error) == "provider_timeout"


def test_voice_tts_failure_metrics_classify_openai_quota_exhaustion() -> None:
    import app.api.app as api

    try:
        raise RuntimeError("received 1013 insufficient_quota.credit_balance_exhausted")
    except RuntimeError as cause:
        error = TTSProviderError("OpenAI Realtime speech service is unavailable")
        error.__cause__ = cause

    assert api._voice_tts_failure_code(error) == "insufficient_credits"


@pytest.mark.asyncio
async def test_hybrid_readiness_uses_configured_tts_when_realtime_tts_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    class Routes:
        def __init__(self, readiness: dict[str, bool]) -> None:
            self.route_status = readiness

        async def readiness(self) -> dict[str, bool]:
            return self.route_status

    class STT:
        async def is_ready(self) -> bool:
            return True

    monkeypatch.setattr(
        api,
        "provider_readiness",
        lambda: SimpleNamespace(openai=True, multilingual_tts=False),
    )
    monkeypatch.setattr(api, "stt", STT())
    async def unexpected_openai_probe() -> bool:
        raise AssertionError("disabled OpenAI Realtime readiness must not delay hybrid voice")

    monkeypatch.setattr(api, "live_openai_stt_ready", unexpected_openai_probe)
    monkeypatch.setattr(api, "openai_voice_tts", Routes({"*": True}))
    monkeypatch.setattr(api, "tts", Routes({"ur-Latn": True, "en": True}))
    monkeypatch.setattr(settings, "openai_realtime_tts_enabled", False)

    readiness = await api.voice_option_readiness()

    assert readiness["hybrid_voice_ready"] is True
    assert readiness["live_voice_pipeline_ready"] is True


async def _async_true() -> bool:
    return True


@pytest.mark.asyncio
async def test_openai_voice_readiness_requires_a_live_realtime_handshake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    calls = {"warmup": 0, "close": 0}

    class Probe:
        async def is_ready(self) -> bool:
            return True

        async def warmup(self) -> bool:
            calls["warmup"] += 1
            return False

        async def aclose(self) -> None:
            calls["close"] += 1

    monkeypatch.setattr(api, "_openai_stt_readiness_cache", None)
    monkeypatch.setattr(api, "build_openai_realtime_stt", lambda config: Probe())

    assert await api.live_openai_stt_ready() is False
    assert await api.live_openai_stt_ready() is False
    assert calls == {"warmup": 1, "close": 1}


@pytest.fixture(autouse=True)
def isolate_voice_session_service(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.app as api
    from app.repositories.bootstrap import create_schema_for_local_development

    create_schema_for_local_development()
    monkeypatch.setattr(
        api,
        "voice_sessions",
        VoiceSessionService(f"test-hmac-key-{uuid4()}"),
    )


def test_admin_key_is_required_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-key")

    with pytest.raises(HTTPException) as missing:
        require_admin_api_key(None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException):
        require_admin_api_key("wrong-key")

    assert require_admin_api_key("test-admin-key") is None


def test_state_changing_admin_routes_have_dependency() -> None:
    protected_paths = {
        "/v1/properties/import",
        "/v1/properties/import-file",
        "/v1/properties/validate-file",
        "/v1/knowledge/ingest-file",
        "/v1/admin/metrics",
        "/v1/admin/evaluations/report",
        "/v1/admin/outbox",
        "/v1/admin/audit",
        "/v1/admin/call-outcomes",
        "/v1/admin/follow-ups/{lead_id}/complete",
    }
    for route in app.routes:
        if getattr(route, "path", None) in protected_paths:
            assert route.dependant.dependencies, f"{route.path} is missing an admin dependency"


def test_admin_metrics_exposes_due_follow_ups_without_contact_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    due_reminders = [{
        "lead_id": "lead-123",
        "intent": "sell",
        "city": "Karachi",
        "area": "DHA Phase 6",
        "budget_pkr": None,
        "follow_up_at": "2026-09-29T12:00:00+00:00",
    }]
    monkeypatch.setattr(api.leads, "list_due_followups", lambda: due_reminders)

    with TestClient(app) as client:
        response = client.get("/v1/admin/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["follow_ups_due"] == due_reminders
    assert "contact_email" not in body["follow_ups_due"][0]
    assert "client_name" not in body["follow_ups_due"][0]


def test_inventory_file_preview_and_import_are_all_or_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import func, select

    from app.repositories.database import SessionLocal
    from app.repositories.records import PropertyImportBatchRecord, PropertyRecord

    import_id = f"UPLOAD-{uuid4()}"
    source_label = f"owner-reviewed-{uuid4()}"
    csv_body = (
        b"id,title,city,area,purpose,price_pkr,bedrooms,size_sqft,amenities,developer,"
        b"payment_plan,available,assigned_employee,source_version\n"
        + f"{import_id},Reviewed home,Karachi,DHA,sale,25000000,3,1800,parking,Owner,".encode()
        + b"Installments,true,Ayesha,rev-1\n"
        + b"UPLOAD-BAD,Invalid row,Karachi,DHA,sale,not-a-price,3,1800,parking,Owner,"
        + b"Installments,true,Ayesha,rev-1\n"
    )
    monkeypatch.setattr(settings, "app_env", "development")
    with TestClient(app) as client:
        params = {
            "filename": "owner-inventory.csv",
            "source": source_label,
        }
        preview = client.post(
            "/v1/properties/validate-file", params=params, content=csv_body
        )
        assert preview.status_code == 200
        assert preview.json()["accepted"] == 1
        assert preview.json()["rejected"] == 1
        assert preview.json()["validation_errors"][0]["row"] == 3
        assert preview.json()["validation_errors"][0]["field"] == "price_pkr"

        rejected_import = client.post(
            "/v1/properties/import-file", params=params, content=csv_body
        )
        assert rejected_import.status_code == 422
        assert rejected_import.json()["detail"]["accepted"] == 1
        assert rejected_import.json()["detail"]["rejected"] == 1
        assert all(row["id"] != import_id for row in client.get("/v1/properties").json())

    with SessionLocal() as session:
        assert session.get(PropertyRecord, import_id) is None
        batch_count = session.scalar(
            select(func.count())
            .select_from(PropertyImportBatchRecord)
            .where(PropertyImportBatchRecord.source == source_label)
        )
        assert batch_count == 0


def test_clean_inventory_preview_can_be_confirmed_and_imported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import delete

    from app.repositories.database import SessionLocal
    from app.repositories.records import PropertyImportBatchRecord, PropertyRecord

    import_id = f"UPLOAD-{uuid4()}"
    csv_body = (
        b"id,title,city,area,purpose,price_pkr,bedrooms,size_sqft,developer,payment_plan,available,assigned_employee,source_version\n"
        + f"{import_id},Reviewed home,Karachi,DHA,sale,25000000,3,1800,Owner,".encode()
        + b"Installments,true,Ayesha,approved-rev-1\n"
    )
    monkeypatch.setattr(settings, "app_env", "development")
    batch_id: str | None = None
    try:
        with TestClient(app) as client:
            params = {
                "filename": "owner-inventory.csv",
                "source": "owner-reviewed-rev-1",
            }
            preview = client.post(
                "/v1/properties/validate-file", params=params, content=csv_body
            )
            assert preview.status_code == 200
            assert preview.json()["accepted"] == 1
            assert preview.json()["rejected"] == 0

            imported = client.post(
                "/v1/properties/import-file", params=params, content=csv_body
            )
            assert imported.status_code == 202
            result = imported.json()
            batch_id = result["batch_id"]
            assert result["accepted"] == 1
            assert result["rejected"] == 0
            # CSV imports are retained as drafts until staff classifies and approves them.
            assert all(row["id"] != import_id for row in client.get("/v1/properties").json())
            with SessionLocal() as session:
                property_item = session.get(PropertyRecord, import_id)
                assert property_item is not None
                assert property_item.source == "owner-reviewed-rev-1"
                assert property_item.source_version == "approved-rev-1"
    finally:
        with SessionLocal.begin() as session:
            session.execute(delete(PropertyRecord).where(PropertyRecord.id == import_id))
            if batch_id:
                session.execute(
                    delete(PropertyImportBatchRecord).where(
                        PropertyImportBatchRecord.id == batch_id
                    )
                )


def test_knowledge_file_ingestion_preserves_property_and_language_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    class KnowledgeStore:
        def __init__(self) -> None:
            self.chunks = []

        def upsert(self, chunks) -> None:
            self.chunks = chunks

    store = KnowledgeStore()
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(api, "knowledge_store", store)

    with TestClient(app) as client:
        response = client.post(
            "/v1/knowledge/ingest-file",
            params={
                "filename": "DHA-faq.md",
                "source": "owner-faq-rev-2",
                "property_id": "DHA-001",
                "city": "Karachi",
                "language": "ur-Latn",
                "source_version": "rev-2",
            },
            content="Payment plan details are listed in the approved brochure.",
        )

    assert response.status_code == 202
    result = response.json()
    assert result["accepted"] == 1
    assert result["source"] == "owner-faq-rev-2"
    assert result["metadata"] == {
        "property_id": "DHA-001",
        "city": "Karachi",
        "language": "ur-Latn",
        "version": "rev-2",
    }
    assert store.chunks[0].metadata["property_id"] == "DHA-001"
    assert store.chunks[0].metadata["language"] == "ur-Latn"


def test_consent_bound_lead_form_remains_public() -> None:
    lead_routes = [route for route in app.routes if getattr(route, "path", None) == "/v1/leads"]
    assert lead_routes
    assert not lead_routes[0].dependant.dependencies


def test_readyz_separates_api_health_from_live_voice_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    monkeypatch.setattr(api, "live_openai_stt_ready", lambda: _async_true())
    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["status"] in {"ready", "degraded"}
    assert "database_ready" in readiness["application"]
    assert readiness["live_voice"]["status"] in {"configured_unverified", "blocked"}
    assert readiness["live_voice"]["verification"] == "configuration_only"
    assert isinstance(readiness["live_voice"]["blockers"], list)
    assert readiness["live_voice"]["configured"] is (
        readiness["providers"]["standard_voice_ready"]
        or readiness["providers"]["openai_voice_ready"]
        or readiness["providers"]["hybrid_voice_ready"]
    )
    assert readiness["structured_reasoning"]["status"] in {
        "unconfigured",
        "configured_unverified",
        "cooldown",
        "provider_error",
    }


def test_readyz_reports_degraded_agent_during_structured_provider_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api
    from app.integrations.providers import ProviderReadiness

    async def voice_ready() -> dict[str, object]:
        return {
            "standard_voice_ready": False,
            "openai_voice_ready": False,
            "hybrid_voice_ready": True,
            "multilingual_tts": False,
            "live_voice_pipeline_ready": True,
        }

    monkeypatch.setattr(
        api,
        "provider_readiness",
        lambda: ProviderReadiness(
            deepgram=True,
            openai=True,
            fish_audio=True,
            elevenlabs=False,
            pinecone=True,
            multilingual_tts=False,
            calendar=False,
            gmail=False,
            telephony=False,
        ),
    )
    monkeypatch.setattr(api, "voice_option_readiness", voice_ready)
    monkeypatch.setattr(
        api.agent,
        "decision_provider",
        SimpleNamespace(failure_cooldown_remaining=12.3),
    )

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["status"] == "degraded"
    assert readiness["mode"] == "live"
    assert readiness["structured_reasoning"] == {
        "configured": True,
        "status": "cooldown",
        "fallback": "deterministic",
        "cooldown_remaining_seconds": 12.3,
        "last_failure_category": None,
    }


def test_readyz_keeps_structured_provider_failure_visible_after_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    async def voice_ready() -> dict[str, object]:
        return {
            "standard_voice_ready": False,
            "openai_voice_ready": False,
            "hybrid_voice_ready": True,
            "multilingual_tts": False,
            "live_voice_pipeline_ready": True,
        }

    monkeypatch.setattr(
        api,
        "voice_option_readiness",
        voice_ready,
    )
    monkeypatch.setattr(
        api.agent,
        "decision_provider",
        SimpleNamespace(failure_cooldown_remaining=0.0, last_failure_category="rate_limited"),
    )

    with TestClient(app) as client:
        readiness = client.get("/readyz").json()

    assert readiness["status"] == "degraded"
    assert readiness["structured_reasoning"] == {
        "configured": True,
        "status": "provider_error",
        "fallback": "deterministic",
        "cooldown_remaining_seconds": 0.0,
        "last_failure_category": "rate_limited",
    }


def test_voice_origin_must_match_configured_origin_outside_development() -> None:
    assert voice_origin_allowed(
        "https://voice.example.com", "production", "https://voice.example.com"
    )
    assert not voice_origin_allowed(
        "https://evil.example", "production", "https://voice.example.com"
    )
    assert not voice_origin_allowed(None, "production", "https://voice.example.com")
    assert not voice_origin_allowed(
        "https://voice.example.com/path", "production", "https://voice.example.com"
    )
    assert voice_origin_allowed(None, "development", "http://localhost:5173")


def test_voice_websocket_rejects_disallowed_origin_before_accepting() -> None:
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/v1/voice", headers={"origin": "https://evil.example"}),
    ):
        pass
    assert disconnected.value.code == 1008


def test_voice_ticket_endpoint_checks_origin_and_limits_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api
    from app.services.voice_sessions import VoiceSessionService

    async def ready_options() -> dict[str, bool]:
        return {
            "standard_voice_ready": False,
            "openai_voice_ready": True,
            "hybrid_voice_ready": True,
            "multilingual_tts": False,
            "live_voice_pipeline_ready": True,
        }

    async def warmup_voice_transport() -> bool:
        return False

    monkeypatch.setattr(api, "voice_option_readiness", ready_options)
    monkeypatch.setattr(api.openai_voice_tts, "warmup", warmup_voice_transport)

    monkeypatch.setattr(
        api,
        "voice_sessions",
        VoiceSessionService(f"test-hmac-key-{uuid4()}", issue_limit=1),
    )
    with TestClient(app) as client:
        assert client.post("/v1/voice/session").status_code == 403
        assert (
            client.post("/v1/voice/session", headers={"origin": "https://evil.example"}).status_code
            == 403
        )
        response = client.post(
            "/v1/voice/session",
            headers={"origin": "http://localhost:5173"},
            json={"mode": "hybrid"},
        )
        assert response.status_code == 200
        ticket = response.json()["ticket"]
        assert isinstance(ticket, str) and len(ticket) >= 40
        limited = client.post(
            "/v1/voice/session",
            headers={"origin": "http://localhost:5173"},
            json={"mode": "openai"},
        )
        assert limited.status_code == 429
        assert "ticket" not in limited.text


def test_voice_websocket_rejects_non_object_and_wrongly_typed_events() -> None:
    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        assert _authenticate_voice_socket(websocket, _voice_ticket())["type"] == "state"
        websocket.send_json(["not", "an", "object"])
        assert websocket.receive_json()["type"] == "error"
        websocket.send_json({"type": "user_text", "text": 4})
        assert websocket.receive_json() == {"type": "error", "message": "Text must be a string"}


def test_booking_contact_is_session_scoped_and_never_sent_to_agent_or_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    model_inputs: list[str] = []
    retained: list[tuple[str, str, str]] = []

    def respond(conversation_id: str, text: str, language: str) -> AgentDecision:
        del conversation_id, language
        model_inputs.append(text)
        return AgentDecision(kind="answer", spoken_text="Ji, main help karta hoon.")

    class EmptyTTS:
        async def synthesize_stream(self, text: str, language: str):
            del text, language
            if False:
                yield None

    class NoopSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            async for frame in audio:
                if frame is None:
                    return
                yield STTEvent(text="", is_final=False)

    noop_stt = NoopSTT()

    monkeypatch.setattr(api.agent, "respond", respond)
    monkeypatch.setattr(api.transcripts, "append", lambda *args: retained.append(args))
    monkeypatch.setattr(api, "tts", EmptyTTS())
    monkeypatch.setattr(api, "stt", noop_stt)
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: noop_stt)
    monkeypatch.setattr(api, "build_english_hybrid_stt", lambda config: noop_stt)
    with SessionLocal() as session:
        existing_event_ids = set(
            session.scalars(
                select(OutboxEventRecord.id).where(
                    OutboxEventRecord.event_type == "voice.call_completed"
                )
            ).all()
        )

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_json(
            {
                "type": "booking_contact",
                "contact": {
                    "client_name": "Private Caller",
                    "contact_email": "private@example.com",
                    "contact_phone": "+923001234567",
                    "consent": True,
                },
            }
        )
        assert websocket.receive_json() == {"type": "booking_contact_status", "ready": True}
        websocket.send_json({"type": "user_text", "text": "hello", "language": "en"})
        while True:
            event = websocket.receive_json()
            if event.get("type") == "agent_response":
                break
        websocket.close()

    assert model_inputs == ["hello"]
    assert all(
        "private@example.com" not in text
        and "+923001234567" not in text
        and "Private Caller" not in text
        for _, _, text in retained
    )
    new_events = []
    for _ in range(60):
        with SessionLocal() as session:
            events = session.scalars(
                select(OutboxEventRecord).where(OutboxEventRecord.event_type == "voice.call_completed")
            ).all()
        new_events = [event for event in events if event.id not in existing_event_ids]
        if new_events:
            break
        sleep(0.05)
    assert len(new_events) == 1
    event_payload = new_events[0].payload
    assert event_payload["channel"] == "browser"
    assert "private@example.com" not in str(event_payload)
    assert "+923001234567" not in str(event_payload)
    assert "Private Caller" not in str(event_payload)


def test_voice_websocket_closes_oversized_event() -> None:
    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_text("x" * (settings.voice_max_event_bytes + 1))
        with pytest.raises(WebSocketDisconnect) as disconnected:
            websocket.receive_json()
        assert disconnected.value.code == 1009


def test_voice_session_uses_selected_response_language_for_transcribed_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    received: dict[str, str] = {}

    class FakeSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            del audio
            yield STTEvent(
                text="Find me an apartment",
                language="en",
                confidence=0.99,
                is_final=True,
                speech_final=True,
            )

    def respond(conversation_id: str, text: str, language: str) -> AgentDecision:
        del conversation_id, text
        received["language"] = language
        return AgentDecision(kind="answer", spoken_text="Ji, main madad karta hoon.")

    monkeypatch.setattr(api, "stt", FakeSTT())
    monkeypatch.setattr(api.agent, "respond", respond)
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        initial = _authenticate_voice_socket(websocket, _voice_ticket())
        assert initial["type"] == "state"
        websocket.send_json({"type": "set_language", "language": "ar"})
        assert websocket.receive_json()["response_language"] == "ar"
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        events = []
        while not any(event.get("type") == "agent_response" for event in events):
            events.append(websocket.receive_json())

    assert received["language"] == "ar"


def test_voice_websocket_rejects_replayed_or_origin_bound_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket = _voice_ticket()
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173,http://localhost:5174")
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket:
            initial = _authenticate_voice_socket(websocket, ticket)
        assert initial["type"] == "state"
        # A consumed ticket cannot establish a second session.
        with client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as replayed:
            replayed.send_json({"type": "authenticate", "ticket": ticket})
            with pytest.raises(WebSocketDisconnect) as disconnected:
                replayed.receive_json()
            assert disconnected.value.code == 1008


def test_voice_websocket_enforces_active_session_capacity_and_releases_lease(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.api.app as api
    from app.repositories.database import Base

    class NoopSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            async for frame in audio:
                if frame is None:
                    return
                yield STTEvent(text="", is_final=False)

    noop_stt = NoopSTT()
    monkeypatch.setattr(api, "stt", noop_stt)
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: noop_stt)
    monkeypatch.setattr(api, "build_english_hybrid_stt", lambda config: noop_stt)

    database_engine = create_engine(
        f"sqlite:///{tmp_path / 'voice-session-capacity.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(database_engine)
    session_factory = sessionmaker(bind=database_engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(
        api,
        "voice_sessions",
        VoiceSessionService(
            f"capacity-websocket-key-{uuid4()}",
            session_factory=session_factory,
            dialect_name="sqlite",
            max_active_total=1,
        ),
    )
    with TestClient(app) as client:
        first_ticket = _voice_ticket()
        second_ticket = _voice_ticket()
        with client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as first:
            assert _authenticate_voice_socket(first, first_ticket)["type"] == "state"
            with client.websocket_connect(
                "/v1/voice", headers={"origin": "http://localhost:5173"}
            ) as second:
                second.send_json({"type": "authenticate", "ticket": second_ticket})
                with pytest.raises(WebSocketDisconnect) as disconnected:
                    second.receive_json()
                assert disconnected.value.code == 1013
            # Explicitly close the accepted connection, then wait for the async server
            # cleanup path (which releases the database lease in a worker thread).
            first.close()
            cleanup_deadline = monotonic() + 2
            while (
                api.voice_sessions.capacity_snapshot()["active"] > 0
                and monotonic() < cleanup_deadline
            ):
                sleep(0.01)

        assert api.voice_sessions.capacity_snapshot()["active"] == 0
        retry_ticket = _voice_ticket()
        with client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as retried:
            assert _authenticate_voice_socket(retried, retry_ticket)["type"] == "state"
            retried.close()

        with (
            pytest.raises(WebSocketDisconnect) as disconnected,
            client.websocket_connect("/v1/voice", headers={"origin": "http://localhost:5174"}),
        ):
            pass
        assert disconnected.value.code == 1008
    database_engine.dispose()


def test_voice_session_rejects_unsupported_response_language() -> None:
    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_json({"type": "set_language", "language": "xx"})
        assert websocket.receive_json() == {
            "type": "error",
            "message": "Unsupported response language",
        }


def test_voice_session_records_separate_decision_tts_and_end_to_audio_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    measurements: dict[str, list[float]] = {}

    class FakeSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            del audio
            yield STTEvent(
                text="Find me an apartment",
                language="en",
                confidence=0.99,
                is_final=True,
                speech_final=True,
            )

    class FakeTTS:
        async def synthesize_stream(self, text: str, language: str):
            assert text == "A verified option is available."
            yield AudioChunk(
                sequence=0,
                audio=b"\x01\x00" * 160,
                language=language,
                sample_rate=24_000,
            )
            yield AudioChunk(
                sequence=1,
                audio=b"",
                language="",
                sample_rate=24_000,
                is_final=True,
            )

    def respond(conversation_id: str, text: str, language: str) -> AgentDecision:
        del conversation_id, text, language
        return AgentDecision(kind="answer", spoken_text="A verified option is available.")

    monkeypatch.setattr(api, "stt", FakeSTT())
    monkeypatch.setattr(api, "tts", FakeTTS())
    monkeypatch.setattr(api.agent, "respond", respond)
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    monkeypatch.setattr(
        api.traces,
        "observe",
        lambda name, value, limit=1000: measurements.setdefault(name, []).append(value),
    )
    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        websocket.receive_json()
        events = []
        while not any(
            event.get("type") == "state"
            and event.get("state") == "listening"
            and not event.get("audio_started")
            for event in events
        ):
            events.append(websocket.receive_json())

    assert any(event.get("type") == "audio_chunk" and event.get("audio_base64") for event in events)
    assert measurements["voice.decision_latency_ms"]
    assert measurements["voice.tts_first_audio_latency_ms"]
    assert measurements["voice.final_transcript_to_first_audio_ms"]
    assert measurements["voice.tts_stream_duration_ms"]
    assert measurements["voice.final_transcript_to_first_audio_ms"][0] >= 0


def test_hybrid_voice_records_deepgram_audio_cursor_lag_from_websocket_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api
    from app.integrations.stt import DeepgramStreamingSTT

    measurements: dict[str, list[float]] = {}
    released_tickets: list[str] = []
    monkeypatch.setattr(settings, "openai_realtime_tts_enabled", False)
    assert settings.openai_realtime_tts_enabled is False

    class CursorSTT(DeepgramStreamingSTT):
        def __init__(self) -> None:
            super().__init__(api_key="test-key", finalize_timeout_seconds=0.5)

        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            if self.on_transport_ready is not None:
                self.on_transport_ready()
            async for frame in audio:
                if frame == b"":
                    yield STTEvent(
                        text="Find me a home",
                        language="en",
                        confidence=0.99,
                        audio_start_seconds=0.0,
                        audio_duration_seconds=0.01,
                        is_final=True,
                        from_finalize=True,
                    )

    class FakeTTS:
        async def synthesize_stream(self, text: str, language: str):
            assert text == "A verified option is available."
            yield AudioChunk(0, b"\x01\x00" * 80, language, 24_000)
            yield AudioChunk(1, b"", language, 24_000, is_final=True)

    class FakeRealtimeTTS:
        async def warmup(self) -> bool:
            return False

        async def aclose(self) -> None:
            return None

        async def synthesize_stream(self, text: str, language: str):
            del text, language
            if False:
                yield AudioChunk(0, b"", "en", 24_000)

    provider = CursorSTT()
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: provider)
    monkeypatch.setattr(api, "OpenAIRealtimeSpeechProvider", lambda **kwargs: FakeRealtimeTTS())
    monkeypatch.setattr(api, "tts", FakeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="A verified option is available."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    monkeypatch.setattr(api, "record_voice_call_outcome", lambda **kwargs: None)
    monkeypatch.setattr(
        api.traces,
        "observe",
        lambda name, value, limit=1000: measurements.setdefault(name, []).append(value),
    )
    actual_release = api.voice_sessions.release

    def record_release(ticket: str) -> None:
        released_tickets.append(ticket)
        actual_release(ticket)

    monkeypatch.setattr(api.voice_sessions, "release", record_release)
    active_sessions_before = api.voice_sessions.capacity_snapshot()["active"]
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket:
            _authenticate_voice_socket(websocket, issued[0])
            websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
            while websocket.receive_json().get("audio_started") is not True:
                pass
            websocket.send_json({"type": "audio_turn_start"})
            websocket.send_bytes(b"\x01\x00" * 160)
            websocket.send_json({"type": "audio_turn_end"})
            events = []
            saw_final_audio = False
            saw_listening = False
            while not (saw_final_audio and saw_listening):
                event = _receive_json_timeout(websocket)
                events.append(event)
                saw_final_audio |= event.get("type") == "audio_chunk" and event.get("is_final") is True
                saw_listening |= event.get("type") == "state" and event.get("state") == "listening"
            websocket.close()

        # Let the WebSocket disconnect handler run on the still-live app loop.
        cleanup_deadline = monotonic() + 3
        while (
            issued[0] not in released_tickets
            and monotonic() < cleanup_deadline
        ):
            sleep(0.01)

    assert any(event.get("type") == "transcript" and event.get("is_final") for event in events)
    assert measurements["voice.stt_audio_cursor_lag_ms"] == [0.0]
    server_released = issued[0] in released_tickets
    try:
        assert server_released, "hybrid voice disconnect should release its server-side session lease"
    finally:
        # Keep a failed cleanup assertion from polluting later tests.
        if not server_released:
            actual_release(issued[0])
    assert api.voice_sessions.capacity_snapshot()["active"] == active_sessions_before


def test_realtime_tts_failure_falls_back_to_http_speech_before_first_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    monkeypatch.setattr(settings, "openai_realtime_tts_enabled", True)

    class ReadySTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            del audio
            if False:
                yield STTEvent()

    class BrokenRealtimeTTS:
        def __init__(self, **kwargs) -> None:
            del kwargs

        async def warmup(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

        async def synthesize_stream(self, text: str, language: str):
            del text, language
            raise TTSProviderError("provider did not start")
            yield AudioChunk(0, b"", "", 24_000)  # pragma: no cover

    class HttpFallbackTTS:
        async def synthesize_stream(self, text: str, language: str):
            assert text == "One verified answer."
            yield AudioChunk(0, b"\x01\x00" * 80, language, 24_000)
            yield AudioChunk(1, b"", language, 24_000, is_final=True)

    fallback_counts: list[str] = []
    monkeypatch.setattr(api, "build_openai_realtime_stt", lambda config: ReadySTT())
    monkeypatch.setattr(api, "OpenAIRealtimeSpeechProvider", BrokenRealtimeTTS)
    monkeypatch.setattr(api, "openai_voice_tts", HttpFallbackTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="One verified answer."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    monkeypatch.setattr(api.traces, "increment", lambda name, amount=1: fallback_counts.append(name))
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "openai")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "user_text", "text": "Hello", "language": "en"})
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event)
            if event.get("type") == "audio_chunk" and event.get("is_final"):
                break

    assert any(event.get("type") == "agent_response" for event in events)
    assert any(event.get("type") == "audio_chunk" and event.get("audio_base64") for event in events)
    assert "voice:realtime_tts_fallback" in fallback_counts


def test_openai_voice_buffers_audio_while_transcription_connects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    assert settings.voice_audio_queue_frames >= 128

    from app.integrations.stt import OpenAIRealtimeSTT

    class DelayedSTT(OpenAIRealtimeSTT):
        def __init__(self) -> None:
            super().__init__("test-key")

        async def is_ready(self) -> bool:
            return True

        async def warmup(self) -> bool:
            return True

        async def stream(self, audio):
            await asyncio.sleep(0.2)
            async for frame in audio:
                if frame == b"":
                    yield STTEvent(text="Hello", is_final=True, speech_final=True)

    class FakeTTS:
        async def synthesize_stream(self, text: str, language: str):
            del text
            yield AudioChunk(sequence=0, audio=b"\x01\x00" * 80, language=language, sample_rate=24_000)
            yield AudioChunk(sequence=1, audio=b"", language=language, sample_rate=24_000, is_final=True)

    class NoRealtimeTTS:
        async def warmup(self) -> bool:
            return False

        async def aclose(self) -> None:
            return None

        async def synthesize_stream(self, text: str, language: str):
            del text, language
            raise AssertionError("Unavailable Realtime TTS must not synthesize")
            yield AudioChunk(sequence=0, audio=b"", language="", sample_rate=24_000)

    provider = DelayedSTT()
    monkeypatch.setattr(api, "build_openai_realtime_stt", lambda config: provider)
    monkeypatch.setattr(api, "OpenAIRealtimeSpeechProvider", lambda **kwargs: NoRealtimeTTS())
    monkeypatch.setattr(api, "openai_voice_tts", FakeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda conversation_id, text, language: AgentDecision(kind="answer", spoken_text="Hello"),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "openai")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "set_language", "language": "ur-Latn"})
        assert websocket.receive_json()["response_language"] == "ur-Latn"
        assert provider.language == "ur"
        assert "Roman Urdu" in provider.transcription_prompt
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        for _ in range(40):
            websocket.send_bytes(b"\x01\x00" * 160)
        # Client VAD commits the OpenAI Realtime input buffer at each turn end.
        websocket.send_json({"type": "audio_turn_end", "auto": True})
        events = []
        while not any(event.get("type") == "agent_response" for event in events):
            events.append(websocket.receive_json())

    assert any(event.get("type") == "transcript" and event.get("is_final") for event in events)


def test_openai_voice_sends_prepared_acknowledgement_during_transcription_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    monkeypatch.setattr(settings, "openai_realtime_tts_enabled", True)

    class ReadySTT:
        async def is_ready(self) -> bool:
            return True

        async def warmup(self) -> bool:
            return True

        async def stream(self, audio):
            async for frame in audio:
                if frame == b"":
                    yield STTEvent(text="Mujhe ghar chahiye", is_final=True, speech_final=True)

    class RealtimeTTS:
        async def warmup(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

        async def synthesize_stream(self, text: str, language: str):
            if text == "Ji, ek second.":
                yield AudioChunk(0, b"\x01\x00" * 100, language, 24_000)
                return
            yield AudioChunk(0, b"\x02\x00" * 100, language, 24_000)
            yield AudioChunk(1, b"", language, 24_000, is_final=True)

    monkeypatch.setattr(api, "build_openai_realtime_stt", lambda config: ReadySTT())
    monkeypatch.setattr(api, "OpenAIRealtimeSpeechProvider", lambda **kwargs: RealtimeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="I can help with that."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "openai")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_end"})
        while websocket.receive_json().get("state") != "processing":
            pass
        websocket.send_json({"type": "audio_turn_start"})
        websocket.send_bytes(b"\x01\x00" * 160)
        websocket.send_json({"type": "audio_turn_end"})
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event)
            if event.get("type") == "audio_chunk" and event.get("is_final") is True:
                break

    acknowledgement_index = next(
        index for index, event in enumerate(events)
        if event.get("type") == "audio_chunk" and event.get("acknowledgement") is True
    )
    agent_response_index = next(
        index for index, event in enumerate(events)
        if event.get("type") == "agent_response"
    )
    assert acknowledgement_index < agent_response_index
    assert events[acknowledgement_index]["is_final"] is False
    assert any(event.get("type") == "agent_response" for event in events)


def test_hybrid_voice_keeps_one_stt_stream_for_multiple_browser_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    class BoundarySTT:
        def __init__(self) -> None:
            self.seen_boundaries = 0
            self.streams = 0

        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            self.streams += 1
            async for frame in audio:
                if frame == b"":
                    self.seen_boundaries += 1
                    yield STTEvent(
                        text=f"Mujhe Karachi mein ghar chahiye {self.seen_boundaries}",
                        is_final=True,
                    )

    class RealtimeTTS:
        async def warmup(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

        async def synthesize_stream(self, text: str, language: str):
            del text
            yield AudioChunk(0, b"\x01\x00" * 80, language, 24_000)
            yield AudioChunk(1, b"", language, 24_000, is_final=True)

    provider = BoundarySTT()
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: provider)
    monkeypatch.setattr(api, "tts", RealtimeTTS())
    monkeypatch.setattr(api, "OpenAIRealtimeSpeechProvider", lambda **kwargs: RealtimeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="I can help with that."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        while websocket.receive_json().get("audio_started") is not True:
            pass
        events = []
        for _ in range(2):
            turn_start_index = len(events)
            websocket.send_json({"type": "audio_turn_start"})
            websocket.send_bytes(b"\x01\x00" * 160)
            websocket.send_json({"type": "audio_turn_end"})
            while not any(
                (event.get("type") == "audio_chunk" and event.get("is_final") is True)
                or event.get("type") in {"stt_unavailable", "agent_unavailable"}
                for event in events[turn_start_index:]
            ):
                events.append(_receive_json_timeout(websocket))

    assert not any(event.get("type") in {"stt_unavailable", "agent_unavailable"} for event in events), events
    assert provider.streams == 1
    assert provider.seen_boundaries == 2
    assert any(event.get("type") == "transcript" and event.get("is_final") for event in events)
    assert any(
        event.get("type") == "transcript" and event.get("speech_final") is True
        for event in events
    )
    assert sum(event.get("type") == "agent_response" for event in events) == 2


def test_hybrid_voice_processes_stable_final_arriving_before_browser_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    received: list[str] = []

    class PrecommitFinalSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            # Model a provider that returns a stable segment final before the
            # browser VAD's explicit end-of-turn event arrives.
            yield STTEvent(
                text="Mujhe Karachi mein",
                confidence=0.94,
                is_final=True,
                speech_final=False,
                from_finalize=False,
            )
            async for frame in audio:
                if frame == b"":
                    yield STTEvent(
                        text="ghar chahiye",
                        confidence=0.92,
                        is_final=True,
                        speech_final=True,
                    )

    class FakeTTS:
        async def synthesize_stream(self, text: str, language: str):
            del text
            yield AudioChunk(0, b"\x01\x00" * 80, language, 24_000)
            yield AudioChunk(1, b"", language, 24_000, is_final=True)

    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: PrecommitFinalSTT())
    monkeypatch.setattr(api, "tts", FakeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda _conversation_id, text, _language: (
            received.append(text)
            or AgentDecision(kind="answer", spoken_text="I can help with that.")
        ),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        while websocket.receive_json().get("audio_started") is not True:
            pass
        websocket.send_json({"type": "audio_turn_start"})
        websocket.send_bytes(b"\x01\x00" * 160)
        websocket.send_json({"type": "audio_turn_end"})
        events = []
        while not any(event.get("type") == "agent_response" for event in events):
            events.append(_receive_json_timeout(websocket))

    assert received == ["Mujhe Karachi mein ghar chahiye"]
    assert any(
        event.get("type") == "transcript"
        and event.get("is_final") is True
        and event.get("speech_final") is True
        for event in events
    )


def test_hybrid_voice_recovers_when_stt_closes_between_completed_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    class ClosingSTT:
        def __init__(self) -> None:
            self.streams = 0

        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            self.streams += 1
            async for frame in audio:
                if frame == b"":
                    yield STTEvent(text=f"Voice turn {self.streams}", is_final=True)
                    # Some provider callbacks are delayed. A late speech-start
                    # for the just-finalized turn must not cancel the reply.
                    yield STTEvent(speech_started=True)
                    return

    class RealtimeTTS:
        async def warmup(self) -> bool:
            return True

        async def aclose(self) -> None:
            return None

        async def synthesize_stream(self, text: str, language: str):
            del text
            yield AudioChunk(0, b"\x01\x00" * 80, language, 24_000)
            yield AudioChunk(1, b"", language, 24_000, is_final=True)

    provider = ClosingSTT()
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: provider)
    monkeypatch.setattr(api, "OpenAIRealtimeSpeechProvider", lambda **kwargs: RealtimeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="I can help with that."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        while websocket.receive_json().get("audio_started") is not True:
            pass

        completed_events = []
        for turn_number in range(2):
            websocket.send_json({"type": "audio_turn_start"})
            if turn_number == 1:
                # Confirm the next provider stream is already running before
                # the first PCM frame for the follow-up turn is sent.
                while True:
                    event = _receive_json_timeout(websocket)
                    completed_events.append(event)
                    if (
                        event.get("type") == "state"
                        and event.get("state") == "listening"
                        and event.get("interrupt_playback") is True
                    ):
                        break
                assert provider.streams == 2
            websocket.send_bytes(b"\x01\x00" * 160)
            websocket.send_json({"type": "audio_turn_end"})
            while True:
                event = _receive_json_timeout(websocket)
                completed_events.append(event)
                if event.get("type") == "audio_chunk" and event.get("is_final") is True:
                    break

    assert provider.streams == 2
    assert sum(event.get("type") == "agent_response" for event in completed_events) == 2
    assert not any(event.get("type") == "stt_unavailable" for event in completed_events)


def test_hybrid_voice_waits_for_browser_commit_after_provider_endpointing() -> None:
    import app.api.app as api

    early_endpoint = STTEvent(text="Mujhe ghar", is_final=True, speech_final=True)
    finalized_after_commit = STTEvent(text="Mujhe ghar chahiye", is_final=True)

    assert api._is_turn_final("hybrid", early_endpoint, browser_committed=False) is False
    assert api._is_turn_final("hybrid", finalized_after_commit, browser_committed=True) is True
    assert api._is_turn_final("openai", early_endpoint, browser_committed=False) is False
    # Keep provider-owned end-of-turn behavior for the legacy standard route.
    assert api._is_turn_final("standard", early_endpoint, browser_committed=False) is True


def test_stt_automatic_recovery_only_accepts_known_transient_failures() -> None:
    import app.api.app as api

    assert api._stt_failure_is_recoverable("stt_stream_ended") is True
    assert api._stt_failure_is_recoverable("stt_provider_timeout") is True
    assert api._stt_failure_is_recoverable("stt_provider_auth_rejected") is False
    assert api._stt_failure_is_recoverable("stt_provider_insufficient_credits") is False
    assert api._stt_failure_is_recoverable("stt_provider_rate_limited") is False
    assert api._stt_failure_is_recoverable("unexpected_provider_error") is False


def test_hybrid_finalize_deadline_covers_provider_read_started_before_browser_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    class HangingSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            async for frame in audio:
                if frame:
                    yield STTEvent(text="partial transcript", confidence=0.9)
                elif frame == b"":
                    await asyncio.sleep(0.5)
                    yield STTEvent(text="late stable transcript", is_final=True)

    class NoAudioTTS:
        async def synthesize_stream(self, text: str, language: str):
            del text, language
            if False:
                yield

    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: HangingSTT())
    monkeypatch.setattr(api, "tts", NoAudioTTS())
    monkeypatch.setattr(api, "openai_voice_tts", NoAudioTTS())
    monkeypatch.setattr(api.settings, "openai_realtime_tts_enabled", False)
    monkeypatch.setattr(api.settings, "stt_finalize_timeout_seconds", 0.05)
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: pytest.fail("A partial transcript must not reach the agent"),
    )
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        while websocket.receive_json().get("audio_started") is not True:
            pass
        websocket.send_json({"type": "audio_turn_start"})
        websocket.send_bytes(b"\x01\x00" * 160)
        interim = websocket.receive_json()
        while interim.get("type") != "transcript":
            interim = websocket.receive_json()
        assert interim["is_final"] is False
        started_at = monotonic()
        websocket.send_json({"type": "audio_turn_end"})
        events = []
        while not any(event.get("type") == "stt_unavailable" for event in events):
            events.append(_receive_json_timeout(websocket, timeout_seconds=1))

    failure = next(event for event in events if event.get("type") == "stt_unavailable")
    assert failure["reason"] == "stt_finalize_timeout"
    assert monotonic() - started_at < 0.4
    assert not any(event.get("type") == "agent_response" for event in events)


def test_hybrid_voice_speaks_a_safe_retry_after_finalize_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    class HangingSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            async for frame in audio:
                if frame:
                    yield STTEvent(text="partial budget transcript", confidence=0.9)
                elif frame == b"":
                    await asyncio.sleep(0.5)
                    yield STTEvent(text="unconfirmed final", is_final=True)

    class SpeechProvider:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def is_ready(self) -> bool:
            return True

        async def synthesize_stream(self, text: str, language: str, voice_id=None):
            del voice_id
            self.prompts.append(text)
            yield AudioChunk(0, b"provider-audio-fixture", language, is_final=True)

    speech = SpeechProvider()
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: HangingSTT())
    monkeypatch.setattr(api, "tts", speech)
    monkeypatch.setattr(api, "openai_voice_tts", speech)
    monkeypatch.setattr(api.settings, "openai_realtime_tts_enabled", False)
    monkeypatch.setattr(api.settings, "stt_finalize_timeout_seconds", 0.05)
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: pytest.fail("An unconfirmed interim transcript must not reach the agent"),
    )
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        while websocket.receive_json().get("audio_started") is not True:
            pass
        websocket.send_json({"type": "audio_turn_start"})
        websocket.send_bytes(b"\x01\x00" * 160)
        interim = websocket.receive_json()
        while interim.get("type") != "transcript":
            interim = websocket.receive_json()
        assert interim["is_final"] is False
        websocket.send_json({"type": "audio_turn_end"})
        events = []
        while not (
            any(event.get("type") == "agent_response" for event in events)
            and any(
                event.get("type") == "audio_chunk"
                and not event.get("acknowledgement")
                and event.get("is_final") is True
                for event in events
            )
        ):
            events.append(_receive_json_timeout(websocket, timeout_seconds=1))

    recovery = next(event for event in events if event.get("type") == "agent_response")
    assert recovery["decision"]["reason"] == "transcription_incomplete"
    from app.services.voice_recovery import transcription_recovery_prompt

    assert recovery["decision"]["spoken_text"] == transcription_recovery_prompt(
        "ur-Latn", "partial budget transcript"
    )
    assert speech.prompts[-1] == recovery["decision"]["spoken_text"]
    assert not any(event.get("type") == "stt_unavailable" for event in events)


def test_hybrid_voice_speaks_a_safe_retry_for_low_confidence_final(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.api.app as api
    from app.repositories.database import Base

    database_engine = create_engine(
        f"sqlite:///{tmp_path / 'low-confidence-recovery.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(database_engine)
    session_factory = sessionmaker(bind=database_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(
        api,
        "voice_sessions",
        VoiceSessionService(
            f"low-confidence-recovery-key-{uuid4()}",
            session_factory=session_factory,
            dialect_name="sqlite",
            max_active_total=2,
        ),
    )

    class LowConfidenceSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            async for frame in audio:
                if frame == b"":
                    yield STTEvent(
                        text="unclear transcript",
                        confidence=0.2,
                        is_final=True,
                        from_finalize=True,
                    )

    class SpeechProvider:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def is_ready(self) -> bool:
            return True

        async def synthesize_stream(self, text: str, language: str, voice_id=None):
            del voice_id
            self.prompts.append(text)
            yield AudioChunk(0, b"retry-audio-fixture", language, is_final=True)

    speech = SpeechProvider()
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: LowConfidenceSTT())
    monkeypatch.setattr(api, "tts", speech)
    monkeypatch.setattr(api, "openai_voice_tts", speech)
    monkeypatch.setattr(api.settings, "openai_realtime_tts_enabled", False)
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: pytest.fail("A low-confidence final transcript must not reach the agent"),
    )
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        while websocket.receive_json().get("audio_started") is not True:
            pass
        websocket.send_json({"type": "audio_turn_start"})
        websocket.send_bytes(b"\x01\x00" * 160)
        websocket.send_json({"type": "audio_turn_end"})
        events = []
        while not (
            any(event.get("type") == "agent_response" for event in events)
            and any(
                event.get("type") == "audio_chunk"
                and event.get("is_final") is True
                and not event.get("acknowledgement")
                for event in events
            )
        ):
            events.append(_receive_json_timeout(websocket, timeout_seconds=1))

    low_confidence = next(
        event for event in events if event.get("type") == "transcript_low_confidence"
    )
    recovery = next(event for event in events if event.get("type") == "agent_response")
    from app.services.voice_recovery import transcription_recovery_prompt

    assert low_confidence["confidence"] == 0.2
    assert recovery["decision"]["reason"] == "transcription_incomplete"
    assert recovery["decision"]["spoken_text"] == transcription_recovery_prompt(
        "ur-Latn", "unclear transcript"
    )
    assert speech.prompts[-1] == recovery["decision"]["spoken_text"]
    assert any(
        event.get("type") == "audio_chunk"
        and event.get("is_final") is True
        and event.get("response_id") == recovery["response_id"]
        for event in events
    )
    database_engine.dispose()


def test_hybrid_voice_plays_configured_tts_ack_before_manual_finalize_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.app as api

    monkeypatch.setattr(settings, "openai_realtime_tts_enabled", False)

    class FinalizeSTT:
        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            async for frame in audio:
                if frame == b"":
                    yield STTEvent(
                        text="Mujhe Karachi mein ghar chahiye",
                        is_final=True,
                        from_finalize=True,
                    )

    class ConfiguredTTS:
        async def is_ready(self) -> bool:
            return True

        async def synthesize_stream(self, text: str, language: str, voice_id=None):
            del voice_id
            marker = b"\x03\x00" if text == "Ji, ek second." else b"\x04\x00"
            yield AudioChunk(0, marker * 100, language, 24_000)
            if text != "Ji, ek second.":
                yield AudioChunk(1, b"", language, 24_000, is_final=True)

    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda config: FinalizeSTT())
    monkeypatch.setattr(api, "tts", ConfiguredTTS())
    monkeypatch.setattr(
        api.agent,
        "decision_provider",
        SimpleNamespace(failure_cooldown_remaining=12.3),
    )
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="I found your request."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    issued = api.voice_sessions.issue("testclient", "http://localhost:5173", "hybrid")
    assert issued is not None

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/voice", headers={"origin": "http://localhost:5173"}
        ) as websocket,
    ):
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        while websocket.receive_json().get("audio_started") is not True:
            pass
        websocket.send_json({"type": "audio_turn_start"})
        websocket.send_bytes(b"\x01\x00" * 160)
        websocket.send_json({"type": "audio_turn_end"})
        events = []
        while not any(event.get("type") == "audio_chunk" and event.get("is_final") for event in events):
            events.append(websocket.receive_json())

    acknowledgement_index = next(
        index for index, event in enumerate(events)
        if event.get("type") == "audio_chunk" and event.get("acknowledgement") is True
    )
    agent_response_index = next(
        index for index, event in enumerate(events)
        if event.get("type") == "agent_response"
    )
    assert acknowledgement_index < agent_response_index
    assert events[acknowledgement_index]["is_final"] is False
    response = next(event for event in events if event.get("type") == "agent_response")
    assert response["reasoning_status"] == "cooldown"


@pytest.mark.parametrize('first_chunk,reason', [(False, 'tts_first_audio_timeout'), (True, 'tts_idle_timeout')])
def test_voice_tts_deadlines_recover_and_tag_response(monkeypatch, first_chunk, reason):
    import app.api.app as api

    closed = []
    class FakeSTT:
        async def is_ready(self):
            return True
    class HangingTTS:
        async def synthesize_stream(self, text, language):
            try:
                if first_chunk:
                    yield AudioChunk(sequence=0, audio=b'\x01\x00', language=language)
                await asyncio.sleep(3600)
            finally:
                closed.append(True)
    monkeypatch.setattr(api, 'stt', FakeSTT())
    monkeypatch.setattr(api, 'tts', HangingTTS())
    monkeypatch.setattr(settings, 'voice_tts_first_audio_timeout_seconds', 0.04)
    monkeypatch.setattr(settings, 'voice_tts_idle_timeout_seconds', 0.04)
    monkeypatch.setattr(api.agent, 'respond', lambda *args: AgentDecision(kind='answer', spoken_text='One answer.'))
    monkeypatch.setattr(api.transcripts, 'append', lambda *args: None)
    with TestClient(app) as client, client.websocket_connect('/v1/voice', headers={'origin':'http://localhost:5173'}) as websocket:
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_json({'type':'user_text', 'text':'Hello', 'language':'en'})
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event)
            if event.get('state') == 'listening':
                break
        assert events[0]['state'] == 'thinking'
        response_id = events[0]['response_id']
        assert all(event['response_id'] == response_id for event in events)
        unavailable = next(event for event in events if event['type'] == 'audio_unavailable')
        assert unavailable['reason'] == reason and unavailable['recoverable'] is True
        assert closed


def test_superseded_business_turn_cannot_speak_or_reset_new_turn(monkeypatch):
    from threading import Event

    import app.api.app as api

    entered = Event()
    release = Event()
    class FakeSTT:
        async def is_ready(self):
            return True
    class FakeTTS:
        async def synthesize_stream(self, text, language):
            yield AudioChunk(sequence=0, audio=text.encode(), language=language)
    def respond(conversation_id, text, language):
        if text == 'first':
            entered.set()
            assert release.wait(2)
        return AgentDecision(kind='answer', spoken_text=text)
    monkeypatch.setattr(api, 'stt', FakeSTT())
    monkeypatch.setattr(api, 'tts', FakeTTS())
    monkeypatch.setattr(api.agent, 'respond', respond)
    monkeypatch.setattr(api.transcripts, 'append', lambda *args: None)
    with TestClient(app) as client, client.websocket_connect('/v1/voice', headers={'origin':'http://localhost:5173'}) as websocket:
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_json({'type':'user_text','text':'first'})
        first = websocket.receive_json()
        assert entered.wait(2)
        websocket.send_json({'type':'user_text','text':'second'})
        second = websocket.receive_json()
        assert second['state'] == 'thinking' and second['response_id'] > first['response_id']
        release.set()
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event)
            if event.get('state') == 'listening':
                break
        assert all(event['response_id'] == second['response_id'] for event in events)
        assert next(event for event in events if event['type'] == 'agent_response')['decision']['spoken_text'] == 'second'


def test_stt_unexpected_completion_can_restart_without_dead_queue(monkeypatch):
    import app.api.app as api

    calls = []
    class EndingSTT:
        async def is_ready(self):
            return True
        async def stream(self, audio):
            calls.append(True)
            if False:
                yield
    monkeypatch.setattr(api, 'stt', EndingSTT())
    with TestClient(app) as client, client.websocket_connect('/v1/voice', headers={'origin':'http://localhost:5173'}) as websocket:
        _authenticate_voice_socket(websocket, _voice_ticket())
        for _ in range(2):
            websocket.send_json({'type':'audio_start','sample_rate':16000})
            assert websocket.receive_json()['audio_started'] is True
            event = websocket.receive_json()
            assert event['type'] == 'stt_unavailable'
            assert event['reason'] == 'stt_stream_ended'
            assert event['recoverable'] is True and event['restart_required'] is True
        assert len(calls) == 2


def test_stt_stream_drop_recovers_on_next_live_audio_frame(monkeypatch):
    import app.api.app as api

    monkeypatch.setattr(
        api,
        "voice_sessions",
        VoiceSessionService(
            f"stt-recovery-test-key-{uuid4()}",
            issue_limit=50,
            max_active_total=100,
            max_active_per_client=50,
        ),
    )
    calls = []

    class RecoveringSTT:
        async def is_ready(self):
            return True

        async def stream(self, audio):
            calls.append(True)
            if len(calls) == 1:
                return
            async for frame in audio:
                if frame:
                    continue
                if False:
                    yield

    monkeypatch.setattr(api, "stt", RecoveringSTT())
    with TestClient(app) as client, client.websocket_connect(
        "/v1/voice", headers={"origin": "http://localhost:5173"}
    ) as websocket:
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        assert websocket.receive_json()["audio_started"] is True
        assert websocket.receive_json()["type"] == "stt_unavailable"

        websocket.send_bytes(b"\x01\x00" * 160)
        recovery = websocket.receive_json()
        assert recovery["type"] == "state"
        assert recovery["audio_recovered"] is True
        assert recovery["audio_started"] is True
        assert len(calls) == 2

        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        acknowledgement = websocket.receive_json()
        assert acknowledgement["type"] == "state"
        assert acknowledgement["audio_started"] is True
        assert len(calls) == 2


def test_hybrid_voice_retries_a_quick_deepgram_startup_timeout(monkeypatch) -> None:
    import app.api.app as api
    from app.integrations.stt.deepgram import DeepgramStreamingSTT, STTProviderError

    class FlakyDeepgramSTT(DeepgramStreamingSTT):
        def __init__(self) -> None:
            super().__init__(api_key="test-key")
            self.attempts = 0

        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            self.attempts += 1
            if self.attempts == 1:
                raise STTProviderError("temporary connect timeout", code="provider_timeout")
            if self.on_transport_ready is not None:
                self.on_transport_ready()
            async for _frame in audio:
                pass
            if False:
                yield STTEvent()

    provider = FlakyDeepgramSTT()
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda _config: provider)
    issued = api.voice_sessions.issue(
        "testclient", "http://localhost:5173", "hybrid"
    )
    assert issued is not None

    with TestClient(app) as client, client.websocket_connect(
        "/v1/voice", headers={"origin": "http://localhost:5173"}
    ) as websocket:
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        events = []
        while not any(event.get("audio_started") is True for event in events):
            events.append(_receive_json_timeout(websocket))

    assert provider.attempts == 2
    assert not any(event.get("type") == "stt_unavailable" for event in events)


def test_hybrid_voice_does_not_retry_a_permanent_deepgram_startup_failure(
    monkeypatch,
) -> None:
    import app.api.app as api
    from app.integrations.stt.deepgram import DeepgramStreamingSTT, STTProviderError

    class RejectedDeepgramSTT(DeepgramStreamingSTT):
        def __init__(self) -> None:
            super().__init__(api_key="test-key")
            self.attempts = 0

        async def is_ready(self) -> bool:
            return True

        async def stream(self, audio):
            del audio
            self.attempts += 1
            raise STTProviderError("credentials rejected", code="provider_auth_rejected")
            yield STTEvent()  # pragma: no cover

    provider = RejectedDeepgramSTT()
    monkeypatch.setattr(api, "build_urdu_hybrid_stt", lambda _config: provider)
    issued = api.voice_sessions.issue(
        "testclient", "http://localhost:5173", "hybrid"
    )
    assert issued is not None

    with TestClient(app) as client, client.websocket_connect(
        "/v1/voice", headers={"origin": "http://localhost:5173"}
    ) as websocket:
        _authenticate_voice_socket(websocket, issued[0])
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        events = []
        while not any(event.get("type") == "stt_unavailable" for event in events):
            events.append(_receive_json_timeout(websocket))

    assert provider.attempts == 1
    assert next(event for event in events if event.get("type") == "stt_unavailable")[
        "reason"
    ] == "stt_provider_auth_rejected"


@pytest.mark.parametrize(
    ("provider_message", "expected_reason", "expected_recoverable"),
    (
        ("provider failure", "stt_provider_error", True),
        ("HTTP 401 unauthorized private-test-secret", "stt_provider_auth_rejected", False),
        ("insufficient_quota.credit_balance_exhausted", "stt_provider_insufficient_credits", False),
        ("HTTP 429 too many requests rate limit", "stt_provider_rate_limited", False),
    ),
)
def test_stt_provider_failure_after_normal_audio_end_is_reported(
    monkeypatch, provider_message: str, expected_reason: str, expected_recoverable: bool
):
    import app.api.app as api

    monkeypatch.setattr(
        api,
        "voice_sessions",
        VoiceSessionService(
            f"provider-error-test-key-{uuid4()}",
            issue_limit=50,
            max_active_total=100,
            max_active_per_client=50,
        ),
    )

    class FailingSTT:
        async def is_ready(self):
            return True

        async def stream(self, audio):
            async for _ in audio:
                pass
            raise RuntimeError(provider_message)
            yield

    monkeypatch.setattr(api, "stt", FailingSTT())
    with TestClient(app) as client, client.websocket_connect(
        "/v1/voice", headers={"origin": "http://localhost:5173"}
    ) as websocket:
        _authenticate_voice_socket(websocket, _voice_ticket())
        websocket.send_json({"type": "audio_start", "sample_rate": 16_000})
        assert websocket.receive_json()["audio_started"] is True
        websocket.send_json({"type": "audio_end"})
        event = websocket.receive_json()
        while event.get("type") != "stt_unavailable":
            event = websocket.receive_json()
        assert event["type"] == "stt_unavailable"
        assert event["reason"] == expected_reason
        assert "private-test-secret" not in str(event)
        assert event["recoverable"] is expected_recoverable
        assert event["restart_required"] is True
