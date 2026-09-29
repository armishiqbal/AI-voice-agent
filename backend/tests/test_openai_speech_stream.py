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
    stream = OpenAISpeechProvider("test-key", model="gpt-4o-mini-tts").synthesize_stream("Hello", "en")
    first = await anext(stream)
    assert first.audio == b"\x01\x02"
    assert reads == [1]
    remaining = [chunk async for chunk in stream]
    assert b"".join(c.audio for c in [first, *remaining]) == b"\x01\x02\x03\x04" + b"\x00" * 5000
    assert all(len(c.audio) <= 2048 and len(c.audio) % 2 == 0 for c in remaining)
    assert [c.sequence for c in [first, *remaining]] == list(range(1 + len(remaining)))


@pytest.mark.asyncio
async def test_tts_1_streams_mp3_chunks_without_pcm_or_instruction_assumptions(monkeypatch) -> None:
    requests = []

    class Response:
        status_code = 200

        async def aiter_bytes(self):
            yield b"mp3-first"
            yield b"mp3-second"

    class Client:
        def __init__(self, **kwargs):
            pass

        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            requests.append(kwargs)
            yield Response()

        async def aclose(self):
            pass

    monkeypatch.setattr("app.integrations.tts.openai.httpx.AsyncClient", Client)
    provider = OpenAISpeechProvider("test-key", model="tts-1", voice="alloy")
    chunks = [chunk async for chunk in provider.synthesize_stream("Hello", "en")]

    assert requests[0]["json"]["response_format"] == "mp3"
    assert "instructions" not in requests[0]["json"]
    assert [chunk.audio for chunk in chunks] == [b"mp3-first", b"mp3-second"]
    assert all(chunk.encoding == "audio/mpeg" for chunk in chunks)
    assert all(chunk.sample_rate == 24_000 for chunk in chunks)
    await provider.aclose()


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
        _ = [
            chunk
            async for chunk in OpenAISpeechProvider("test", model="gpt-4o-mini-tts").synthesize_stream(
                "Hello", "en"
            )
        ]


@pytest.mark.asyncio
async def test_speech_reuses_http_connection_pool_and_closes_it_on_shutdown(monkeypatch) -> None:
    instances = []

    class Response:
        status_code = 200

        async def aiter_bytes(self):
            yield b"\x01\x02"

    class Client:
        def __init__(self, **kwargs):
            self.closed = False
            self.options = kwargs
            instances.append(self)

        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield Response()

        async def aclose(self):
            self.closed = True

    monkeypatch.setattr("app.integrations.tts.openai.httpx.AsyncClient", Client)
    provider = OpenAISpeechProvider("test-key")
    for _ in range(2):
        chunks = [chunk async for chunk in provider.synthesize_stream("Hello", "en")]
        assert chunks[0].audio == b"\x01\x02"

    assert len(instances) == 1
    assert instances[0].options["limits"].keepalive_expiry == 120.0
    assert instances[0].closed is False
    await provider.aclose()
    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_transport_warmup_reuses_speech_client_and_is_cached(monkeypatch) -> None:
    instances = []
    requests = []

    class Response:
        status_code = 200

    class Client:
        def __init__(self, **kwargs):
            instances.append(self)

        async def get(self, url, **kwargs):
            requests.append((url, kwargs))
            return Response()

        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield type("AudioResponse", (), {
                "status_code": 200,
                "aiter_bytes": lambda self: _audio_bytes(),
            })()

        async def aclose(self):
            pass

    async def _audio_bytes():
        yield b"\x01\x02"

    monkeypatch.setattr("app.integrations.tts.openai.httpx.AsyncClient", Client)
    provider = OpenAISpeechProvider("test-key", model="gpt-4o-mini-tts")

    assert await provider.warmup() is True
    assert await provider.warmup() is True
    audio = [chunk async for chunk in provider.synthesize_stream("Ji bilkul.", "ur-Latn")]

    assert len(instances) == 1
    assert len(requests) == 1
    assert requests[0][0].endswith("/v1/models/gpt-4o-mini-tts")
    assert requests[0][1]["headers"]["Authorization"] == "Bearer test-key"
    assert audio[0].audio == b"\x01\x02"
    await provider.aclose()


@pytest.mark.asyncio
async def test_transport_warmup_failure_is_nonfatal_and_not_cached(monkeypatch) -> None:
    attempts = []

    class Response:
        status_code = 401

    class Client:
        def __init__(self, **kwargs):
            pass

        async def get(self, url, **kwargs):
            attempts.append(url)
            return Response()

        async def aclose(self):
            pass

    monkeypatch.setattr("app.integrations.tts.openai.httpx.AsyncClient", Client)
    provider = OpenAISpeechProvider("test-key")
    assert await provider.warmup() is False
    assert await provider.warmup() is False
    assert len(attempts) == 2
    await provider.aclose()
