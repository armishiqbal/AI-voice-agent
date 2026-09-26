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
            "Use natural Urdu-English code-switching and a relaxed conversational pace. "
            "Use short pauses at sentence boundaries, clear numbers and a warm, restrained tone. "
            "Avoid exaggerated sales delivery. Read only the supplied words."
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
                # Yield complete PCM samples as network bytes arrive. Asking httpx for an
                # 8192-byte block held back ~171ms of 24kHz audio before first playback.
                async for part in response.aiter_bytes():
                    pending.extend(part)
                    while len(pending) >= 2:
                        size = min(2048, len(pending) - len(pending) % 2)
                        chunk = bytes(pending[:size])
                        del pending[:size]
                        yield AudioChunk(
                            sequence=sequence,
                            audio=chunk,
                            language=language,
                            sample_rate=24_000,
                            encoding="pcm_s16le",
                        )
                        sequence += 1
                if pending:
                    raise TTSProviderError("OpenAI speech returned an incomplete PCM sample")
                if sequence == 0:
                    raise TTSProviderError("OpenAI speech returned no audio")
        except TTSProviderError:
            raise
        except httpx.HTTPError as error:
            raise TTSProviderError("OpenAI speech service is unavailable") from error
