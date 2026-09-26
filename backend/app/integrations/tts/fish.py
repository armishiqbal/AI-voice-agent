from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.domain.phonetics import apply_phonetic_transliteration
from app.integrations.tts.router import AudioChunk, TTSProviderError


class FishAudioStreamingProvider:
    """Fish Audio streaming adapter using low-latency HTTP streaming."""

    name = "fish-audio"

    def __init__(
        self,
        api_key: str | None,
        model: str = "s2.1-pro",
        sample_rate: int = 24_000,
        latency: str = "low",
        default_reference_id: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate
        self.latency = latency
        self.default_reference_id = default_reference_id
        self.timeout_seconds = timeout_seconds

    async def is_ready(self) -> bool:
        return bool(self.api_key)

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        del language
        if not self.api_key:
            raise TTSProviderError("FISH_AUDIO_API_KEY is not configured")
        if not text.strip():
            return

        normalized_text = apply_phonetic_transliteration(text, target_provider="fish")
        ref_id = voice_id or self.default_reference_id

        payload: dict[str, object] = {
            "text": normalized_text,
            "format": "mp3",
            "latency": self.latency,
        }
        if ref_id:
            payload["reference_id"] = ref_id

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_seconds) as client,
                client.stream(
                    "POST",
                    "https://api.fish.audio/v1/tts",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response,
            ):
                if response.status_code == 402:
                    raise TTSProviderError(
                        "Fish Audio has insufficient API credits. Add funds at https://fish.audio/app/developers"
                    )
                if response.status_code >= 400:
                    raise TTSProviderError(
                        f"Fish Audio streaming request failed with HTTP {response.status_code}"
                    )
                sequence = 0
                async for chunk in response.aiter_bytes(4096):
                    if chunk:
                        yield AudioChunk(
                            sequence=sequence,
                            audio=chunk,
                            language="",
                            sample_rate=self.sample_rate,
                            encoding="audio/mpeg",
                        )
                        sequence += 1
        except TTSProviderError:
            raise
        except httpx.HTTPError as error:
            raise TTSProviderError(f"Fish Audio streaming failed: {error}") from error
