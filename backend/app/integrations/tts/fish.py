from __future__ import annotations

from collections.abc import AsyncIterator

from app.domain.phonetics import apply_phonetic_transliteration
from app.integrations.tts.router import AudioChunk, TTSProviderError


class FishAudioStreamingProvider:
    """Fish Audio streaming adapter with low latency and Pakistani voice clone support."""

    name = "fish-audio"

    def __init__(
        self,
        api_key: str | None,
        model: str = "s2.1-pro",
        sample_rate: int = 24_000,
        latency: str = "low",
        default_reference_id: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate
        self.latency = latency
        self.default_reference_id = default_reference_id

    async def is_ready(self) -> bool:
        if not self.api_key:
            return False
        try:
            import fishaudio  # noqa: F401
        except ImportError:
            return False
        return True

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        del language
        if not self.api_key:
            raise TTSProviderError("FISH_AUDIO_API_KEY is not configured")
        try:
            from fishaudio import AsyncFishAudio
        except ImportError as error:
            raise TTSProviderError("Install the voice-fish extra to enable Fish Audio") from error

        # Normalize Pakistani entities and acronyms for natural pronunciation
        normalized_text = apply_phonetic_transliteration(text, target_provider="fish")

        async def text_stream() -> AsyncIterator[str]:
            yield normalized_text

        try:
            client = AsyncFishAudio(api_key=self.api_key)
            kwargs: dict[str, object] = {"latency": self.latency}
            if self.model:
                kwargs["model"] = self.model
            ref_id = voice_id or self.default_reference_id
            if ref_id:
                kwargs["reference_id"] = ref_id
            stream = await client.tts.stream_websocket(text_stream(), **kwargs)
            sequence = 0
            async for chunk in stream:
                audio = bytes(chunk)
                if audio:
                    yield AudioChunk(
                        sequence=sequence,
                        audio=audio,
                        language="",
                        sample_rate=self.sample_rate,
                        encoding="audio/mpeg",
                    )
                    sequence += 1
        except TTSProviderError:
            raise
        except Exception as error:
            raise TTSProviderError(f"Fish Audio streaming failed: {error}") from error
