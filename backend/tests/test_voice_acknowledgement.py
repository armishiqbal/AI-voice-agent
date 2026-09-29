from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.integrations.tts.router import AudioChunk, TTSProviderError
from app.services.voice_acknowledgement import (
    ACKNOWLEDGEMENTS,
    MAX_ACKNOWLEDGEMENT_AUDIO_BYTES,
    VoiceAcknowledgementCache,
    acknowledgement_text,
    prepare_acknowledgement,
)


class FakeSpeechProvider:
    name = "test-speech"

    def __init__(self, audio: tuple[bytes, ...]) -> None:
        self.audio = audio
        self.text: str | None = None
        self.calls = 0

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        del voice_id
        self.text = text
        self.calls += 1
        for sequence, payload in enumerate(self.audio):
            yield AudioChunk(sequence, payload, language)

    async def is_ready(self) -> bool:
        return True


@pytest.mark.parametrize("language", ["ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn"])
def test_acknowledgement_is_defined_for_supported_voice_languages(language: str) -> None:
    assert acknowledgement_text(language)


def test_acknowledgement_audio_is_bounded_and_does_not_include_empty_markers() -> None:
    async def scenario() -> None:
        provider = FakeSpeechProvider((b"pcm-one", b"", b"pcm-two"))
        chunks = await prepare_acknowledgement(provider, "ur-Latn")
        assert provider.text == ACKNOWLEDGEMENTS["ur-Latn"]
        assert [chunk.audio for chunk in chunks] == [b"pcm-one", b"pcm-two"]

    asyncio.run(scenario())


def test_acknowledgement_rejects_oversized_provider_audio() -> None:
    async def scenario() -> None:
        provider = FakeSpeechProvider((b"x" * (MAX_ACKNOWLEDGEMENT_AUDIO_BYTES + 1),))
        with pytest.raises(TTSProviderError, match="audio limit"):
            await prepare_acknowledgement(provider, "en")

    asyncio.run(scenario())


def test_acknowledgement_rejects_unsupported_language_and_empty_provider_audio() -> None:
    async def scenario() -> None:
        with pytest.raises(TTSProviderError, match="No spoken acknowledgement"):
            await prepare_acknowledgement(FakeSpeechProvider(()), "xx")
        with pytest.raises(TTSProviderError, match="returned no audio"):
            await prepare_acknowledgement(FakeSpeechProvider(()), "en")

    asyncio.run(scenario())


def test_acknowledgement_cache_shares_one_warmup_across_sessions() -> None:
    async def scenario() -> None:
        provider = FakeSpeechProvider((b"shared-audio",))
        cache = VoiceAcknowledgementCache()

        first = cache.warm(provider, "ur-Latn")
        second = cache.warm(provider, "ur-Latn")
        assert first is not None
        assert first is second
        await asyncio.gather(first, second)

        assert provider.calls == 1
        assert cache.get(provider, "ur-Latn") == (AudioChunk(0, b"shared-audio", "ur-Latn"),)
        assert cache.warm(provider, "ur-Latn") is None
        await cache.aclose()

    asyncio.run(scenario())
