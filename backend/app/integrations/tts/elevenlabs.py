from __future__ import annotations

from collections.abc import AsyncIterator

from app.integrations.tts.router import AudioChunk, TTSProviderError


class ElevenLabsStreamingProvider:
    """Optional HTTP streaming adapter used for production TTS and benchmark comparison."""

    name = "elevenlabs"

    def __init__(
        self, api_key: str | None, voice_id: str, model: str = "eleven_multilingual_v2"
    ) -> None:
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model

    async def is_ready(self) -> bool:
        if not self.api_key or not self.voice_id:
            return False
        try:
            import httpx  # noqa: F401
        except ImportError:
            return False
        return True

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        del language
        if not self.api_key:
            raise TTSProviderError("ELEVENLABS_API_KEY is not configured")
        selected_voice = voice_id or self.voice_id
        if not selected_voice:
            raise TTSProviderError("ELEVENLABS_VOICE_ID is not configured")
        try:
            import httpx
        except ImportError as error:
            raise TTSProviderError(
                "Install the voice-elevenlabs extra to enable ElevenLabs"
            ) from error
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{selected_voice}/stream"
        try:
            async with (
                httpx.AsyncClient(timeout=30.0) as client,
                client.stream(
                    "POST",
                    url,
                    params={"output_format": "mp3_22050_32", "enable_logging": "false"},
                    headers={"xi-api-key": self.api_key, "content-type": "application/json"},
                    json={"text": text, "model_id": self.model},
                ) as response,
            ):
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", errors="replace")[:300]
                    raise TTSProviderError(f"ElevenLabs returned {response.status_code}: {body}")
                sequence = 0
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield AudioChunk(
                            sequence=sequence,
                            audio=chunk,
                            language="",
                            sample_rate=22_050,
                            encoding="audio/mpeg",
                        )
                        sequence += 1
        except TTSProviderError:
            raise
        except Exception as error:
            raise TTSProviderError(f"ElevenLabs streaming failed: {error}") from error
