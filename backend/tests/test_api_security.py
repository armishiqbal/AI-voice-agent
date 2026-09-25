from pathlib import Path
from time import monotonic, sleep
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
from app.integrations.tts.router import AudioChunk
from app.repositories.database import SessionLocal
from app.repositories.records import OutboxEventRecord
from app.services.voice_sessions import VoiceSessionService


def _voice_ticket(origin: str = "http://localhost:5173") -> str:
    import app.api.app as api

    issued = api.voice_sessions.issue("testclient", origin)
    assert issued is not None
    return issued[0]


def _authenticate_voice_socket(websocket, ticket: str) -> dict[str, object]:
    websocket.send_json({"type": "authenticate", "ticket": ticket})
    return websocket.receive_json()


@pytest.fixture(autouse=True)
def isolate_voice_session_service(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.app as api

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
        "/v1/knowledge/ingest-file",
        "/v1/admin/metrics",
        "/v1/admin/evaluations/report",
        "/v1/admin/outbox",
        "/v1/admin/audit",
        "/v1/admin/call-outcomes",
    }
    for route in app.routes:
        if getattr(route, "path", None) in protected_paths:
            assert route.dependant.dependencies, f"{route.path} is missing an admin dependency"


def test_consent_bound_lead_form_remains_public() -> None:
    lead_routes = [route for route in app.routes if getattr(route, "path", None) == "/v1/leads"]
    assert lead_routes
    assert not lead_routes[0].dependant.dependencies


def test_readyz_separates_api_health_from_live_voice_readiness() -> None:
    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["status"] in {"ready", "degraded"}
    assert "database_ready" in readiness["application"]
    assert readiness["live_voice"]["status"] in {"configured", "blocked"}
    assert isinstance(readiness["live_voice"]["blockers"], list)
    assert readiness["live_voice"]["configured"] is (
        readiness["providers"]["standard_voice_ready"]
        or readiness["providers"]["openai_voice_ready"]
    )


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
            json={"mode": "openai"},
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

    monkeypatch.setattr(api.agent, "respond", respond)
    monkeypatch.setattr(api.transcripts, "append", lambda *args: retained.append(args))
    monkeypatch.setattr(api, "tts", EmptyTTS())
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
    assert measurements["voice.end_of_turn_to_first_audio_ms"]
    assert measurements["voice.tts_stream_duration_ms"]
    assert measurements["voice.end_of_turn_to_first_audio_ms"][0] >= 0
