import asyncio
import base64
import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.domain.models import AgentDecision
from app.integrations.providers import provider_readiness
from app.integrations.stt import STTEvent, STTProviderError
from app.integrations.telephony import (
    TelephonyProviderError,
    TwilioTelephonyAdapter,
    UnavailableTelephonyAdapter,
    build_telephony_adapter,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    resample_pcm16,
)
from app.integrations.tts import AudioChunk


@pytest.mark.asyncio
async def test_telephony_boundary_fails_closed_without_carrier() -> None:
    with pytest.raises(TelephonyProviderError, match="not configured"):
        await UnavailableTelephonyAdapter().start_session("+923001234567")


@pytest.mark.asyncio
async def test_twilio_outbound_call_uses_server_credentials_and_returns_media_url(
    monkeypatch,
) -> None:
    import httpx

    calls: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"sid": "CA123"}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data, auth):
            calls.update(url=url, data=data, auth=auth)
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    session = await adapter.start_session("+923001234567")
    assert session.call_id == "CA123"
    assert session.websocket_url == "wss://voice.example.com/v1/telephony/media"
    assert calls["auth"] == ("AC123", "secret")
    assert calls["data"]["To"] == "+923001234567"


def test_twilio_signature_and_twiML_are_deterministic() -> None:
    url = "https://voice.example.com/v1/telephony/inbound"
    params = {"CallSid": "CA123", "From": "+923001234567"}
    canonical = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    signature = base64.b64encode(
        hmac.new(b"secret", canonical.encode(), hashlib.sha1).digest()
    ).decode()
    assert TwilioTelephonyAdapter.verify_signature(url, params, signature, "secret")
    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    twiml = adapter.inbound_twiml()
    assert "wss://voice.example.com/v1/telephony/media" in twiml
    assert "/v1/telephony/media?" not in twiml
    assert "<Connect><Stream" in twiml


def test_twilio_websocket_signature_accepts_documented_trailing_slash_variant() -> None:
    url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(hmac.new(b"secret", url.encode(), hashlib.sha1).digest()).decode()
    assert TwilioTelephonyAdapter.verify_websocket_signature(
        url.removesuffix("/"), signature, "secret"
    )
    assert not TwilioTelephonyAdapter.verify_websocket_signature(
        url.removesuffix("/"), signature, "wrong-secret"
    )


def test_media_websocket_accepts_twilio_signed_handshake(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()

    with TestClient(api.app).websocket_connect(
        "/v1/telephony/media", headers={"x-twilio-signature": signature}
    ) as websocket:
        websocket.send_json({"event": "stop"})


def test_media_websocket_rejects_invalid_twilio_signature(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    client = TestClient(api.app)
    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/v1/telephony/media", headers={"x-twilio-signature": "invalid"}),
    ):
        pass
    assert disconnected.value.code == 1008


def test_media_websocket_measures_caller_turn_but_not_initial_greeting(monkeypatch) -> None:
    import app.api.app as api

    measurements: dict[str, list[float]] = {}

    class FakeSTT:
        async def stream(self, audio):
            yielded_final = False
            async for _ in audio:
                if yielded_final:
                    continue
                yielded_final = True
                yield STTEvent(
                    text="Find a home in Lahore",
                    language="en-US",
                    confidence=0.99,
                    is_final=True,
                    speech_final=True,
                )

    class FakeTTS:
        async def synthesize_stream(self, text: str, language: str):
            del text
            yield AudioChunk(
                sequence=1,
                audio=b"\x00\x00" * 160,
                language=language,
                sample_rate=8_000,
            )

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    class CallLeases:
        def __init__(self):
            self.released: list[str] = []

        def renew_external_lease(self, lease_id: str) -> bool:
            return lease_id == "twilio:CA123"

        def release_external_lease(self, lease_id: str) -> None:
            self.released.append(lease_id)

    leases = CallLeases()
    monkeypatch.setattr(api, "voice_sessions", leases)
    monkeypatch.setattr(api, "stt", FakeSTT())
    monkeypatch.setattr(api, "tts", FakeTTS())
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="I can help with that."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    monkeypatch.setattr(
        api.traces,
        "observe",
        lambda name, value, limit=1000: measurements.setdefault(name, []).append(value),
    )
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()

    with TestClient(api.app).websocket_connect(
        "/v1/telephony/media", headers={"x-twilio-signature": signature}
    ) as websocket:
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        assert websocket.receive_json()["event"] == "media"  # Initial greeting audio.
        websocket.send_json(
            {
                "event": "media",
                "media": {"payload": base64.b64encode(b"\xff" * 160).decode("ascii")},
            }
        )
        assert websocket.receive_json()["event"] == "media"  # Response to the caller turn.
        websocket.send_json({"event": "stop"})

    assert len(measurements["voice.final_transcript_to_first_audio_ms"]) == 1
    assert measurements["voice.final_transcript_to_first_audio_ms"][0] >= 0
    assert len(measurements["voice.tts_first_audio_latency_ms"]) == 2
    assert len(measurements["voice.tts_stream_duration_ms"]) == 2
    assert leases.released == ["twilio:CA123"]


def test_twilio_speaks_retry_after_transient_stt_failure_then_answers(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    class CallLeases:
        def __init__(self):
            self.released: list[str] = []

        def renew_external_lease(self, lease_id: str) -> bool:
            return lease_id == "twilio:CA123"

        def release_external_lease(self, lease_id: str) -> None:
            self.released.append(lease_id)

    class RecoveringSTT:
        def __init__(self):
            self.calls = 0

        async def stream(self, audio):
            self.calls += 1
            if self.calls == 1:
                raise STTProviderError("temporary timeout", code="provider_timeout")
                yield STTEvent(text="", is_final=False)
            yielded_final = False
            async for _frame in audio:
                if not yielded_final:
                    yielded_final = True
                    yield STTEvent(
                        text="Find a home in Lahore",
                        language="en-US",
                        confidence=0.99,
                        is_final=True,
                        speech_final=True,
                    )

    class FakeTTS:
        def __init__(self):
            self.spoken_text: list[str] = []

        async def synthesize_stream(self, text: str, language: str):
            self.spoken_text.append(text)
            yield AudioChunk(
                sequence=1,
                audio=b"\x00\x00" * 160,
                language=language,
                sample_rate=8_000,
            )

    leases = CallLeases()
    stt_provider = RecoveringSTT()
    speech = FakeTTS()
    transcript_events: list[tuple[object, ...]] = []
    monkeypatch.setattr(api, "voice_sessions", leases)
    monkeypatch.setattr(api, "stt", stt_provider)
    monkeypatch.setattr(api, "tts", speech)
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="I can help with Lahore homes."),
    )
    monkeypatch.setattr(
        api.transcripts, "append", lambda *args: transcript_events.append(args)
    )
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()
    client = TestClient(api.app)

    with client.websocket_connect(
        "/v1/telephony/media", headers={"x-twilio-signature": signature}
    ) as websocket:
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        assert websocket.receive_json()["event"] == "media"
        websocket.send_json(
            {
                "event": "media",
                "media": {"payload": base64.b64encode(b"\xff" * 160).decode("ascii")},
            }
        )
        for _ in range(3):
            assert websocket.receive_json()["event"] == "media"
            if "I can help with Lahore homes." in speech.spoken_text:
                break
        websocket.send_json({"event": "stop"})

    assert stt_provider.calls == 2
    assert any("poori baat" in text for text in speech.spoken_text)
    assert "I can help with Lahore homes." in speech.spoken_text
    assert [item[2] for item in transcript_events if item[1] == "user"] == [
        "Find a home in Lahore"
    ]
    assert leases.released == ["twilio:CA123"]


def test_twilio_speaks_provider_failure_before_closing_call(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    class CallLeases:
        def __init__(self):
            self.released: list[str] = []

        def renew_external_lease(self, lease_id: str) -> bool:
            return lease_id == "twilio:CA123"

        def release_external_lease(self, lease_id: str) -> None:
            self.released.append(lease_id)

    class RejectedSTT:
        def __init__(self):
            self.calls = 0

        async def stream(self, audio):
            del audio
            self.calls += 1
            raise STTProviderError("provider rejected credentials", code="provider_auth_rejected")
            yield STTEvent(text="", is_final=False)

    class FakeTTS:
        def __init__(self):
            self.spoken_text: list[str] = []

        async def synthesize_stream(self, text: str, language: str):
            self.spoken_text.append(text)
            yield AudioChunk(
                sequence=1,
                audio=b"\x00\x00" * 160,
                language=language,
                sample_rate=8_000,
            )

    leases = CallLeases()
    stt_provider = RejectedSTT()
    speech = FakeTTS()
    monkeypatch.setattr(api, "voice_sessions", leases)
    monkeypatch.setattr(api, "stt", stt_provider)
    monkeypatch.setattr(api, "tts", speech)
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()
    client = TestClient(api.app)

    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/v1/telephony/media", headers={"x-twilio-signature": signature}) as websocket,
    ):
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        assert websocket.receive_json()["event"] == "media"
        websocket.receive_json()

    assert disconnected.value.code == 1011
    assert stt_provider.calls == 1
    assert any("Maazrat" in text for text in speech.spoken_text)
    assert leases.released == ["twilio:CA123"]


def test_twilio_speaks_safe_message_when_agent_processing_fails(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    class CallLeases:
        def __init__(self):
            self.released: list[str] = []

        def renew_external_lease(self, lease_id: str) -> bool:
            return lease_id == "twilio:CA123"

        def release_external_lease(self, lease_id: str) -> None:
            self.released.append(lease_id)

    class WaitingSTT:
        async def stream(self, audio):
            async for _frame in audio:
                yield STTEvent(text="", is_final=False)

    class FakeTTS:
        def __init__(self):
            self.spoken_text: list[str] = []

        async def synthesize_stream(self, text: str, language: str):
            self.spoken_text.append(text)
            yield AudioChunk(
                sequence=1,
                audio=b"\x00\x00" * 160,
                language=language,
                sample_rate=8_000,
            )

    leases = CallLeases()
    speech = FakeTTS()
    transcript_events: list[tuple[object, ...]] = []

    def fail_agent(*args):
        del args
        raise RuntimeError("sensitive upstream detail")

    monkeypatch.setattr(api, "voice_sessions", leases)
    monkeypatch.setattr(api, "stt", WaitingSTT())
    monkeypatch.setattr(api, "tts", speech)
    monkeypatch.setattr(api.agent, "respond", fail_agent)
    monkeypatch.setattr(
        api.transcripts, "append", lambda *args: transcript_events.append(args)
    )
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()
    client = TestClient(api.app)

    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/v1/telephony/media", headers={"x-twilio-signature": signature}) as websocket,
    ):
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        assert websocket.receive_json()["event"] == "media"
        websocket.receive_json()

    assert disconnected.value.code == 1011
    assert any("Maazrat" in text for text in speech.spoken_text)
    assert all("sensitive upstream detail" not in str(item) for item in transcript_events)
    assert leases.released == ["twilio:CA123"]


def test_twilio_speaks_repeat_prompt_for_low_confidence_without_using_partial_text(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")
    monkeypatch.setattr(api.settings, "stt_min_confidence", 0.8)

    class CallLeases:
        def __init__(self):
            self.released: list[str] = []

        def renew_external_lease(self, lease_id: str) -> bool:
            return lease_id == "twilio:CA123"

        def release_external_lease(self, lease_id: str) -> None:
            self.released.append(lease_id)

    class LowConfidenceThenFinalSTT:
        def __init__(self):
            self.turns = 0

        async def stream(self, audio):
            async for _frame in audio:
                if self.turns == 0:
                    self.turns = 1
                    yield STTEvent(
                        text="private unclear words",
                        language="ur-Latn",
                        confidence=0.2,
                        is_final=True,
                        speech_final=True,
                    )
                elif self.turns == 1:
                    self.turns = 2
                    yield STTEvent(
                        text="Lahore mein ghar chahiye",
                        language="ur-Latn",
                        confidence=0.99,
                        is_final=True,
                        speech_final=True,
                    )

    class FakeTTS:
        def __init__(self):
            self.spoken_text: list[str] = []

        async def synthesize_stream(self, text: str, language: str):
            self.spoken_text.append(text)
            yield AudioChunk(
                sequence=1,
                audio=b"\x00\x00" * 160,
                language=language,
                sample_rate=8_000,
            )

    leases = CallLeases()
    speech = FakeTTS()
    transcript_events: list[tuple[object, ...]] = []
    monkeypatch.setattr(api, "voice_sessions", leases)
    monkeypatch.setattr(api, "stt", LowConfidenceThenFinalSTT())
    monkeypatch.setattr(api, "tts", speech)
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="I can help with Lahore homes."),
    )
    monkeypatch.setattr(
        api.transcripts, "append", lambda *args: transcript_events.append(args)
    )
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()
    client = TestClient(api.app)
    caller_audio = {
        "event": "media",
        "media": {"payload": base64.b64encode(b"\xff" * 160).decode("ascii")},
    }

    with client.websocket_connect(
        "/v1/telephony/media", headers={"x-twilio-signature": signature}
    ) as websocket:
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        assert websocket.receive_json()["event"] == "media"
        websocket.send_json(caller_audio)
        assert websocket.receive_json()["event"] == "media"
        websocket.send_json(caller_audio)
        assert websocket.receive_json()["event"] == "media"
        websocket.send_json({"event": "stop"})

    assert any("poori baat" in text for text in speech.spoken_text)
    caller_transcripts = [item[2] for item in transcript_events if item[1] == "user"]
    assert "private unclear words" not in caller_transcripts
    assert "Lahore mein ghar chahiye" in caller_transcripts
    assert leases.released == ["twilio:CA123"]


def test_twilio_inbound_reserves_shared_capacity_and_returns_busy_twiml(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    class CallLeases:
        def __init__(self, available: bool):
            self.available = available
            self.reservations: list[tuple[str, str]] = []

        def acquire_external_lease(self, lease_id: str, caller: str) -> bool:
            self.reservations.append((lease_id, caller))
            return self.available

    body = b"CallSid=CA123&From=%2B923001234567"
    params = {"CallSid": "CA123", "From": "+923001234567"}
    canonical = "https://voice.example.com/v1/telephony/inbound" + "".join(
        f"{key}{params[key]}" for key in sorted(params)
    )
    signature = base64.b64encode(
        hmac.new(b"secret", canonical.encode(), hashlib.sha1).digest()
    ).decode()
    headers = {"x-twilio-signature": signature, "content-type": "application/x-www-form-urlencoded"}

    leases = CallLeases(available=True)
    monkeypatch.setattr(api, "voice_sessions", leases)
    response = TestClient(api.app).post("/v1/telephony/inbound", content=body, headers=headers)
    assert response.status_code == 200
    assert "<Connect><Stream" in response.text
    assert leases.reservations == [("twilio:CA123", "+923001234567")]

    full = CallLeases(available=False)
    monkeypatch.setattr(api, "voice_sessions", full)
    busy = TestClient(api.app).post("/v1/telephony/inbound", content=body, headers=headers)
    assert busy.status_code == 200
    assert "helping other callers" in busy.text
    assert "<Hangup/>" in busy.text


def test_twilio_media_stream_requires_an_inbound_capacity_reservation(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    class CallLeases:
        def renew_external_lease(self, lease_id: str) -> bool:
            return False

        def release_external_lease(self, lease_id: str) -> None:
            raise AssertionError("an unreserved call must not release another caller's lease")

    monkeypatch.setattr(api, "voice_sessions", CallLeases())
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()
    client = TestClient(api.app)
    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/v1/telephony/media", headers={"x-twilio-signature": signature}) as websocket,
    ):
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        websocket.receive_json()
    assert disconnected.value.code == 1013


def test_twilio_media_rejects_invalid_base64_and_releases_its_lease(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    class CallLeases:
        def __init__(self):
            self.released: list[str] = []

        def renew_external_lease(self, lease_id: str) -> bool:
            return lease_id == "twilio:CA123"

        def release_external_lease(self, lease_id: str) -> None:
            self.released.append(lease_id)

    class BlockingSTT:
        async def stream(self, audio):
            async for _frame in audio:
                await asyncio.Event().wait()
                yield STTEvent(text="", is_final=False)

    class FakeTTS:
        async def synthesize_stream(self, text: str, language: str):
            del text
            yield AudioChunk(
                sequence=1,
                audio=b"\x00\x00" * 160,
                language=language,
                sample_rate=8_000,
            )

    leases = CallLeases()
    monkeypatch.setattr(api, "voice_sessions", leases)
    monkeypatch.setattr(api, "stt", BlockingSTT())
    monkeypatch.setattr(api, "tts", FakeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="Hello."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()
    client = TestClient(api.app)

    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/v1/telephony/media", headers={"x-twilio-signature": signature}) as websocket,
    ):
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        assert websocket.receive_json()["event"] == "media"
        websocket.send_json({"event": "media", "media": {"payload": "%%%invalid%%%"}})
        websocket.receive_json()

    assert disconnected.value.code == 1003
    assert leases.released == ["twilio:CA123"]


def test_twilio_media_closes_when_the_stt_audio_queue_is_full(monkeypatch) -> None:
    import app.api.app as api

    adapter = TwilioTelephonyAdapter("AC123", "secret", "+15005550006", "https://voice.example.com")
    monkeypatch.setattr(api, "telephony", adapter)
    monkeypatch.setattr(api.settings, "app_env", "production")
    monkeypatch.setattr(api.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(api.settings, "telephony_public_base_url", "https://voice.example.com")

    class CallLeases:
        def __init__(self):
            self.released: list[str] = []

        def renew_external_lease(self, lease_id: str) -> bool:
            return lease_id == "twilio:CA123"

        def release_external_lease(self, lease_id: str) -> None:
            self.released.append(lease_id)

    class BlockingSTT:
        async def stream(self, audio):
            async for _frame in audio:
                await asyncio.Event().wait()
                yield STTEvent(text="", is_final=False)

    class FakeTTS:
        async def synthesize_stream(self, text: str, language: str):
            del text
            yield AudioChunk(
                sequence=1,
                audio=b"\x00\x00" * 160,
                language=language,
                sample_rate=8_000,
            )

    leases = CallLeases()
    monkeypatch.setattr(api, "voice_sessions", leases)
    monkeypatch.setattr(api, "stt", BlockingSTT())
    monkeypatch.setattr(api, "tts", FakeTTS())
    monkeypatch.setattr(
        api.agent,
        "respond",
        lambda *args: AgentDecision(kind="answer", spoken_text="Hello."),
    )
    monkeypatch.setattr(api.transcripts, "append", lambda *args: None)
    signed_url = "https://voice.example.com/v1/telephony/media/"
    signature = base64.b64encode(
        hmac.new(b"secret", signed_url.encode(), hashlib.sha1).digest()
    ).decode()
    media_payload = base64.b64encode(b"\xff" * 160).decode("ascii")
    client = TestClient(api.app)

    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        client.websocket_connect("/v1/telephony/media", headers={"x-twilio-signature": signature}) as websocket,
    ):
        websocket.send_json({"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA123"}})
        assert websocket.receive_json()["event"] == "media"
        websocket.send_json({"event": "media", "media": {"payload": media_payload}})
        time.sleep(0.05)  # Let the STT consumer take one frame and remain stalled on it.
        for _ in range(101):
            websocket.send_json({"event": "media", "media": {"payload": media_payload}})
        websocket.receive_json()

    assert disconnected.value.code == 1013
    assert leases.released == ["twilio:CA123"]


def test_twilio_readiness_requires_complete_server_configuration() -> None:
    incomplete = Settings(telephony_provider="twilio", twilio_account_sid="AC123")
    assert not provider_readiness(incomplete).telephony
    adapter = build_telephony_adapter(incomplete)
    with pytest.raises(TelephonyProviderError, match="requires"):
        # The adapter must not create a fake call when a secret or public URL is absent.
        import asyncio

        asyncio.run(adapter.start_session("+923001234567"))


def test_twilio_pcm16_and_mulaw_codec_round_trip_has_bounded_error() -> None:
    original = (b"\x00\x00" * 8) + (b"\xff\x1f" * 8) + (b"\x00\x80" * 8)
    encoded = pcm16_to_mulaw(original)
    decoded = mulaw_to_pcm16(encoded)
    assert len(encoded) == len(original) // 2
    assert len(decoded) == len(original)
    upsampled = resample_pcm16(decoded, 8_000, 16_000)
    assert len(upsampled) == len(decoded) * 2
