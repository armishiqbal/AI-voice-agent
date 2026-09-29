import asyncio
import base64
import json

import pytest

from app.integrations.tts.openai_realtime import (
    OpenAIRealtimeSpeechProvider,
    _is_spoken_exactly,
    _is_spoken_prefix,
)
from app.integrations.tts.router import TTSProviderError


class FakeConnection:
    def __init__(self, response_events):
        self.events = [json.dumps({"type": "session.updated"})]
        self.response_events = list(response_events)
        self.sent = []
        self.closed = False

    async def send(self, payload):
        message = json.loads(payload)
        self.sent.append(message)
        if message.get("type") == "response.create":
            self.events.extend(json.dumps(event) for event in self.response_events)

    async def recv(self):
        if not self.events:
            raise RuntimeError("No fake provider event is available")
        return self.events.pop(0)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_realtime_tts_reuses_session_and_streams_only_verified_pcm(monkeypatch):
    phrase = "Hello, Karachi."
    pcm = b"\x01\x00\x02\x00"
    connection = FakeConnection(
        [
            {"type": "response.output_audio_transcript.delta", "delta": "Hello"},
            {
                "type": "response.output_audio.delta",
                "delta": base64.b64encode(pcm).decode("ascii"),
            },
            {"type": "response.output_audio_transcript.delta", "delta": ", Karachi"},
            {
                "type": "response.output_audio_transcript.done",
                "transcript": phrase,
            },
            {
                "type": "response.done",
                "response": {"status": "completed"},
            },
        ]
    )
    connections = []

    async def fake_connect(*args, **kwargs):
        connections.append(kwargs)
        return connection

    monkeypatch.setattr("websockets.asyncio.client.connect", fake_connect)
    provider = OpenAIRealtimeSpeechProvider("test-key")

    first = [chunk async for chunk in provider.synthesize_stream(phrase, "en")]
    second = [chunk async for chunk in provider.synthesize_stream(phrase, "en")]

    assert len(connections) == 1
    assert first[0].audio == pcm
    assert first[0].encoding == "pcm_s16le"
    assert first[-1].is_final
    assert second[0].sequence == 0
    assert second[-1].is_final
    assert connection.closed is False
    await provider.aclose()
    assert connection.closed is True


@pytest.mark.asyncio
async def test_realtime_tts_rejects_unapproved_text_before_emitting_audio(monkeypatch):
    connection = FakeConnection(
        [
            {"type": "response.output_audio_transcript.delta", "delta": "Added advice"},
            {
                "type": "response.output_audio.delta",
                "delta": base64.b64encode(b"\x01\x00").decode("ascii"),
            },
        ]
    )

    async def fake_connect(*args, **kwargs):
        return connection

    monkeypatch.setattr("websockets.asyncio.client.connect", fake_connect)
    provider = OpenAIRealtimeSpeechProvider("test-key")
    stream = provider.synthesize_stream("Verified listings are unavailable.", "en")

    with pytest.raises(TTSProviderError, match="approved text"):
        await anext(stream)

    assert any(message.get("type") == "response.cancel" for message in connection.sent)
    assert connection.closed is True


@pytest.mark.asyncio
async def test_realtime_tts_fails_fast_when_no_first_audio_arrives(monkeypatch):
    class StalledConnection(FakeConnection):
        async def recv(self):
            if self.events:
                return self.events.pop(0)
            await asyncio.Future()

    connection = StalledConnection([])

    async def fake_connect(*args, **kwargs):
        return connection

    monkeypatch.setattr("websockets.asyncio.client.connect", fake_connect)
    provider = OpenAIRealtimeSpeechProvider(
        "test-key", response_timeout_seconds=1, first_audio_timeout_seconds=0.01
    )

    with pytest.raises(TTSProviderError, match="first audio"):
        _ = [chunk async for chunk in provider.synthesize_stream("Hello, Karachi.", "en")]

    assert connection.closed is True
    assert any(message.get("type") == "response.cancel" for message in connection.sent)


def test_spoken_text_validation_preserves_words_and_numbers():
    assert _is_spoken_prefix("Aap budget 5", "Aap budget 5 crore hai")
    assert _is_spoken_exactly("Aap budget 5 crore hai!", "Aap budget 5 crore hai.")
    assert not _is_spoken_exactly("Aap budget five crore hai", "Aap budget 5 crore hai")
