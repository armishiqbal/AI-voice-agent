from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import urlparse

from app.integrations.tts.router import AudioChunk, TTSProviderError


class HTTPTextToSpeechProvider:
    """Authenticated adapter for an independently deployed local TTS model service.

    The service returns raw mono PCM16 little-endian audio. The adapter rechunks the
    byte stream into bounded, even-sized packets for the browser WebSocket contract.
    """

    def __init__(
        self,
        base_url: str,
        engine: str,
        required_languages: set[str] | frozenset[str],
        api_key: str | None = None,
        timeout_seconds: float = 45.0,
        chunk_ms: int = 80,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        parsed = urlparse(self.base_url)
        if not api_key:
            raise ValueError("TTS services require an authentication token")
        local_http = parsed.scheme == "http" and parsed.hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
        if parsed.scheme != "https" and not local_http:
            raise ValueError("Remote TTS services must use HTTPS")
        normalized_languages = frozenset(required_languages)
        if not normalized_languages or any(
            not language.strip() for language in normalized_languages
        ):
            raise ValueError("TTS service routes must declare required languages")
        self.engine = engine
        self.required_languages = normalized_languages
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.chunk_ms = chunk_ms
        self.name = f"opensource-{engine}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def is_ready(self) -> bool:
        if not self.base_url:
            return False
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/readyz", headers=self._headers())
            if response.status_code != 200:
                return False
            payload = response.json()
            supported_languages = payload.get("supported_languages")
            return (
                payload.get("ready") is True
                and payload.get("model_loaded") is True
                and payload.get("engine") == self.engine
                and isinstance(supported_languages, list)
                and all(isinstance(language, str) for language in supported_languages)
                and self.required_languages.issubset(supported_languages)
            )
        except Exception:  # noqa: BLE001 - readiness is a probe, not a request failure
            return False

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        del voice_id
        if not text.strip():
            return
        try:
            import httpx

            async with (
                httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout_seconds, connect=3.0)
                ) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/v1/synthesize",
                    headers=self._headers(),
                    json={"text": text, "language": language},
                ) as response,
            ):
                if response.status_code != 200:
                    raise TTSProviderError(
                        f"TTS service {self.engine} returned HTTP {response.status_code}"
                    )
                sample_rate = int(response.headers.get("x-audio-sample-rate", "0"))
                encoding = response.headers.get("x-audio-encoding", "")
                if sample_rate < 8_000 or sample_rate > 96_000 or encoding != "pcm_s16le":
                    raise TTSProviderError(
                        f"TTS service {self.engine} returned an unsupported audio format"
                    )
                bytes_per_chunk = max(2, sample_rate * self.chunk_ms // 1000 * 2)
                sequence = 0
                pending = bytearray()
                async for part in response.aiter_bytes():
                    pending.extend(part)
                    while len(pending) >= bytes_per_chunk:
                        audio = bytes(pending[:bytes_per_chunk])
                        del pending[:bytes_per_chunk]
                        yield AudioChunk(
                            sequence=sequence,
                            audio=audio,
                            language=language,
                            sample_rate=sample_rate,
                            encoding=encoding,
                        )
                        sequence += 1
                    if len(pending) % 2:
                        raise TTSProviderError("TTS service returned an incomplete PCM16 sample")
                    if pending:
                        yield AudioChunk(
                            sequence=sequence,
                            audio=bytes(pending),
                            language=language,
                            sample_rate=sample_rate,
                            encoding=encoding,
                        )
                        sequence += 1
                    if sequence == 0:
                        raise TTSProviderError("TTS service returned no audio")
        except TTSProviderError:
            raise
        except Exception as error:
            raise TTSProviderError(f"TTS service {self.engine} is unavailable") from error
