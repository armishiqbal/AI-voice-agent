import base64
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.domain.models import AgentDecision
from app.integrations.providers import provider_readiness
from app.integrations.stt import STTEvent
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
            async for _ in audio:
                yield STTEvent(
                    text="Find a home in Lahore",
                    language="en-US",
                    confidence=0.99,
                    is_final=True,
                    speech_final=True,
                )
                return

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
