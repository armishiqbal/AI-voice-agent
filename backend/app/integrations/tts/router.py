from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AudioChunk:
    """A playable chunk returned by a TTS provider.

    Providers must return a consistent codec for one session. The router keeps
    language metadata on each chunk so clients can trace code-switched output.
    """

    sequence: int
    audio: bytes
    language: str
    sample_rate: int = 24_000
    encoding: str = "pcm_s16le"
    is_final: bool = False


class TTSProvider(Protocol):
    name: str

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]: ...

    async def is_ready(self) -> bool: ...


class TTSProviderError(RuntimeError):
    """Expected provider failure that can be handled by the router."""


class UnavailableTTSProvider:
    """Explicit no-provider implementation; never produces fake audio."""

    name = "unavailable"

    def __init__(self, reason: str = "No TTS provider is configured") -> None:
        self.reason = reason

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        del text, language, voice_id
        raise TTSProviderError(self.reason)
        yield  # pragma: no cover - keeps this function an async generator

    async def is_ready(self) -> bool:
        return False


# These are intentionally small and conservative. Unknown Latin text follows
# the caller's preferred language instead of being split into tiny chunks.
ROMAN_URDU_MARKERS = frozenset(
    {
        "acha",
        "aap",
        "apka",
        "apki",
        "chahiye",
        "dikha",
        "dikhain",
        "hai",
        "hain",
        "karna",
        "karen",
        "ke",
        "keliye",
        "mein",
        "mujhe",
        "nahi",
        "phir",
        "tha",
        "yeh",
    }
)
ENGLISH_MARKERS = frozenset(
    {
        "available",
        "bedroom",
        "buy",
        "commercial",
        "house",
        "investment",
        "office",
        "price",
        "property",
        "rent",
        "show",
        "visit",
    }
)

WORD_RE = re.compile(r"\s+|[^\s]+")
URDU_SPECIFIC_LETTERS = frozenset("ٹڈڑںھہےچژگپ")
SUPPORTED_LANGUAGES = frozenset({"en", "ur-Latn", "ur-Arab", "hi", "ar", "pa", "bn"})


def detect_language(text: str, preferred: str = "en") -> str:
    """Detect the speech language without pretending to solve ASR language ID."""

    if any("\u0600" <= character <= "\u06ff" for character in text):
        return "ar" if preferred == "ar" else "ur-Arab"
    if any("\u0900" <= character <= "\u097f" for character in text):
        return "hi"
    if any("\u0a00" <= character <= "\u0a7f" for character in text):
        return "pa"
    if any("\u0980" <= character <= "\u09ff" for character in text):
        return "bn"
    words = {word.lower().strip(".,!?;:\")'") for word in text.split()}
    if words & ROMAN_URDU_MARKERS:
        return "ur-Latn"
    return preferred if preferred in {"en", "ur-Latn", "ur-Arab", "hi", "ar", "pa", "bn"} else "en"


def segment_text(text: str, preferred: str | None = None) -> list[tuple[str, str]]:
    """Group a response into language segments using conservative token cues.

    Script is a useful signal for multilingual TTS, but Arabic and Urdu share
    most of their script and Roman Urdu is ambiguous. For those cases, an
    explicit preferred language or a small high-precision word list is used;
    this function does not claim general-purpose language identification.
    """

    cleaned = re.sub(r"[*_#`]+", "", text).strip()
    if not cleaned:
        return []
    default = preferred if preferred in SUPPORTED_LANGUAGES else detect_language(cleaned)
    segments: list[tuple[str, str]] = []
    current_language: str | None = None
    current_text = ""
    pending_space = ""
    for token in WORD_RE.findall(cleaned):
        if token.isspace():
            pending_space += token
            continue
        language = _token_language(token, default)
        if current_language is not None and language != current_language:
            segments.append((current_text + pending_space, current_language))
            current_text = token
        else:
            current_text += pending_space + token
        current_language = language
        pending_space = ""
    if current_language is not None:
        segments.append((current_text + pending_space, current_language))
    return segments


def _token_language(token: str, default: str) -> str:
    """Infer one token's TTS language from script, then high-precision cues."""

    if any("\u0600" <= character <= "\u06ff" for character in token):
        if any(character in URDU_SPECIFIC_LETTERS for character in token):
            return "ur-Arab"
        return "ar" if default == "ar" else "ur-Arab"
    if any("\u0900" <= character <= "\u097f" for character in token):
        return "hi"
    if any("\u0a00" <= character <= "\u0a7f" for character in token):
        return "pa"
    if any("\u0980" <= character <= "\u09ff" for character in token):
        return "bn"
    normalized = re.sub(r"^[^\w]+|[^\w]+$", "", token.lower())
    if normalized in ROMAN_URDU_MARKERS:
        return "ur-Latn"
    if normalized in ENGLISH_MARKERS:
        return "en"
    return default


class TTSRouter:
    """Routes language segments to providers and emits one ordered stream."""

    def __init__(
        self,
        providers: dict[str, TTSProvider],
        fallback: TTSProvider | None = None,
        voices: dict[str, str] | None = None,
    ) -> None:
        self.providers = providers
        self.fallback = fallback
        self.voices = voices or {}

    async def aclose(self) -> None:
        """Close providers that own pooled resources, once per provider instance."""
        providers = {id(provider): provider for provider in self.providers.values()}
        if self.fallback is not None:
            providers[id(self.fallback)] = self.fallback
        close_calls = []
        for provider in providers.values():
            close = getattr(provider, "aclose", None)
            if close is not None:
                close_calls.append(close())
        if close_calls:
            await asyncio.gather(*close_calls)

    async def warmup(self) -> bool:
        """Warm each unique provider that supports transport setup; failures are non-fatal."""
        providers = {id(provider): provider for provider in self.providers.values()}
        if self.fallback is not None:
            providers[id(self.fallback)] = self.fallback
        warmups = [getattr(provider, "warmup", None) for provider in providers.values()]
        callable_warmups = [warmup for warmup in warmups if callable(warmup)]
        if not callable_warmups:
            return False
        results = await asyncio.gather(
            *(warmup() for warmup in callable_warmups), return_exceptions=True
        )
        return all(result is True for result in results)

    async def synthesize_stream(
        self, text: str, preferred_language: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        sequence = 0
        last_sample_rate = 24_000
        last_encoding = "pcm_s16le"
        grouped: list[tuple[str, str, TTSProvider, str | None]] = []
        for segment, language in segment_text(text, preferred_language):
            provider = (
                self.providers.get(language)
                or self.providers.get(language.split("-")[0])
                or self.providers.get("*")
                or self.fallback
            )
            if provider is None:
                raise TTSProviderError(f"No TTS provider configured for {language}")
            voice_id = self.voices.get(language) or self.voices.get("*")
            if grouped and grouped[-1][2] is provider and grouped[-1][3] == voice_id:
                previous_text, previous_language, previous_provider, previous_voice = grouped[-1]
                grouped[-1] = (
                    previous_text + segment,
                    previous_language,
                    previous_provider,
                    previous_voice,
                )
            else:
                grouped.append((segment, language, provider, voice_id))

        for segment, language, provider, voice_id in grouped:
            try:
                async for chunk in provider.synthesize_stream(segment, language, voice_id):
                    last_sample_rate = chunk.sample_rate
                    last_encoding = chunk.encoding
                    yield AudioChunk(
                        sequence=sequence,
                        audio=chunk.audio,
                        language=language,
                        sample_rate=chunk.sample_rate,
                        encoding=chunk.encoding,
                        is_final=False,
                    )
                    sequence += 1
            except TTSProviderError as primary_error:
                if provider is self.fallback or self.fallback is None:
                    raise
                try:
                    async for chunk in self.fallback.synthesize_stream(segment, language, voice_id):
                        last_sample_rate = chunk.sample_rate
                        last_encoding = chunk.encoding
                        yield AudioChunk(
                            sequence=sequence,
                            audio=chunk.audio,
                            language=language,
                            sample_rate=chunk.sample_rate,
                            encoding=chunk.encoding,
                            is_final=False,
                        )
                        sequence += 1
                except TTSProviderError as fallback_error:
                    # Keep the safe fallback error visible while preserving the primary cause
                    # for server-side classification (for example, provider quota exhaustion).
                    raise fallback_error from primary_error
        if sequence:
            yield AudioChunk(
                sequence=sequence,
                audio=b"",
                language="",
                sample_rate=last_sample_rate,
                encoding=last_encoding,
                is_final=True,
            )

    async def readiness(self) -> dict[str, bool]:
        unique = {id(provider): provider for provider in self.providers.values()}
        if self.fallback is not None:
            unique[id(self.fallback)] = self.fallback
        readiness = await asyncio.gather(
            *(provider.is_ready() for provider in unique.values()), return_exceptions=True
        )
        by_provider_id = {
            provider_id: result is True
            for provider_id, result in zip(unique, readiness, strict=True)
        }
        result = {
            language: by_provider_id[id(provider)] for language, provider in self.providers.items()
        }
        if self.fallback is not None:
            result[f"fallback:{self.fallback.name}"] = by_provider_id[id(self.fallback)]
        return result
