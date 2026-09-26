from __future__ import annotations

from collections.abc import AsyncIterator
from os import getenv

import httpx

from app.domain.phonetics import apply_phonetic_transliteration
from app.integrations.tts.router import AudioChunk, TTSProviderError


class OpenAISpeechProvider:
    """Stream OpenAI speech audio while keeping the API key on the backend."""

    name = "openai-speech"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini-tts",
        voice: str = "marin",
        timeout_seconds: float = 45.0,
    ) -> None:
        self.api_key = api_key or getenv("OPENAI_API_KEY")
        self.model = model
        self.voice = voice
        self.timeout_seconds = timeout_seconds

    async def is_ready(self) -> bool:
        return bool(self.api_key)

    async def synthesize_stream(
        self,
        text: str,
        language: str,
        voice_id: str | None = None,
        instructions_override: str | None = None,
    ) -> AsyncIterator[AudioChunk]:
        if not self.api_key:
            raise TTSProviderError("OPENAI_API_KEY is not configured")
        if not text.strip():
            return
        voice = voice_id or self.voice
        instructions = instructions_override or (
            "Speak clearly and warmly for a Pakistani real-estate assistant. "
            "Use concise natural Urdu-English code-switching. Do not add words."
        )
        normalized_text = apply_phonetic_transliteration(text)
        payload = {
            "model": self.model,
            "voice": voice,
            "input": normalized_text,
            "instructions": instructions,
            "response_format": "pcm",
            "stream_format": "audio",
        }
        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_seconds) as client,
                client.stream(
                    "POST",
                    "https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                ) as response,
            ):
                if response.status_code >= 400:
                    # Avoid retaining or surfacing provider response bodies that can contain
                    # request details; the UI receives a stable, non-sensitive failure.
                    raise TTSProviderError(
                        f"OpenAI speech request failed with HTTP {response.status_code}"
                    )
                pending = bytearray()
                sequence = 0
                async for part in response.aiter_bytes(8192):
                    pending.extend(part)
                    while len(pending) >= 8192:
                        chunk = bytes(pending[:8192])
                        del pending[:8192]
                        yield AudioChunk(
                            sequence=sequence,
                            audio=chunk,
                            language=language,
                            sample_rate=24_000,
                            encoding="pcm_s16le",
                        )
                        sequence += 1
                if pending:
                    if len(pending) % 2:
                        pending.pop()
                    if pending:
                        yield AudioChunk(
                            sequence=sequence,
                            audio=bytes(pending),
                            language=language,
                            sample_rate=24_000,
                            encoding="pcm_s16le",
                        )
        except TTSProviderError:
            raise
        except httpx.HTTPError as error:
            raise TTSProviderError("OpenAI speech service is unavailable") from error
