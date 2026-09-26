from contextlib import asynccontextmanager

import pytest

from app.integrations.tts.openai import OpenAISpeechProvider
from app.integrations.tts.router import TTSProviderError


@pytest.mark.asyncio
async def test_speech_yields_small_first_packet_before_requesting_more(monkeypatch) -> None:
    reads = []

    class Response:
        status_code = 200

        async def aiter_bytes(self):
            reads.append(1)
            yield b"\x01\x02\x03"
            reads.append(2)
            yield b"\x04" + b"\x00" * 5000

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield Response()

    monkeypatch.setattr("app.integrations.tts.openai.httpx.AsyncClient", Client)
    stream = OpenAISpeechProvider("test-key").synthesize_stream("Hello", "en")
    first = await anext(stream)
    assert first.audio == b"\x01\x02"
    assert reads == [1]
    remaining = [chunk async for chunk in stream]
    assert b"".join(c.audio for c in [first, *remaining]) == b"\x01\x02\x03\x04" + b"\x00" * 5000
    assert all(len(c.audio) <= 2048 and len(c.audio) % 2 == 0 for c in remaining)
    assert [c.sequence for c in [first, *remaining]] == list(range(1 + len(remaining)))


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,reason", [(b"", "no audio"), (b"\x01", "incomplete PCM")])
async def test_speech_rejects_empty_or_incomplete_audio(monkeypatch, payload, reason) -> None:
    class Response:
        status_code = 200

        async def aiter_bytes(self):
            yield payload

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield Response()

    monkeypatch.setattr("app.integrations.tts.openai.httpx.AsyncClient", Client)
    with pytest.raises(TTSProviderError, match=reason):
        _ = [chunk async for chunk in OpenAISpeechProvider("test").synthesize_stream("Hello", "en")]
