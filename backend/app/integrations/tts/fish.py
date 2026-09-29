from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Literal

import httpx

from app.domain.phonetics import apply_phonetic_transliteration
from app.integrations.tts.router import AudioChunk, TTSProviderError

STREAM_CHUNK_BYTES = 1_024


class FishAudioStreamingProvider:
    """Fish Audio streaming adapter using low-latency HTTP streaming."""

    name = "fish-audio"

    def __init__(
        self,
        api_key: str | None,
        model: str = "s2.1-pro",
        sample_rate: int = 44_100,
        latency: Literal["balanced", "normal"] = "balanced",
        default_reference_id: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate
        self.latency = latency
        self.default_reference_id = default_reference_id
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        timeout=self.timeout_seconds,
                        limits=httpx.Limits(keepalive_expiry=120.0),
                    )
        return self._client

    async def aclose(self) -> None:
        """Close the pooled keep-alive connection during application shutdown."""
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

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
            "sample_rate": self.sample_rate,
            "latency": self.latency,
        }
        if ref_id:
            payload["reference_id"] = ref_id

        try:
            client = await self._http_client()
            async with client.stream(
                "POST",
                "https://api.fish.audio/v1/tts",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "model": self.model,
                },
                json=payload,
            ) as response:
                if response.status_code == 402:
                    raise TTSProviderError(
                        "Fish Audio has insufficient API credits. Add funds at https://fish.audio/app/developers"
                    )
                if response.status_code >= 400:
                    raise TTSProviderError(
                        f"Fish Audio streaming request failed with HTTP {response.status_code}"
                    )
                sequence = 0
                # httpx's ByteChunker waits for this many decoded bytes before it
                # yields. A 4 KiB threshold delayed first audio unnecessarily; keep
                # chunks small so browser playback can begin while the provider streams.
                async for chunk in response.aiter_bytes(STREAM_CHUNK_BYTES):
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
