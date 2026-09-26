from __future__ import annotations

from collections.abc import AsyncIterator

from app.integrations.tts.router import AudioChunk, TTSProviderError


class FishAudioStreamingProvider:
    """Optional Fish Audio streaming adapter returning compressed audio chunks."""

    name = "fish-audio"

    def __init__(
        self, api_key: str | None, model: str = "s2.1-pro", sample_rate: int = 24_000
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate

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

        async def text_stream() -> AsyncIterator[str]:
            yield text

        try:
            client = AsyncFishAudio(api_key=self.api_key)
            kwargs: dict[str, object] = {"latency": "balanced"}
            if self.model:
                kwargs["model"] = self.model
            if voice_id:
                kwargs["reference_id"] = voice_id
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
