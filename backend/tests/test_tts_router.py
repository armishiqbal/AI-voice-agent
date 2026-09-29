from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.integrations.tts import (
    AudioChunk,
    TTSProviderError,
    TTSRouter,
    detect_language,
    segment_text,
)
from app.integrations.tts.elevenlabs import ElevenLabsStreamingProvider
from app.integrations.tts.fish import FishAudioStreamingProvider


class MemoryTTS:
    name = "memory"

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, str | None]] = []
        self.fail = fail

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        self.calls.append((text, language, voice_id))
        if self.fail:
            raise TTSProviderError("provider unavailable")
        yield AudioChunk(sequence=0, audio=f"{language}:{text}".encode(), language=language)

    async def is_ready(self) -> bool:
        return not self.fail


def test_detect_language_handles_urdu_script_and_roman_urdu() -> None:
    assert detect_language("آپ کو گھر چاہیے") == "ur-Arab"
    assert detect_language("Mujhe Karachi mein ghar chahiye") == "ur-Latn"
    assert detect_language("Show me available homes") == "en"


def test_detects_additional_multilingual_scripts() -> None:
    assert detect_language("आप कैसे हैं") == "hi"
    assert detect_language("ਸਤ ਸ੍ਰੀ ਅਕਾਲ") == "pa"
    assert detect_language("আপনি কেমন আছেন") == "bn"
    assert segment_text("مرحبا بكم", "ar") == [("مرحبا بكم", "ar")]


def test_segment_text_preserves_code_switched_language_groups() -> None:
    assert segment_text("Mujhe Karachi mein house chahiye") == [
        ("Mujhe Karachi mein ", "ur-Latn"),
        ("house ", "en"),
        ("chahiye", "ur-Latn"),
    ]


def test_segment_text_routes_mixed_scripts_with_selected_roman_urdu() -> None:
    text = "آپ Karachi mein available گھر ہے"
    segments = segment_text(text, "ur-Latn")

    assert segments == [
        ("آپ ", "ur-Arab"),
        ("Karachi mein ", "ur-Latn"),
        ("available ", "en"),
        ("گھر ہے", "ur-Arab"),
    ]
    assert "".join(segment for segment, _ in segments) == text


@pytest.mark.asyncio
async def test_router_orders_chunks_and_marks_final() -> None:
    urdu = MemoryTTS()
    english = MemoryTTS()
    router = TTSRouter({"ur-Latn": urdu, "en": english})

    chunks = [chunk async for chunk in router.synthesize_stream("Mujhe Karachi mein house chahiye")]

    assert [chunk.sequence for chunk in chunks] == [0, 1, 2, 3]
    assert chunks[-1].is_final is True
    assert [call[1] for call in urdu.calls] == ["ur-Latn", "ur-Latn"]
    assert [call[1] for call in english.calls] == ["en"]


@pytest.mark.asyncio
async def test_router_uses_fallback_when_primary_fails() -> None:
    primary = MemoryTTS(fail=True)
    fallback = MemoryTTS()
    router = TTSRouter({"en": primary}, fallback=fallback)

    chunks = [chunk async for chunk in router.synthesize_stream("Show available homes")]

    assert chunks[-1].is_final
    assert fallback.calls == [("Show available homes", "en", None)]


@pytest.mark.asyncio
async def test_router_preserves_primary_error_when_fallback_also_fails() -> None:
    primary = MemoryTTS(fail=True)
    fallback = MemoryTTS(fail=True)
    router = TTSRouter({"en": primary}, fallback=fallback)

    with pytest.raises(TTSProviderError) as raised:
        [chunk async for chunk in router.synthesize_stream("Show available homes")]

    assert str(raised.value) == "provider unavailable"
    assert isinstance(raised.value.__cause__, TTSProviderError)
    assert str(raised.value.__cause__) == "provider unavailable"


@pytest.mark.asyncio
async def test_fish_provider_without_key_fails_explicitly() -> None:
    provider = FishAudioStreamingProvider(None)
    assert await provider.is_ready() is False
    with pytest.raises(TTSProviderError, match="FISH_AUDIO_API_KEY"):
        [chunk async for chunk in provider.synthesize_stream("hello", "en")]


@pytest.mark.asyncio
async def test_fish_provider_sends_configured_model_header(monkeypatch) -> None:
    from app.integrations.tts import fish

    captured: dict[str, object] = {}
    clients: list[Client] = []

    class Response:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def aiter_bytes(self, chunk_size: int):
            assert chunk_size == fish.STREAM_CHUNK_BYTES == 1024
            yield b"audio"

    class Client:
        def __init__(self, **kwargs):
            self.close_count = 0
            assert kwargs["timeout"] == 30.0
            assert kwargs["limits"].keepalive_expiry == 120.0
            clients.append(self)

        def stream(self, method: str, url: str, **kwargs):
            captured.setdefault("requests", []).append(
                {"method": method, "url": url, **kwargs}
            )
            return Response()

        async def aclose(self):
            self.close_count += 1

    monkeypatch.setattr(fish.httpx, "AsyncClient", lambda **kwargs: Client(**kwargs))
    provider = FishAudioStreamingProvider("test-key", model="s2.1-pro-free")
    chunks = [chunk async for chunk in provider.synthesize_stream("hello", "en")]
    second_chunks = [chunk async for chunk in provider.synthesize_stream("second request", "en")]

    assert len(clients) == 1
    assert len(captured["requests"]) == 2
    assert captured["requests"][0]["method"] == "POST"
    assert captured["requests"][0]["url"] == "https://api.fish.audio/v1/tts"
    assert captured["requests"][0]["headers"]["model"] == "s2.1-pro-free"
    assert captured["requests"][0]["json"]["sample_rate"] == 44_100
    assert captured["requests"][0]["json"]["latency"] == "balanced"
    assert chunks[0].audio == b"audio"
    assert second_chunks[0].audio == b"audio"
    await provider.aclose()
    assert clients[0].close_count == 1


@pytest.mark.asyncio
async def test_elevenlabs_provider_without_key_fails_explicitly() -> None:
    provider = ElevenLabsStreamingProvider(None, "")
    assert await provider.is_ready() is False
    with pytest.raises(TTSProviderError, match="ELEVENLABS_API_KEY"):
        [chunk async for chunk in provider.synthesize_stream("hello", "en")]


@pytest.mark.asyncio
async def test_external_wildcard_provider_supports_additional_languages() -> None:
    provider = MemoryTTS()
    router = TTSRouter({"*": provider})
    chunks = [chunk async for chunk in router.synthesize_stream("Namaste", "hi")]
    assert chunks[0].language == "hi"


@pytest.mark.asyncio
async def test_router_coalesces_code_switches_handled_by_same_model() -> None:
    provider = MemoryTTS()
    router = TTSRouter({"ur-Latn": provider, "en": provider})

    chunks = [
        chunk
        async for chunk in router.synthesize_stream("Mujhe Karachi mein house chahiye", "ur-Latn")
    ]

    assert provider.calls == [("Mujhe Karachi mein house chahiye", "ur-Latn", None)]
    assert chunks[-1].is_final is True
