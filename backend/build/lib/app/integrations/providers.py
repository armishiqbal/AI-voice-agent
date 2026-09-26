from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SpeechToTextProvider(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


class TextToSpeechProvider(Protocol):
    async def synthesize(self, text: str, language: str) -> bytes: ...


class StructuredLLMProvider(Protocol):
    async def decide(self, prompt: str) -> dict[str, object]: ...


class TTSReadinessProvider(Protocol):
    async def readiness(self) -> dict[str, bool]: ...


@dataclass(frozen=True)
class ProviderReadiness:
    deepgram: bool
    openai: bool
    fish_audio: bool
    elevenlabs: bool
    pinecone: bool
    multilingual_tts: bool
    calendar: bool
    gmail: bool
    telephony: bool

    @property
    def live_voice_pipeline_ready(self) -> bool:
        return self.deepgram and self.openai and self.multilingual_tts


def provider_readiness(config: object | None = None) -> ProviderReadiness:
    if config is None:
        from app.core.config import settings

        config = settings
    tts_provider = str(getattr(config, "tts_provider", "router")).casefold()
    open_source_tts_configured = (
        tts_provider == "opensource"
        and bool(getattr(config, "tts_parler_service_url", None))
        and bool(getattr(config, "tts_chatterbox_service_url", None))
        and bool(getattr(config, "tts_service_token", None))
    )
    token_path = getattr(config, "google_token_path", None)
    google_scopes: set[str] = set()
    google_refreshable = False
    if token_path:
        try:
            token = json.loads(Path(str(token_path)).read_text(encoding="utf-8"))
            if isinstance(token, dict):
                google_refreshable = bool(token.get("refresh_token"))
                scopes = token.get("scopes", [])
                if isinstance(scopes, list):
                    google_scopes = {scope for scope in scopes if isinstance(scope, str)}
        except (OSError, json.JSONDecodeError):
            pass
    openai_sdk = importlib.util.find_spec("openai") is not None
    deepgram_sdk = importlib.util.find_spec("deepgram") is not None
    return ProviderReadiness(
        deepgram=bool(getattr(config, "deepgram_api_key", None)) and deepgram_sdk,
        openai=(
            bool(getattr(config, "openai_api_key", None))
            and getattr(config, "llm_provider", "openai") == "openai"
            and openai_sdk
        ),
        fish_audio=bool(getattr(config, "fish_audio_api_key", None)),
        pinecone=bool(
            getattr(config, "pinecone_api_key", None) and getattr(config, "pinecone_index", None)
        ),
        elevenlabs=bool(
            getattr(config, "elevenlabs_api_key", None)
            and getattr(config, "elevenlabs_voice_id", None)
        ),
        # This gate is deliberately specific to the required open-source path.
        # Actual worker/model readiness and per-language checks happen separately.
        multilingual_tts=open_source_tts_configured,
        calendar=google_refreshable
        and "https://www.googleapis.com/auth/calendar.events" in google_scopes,
        gmail=(
            google_refreshable
            and "https://www.googleapis.com/auth/gmail.send" in google_scopes
            and bool(getattr(config, "gmail_sender", None))
        ),
        telephony=(
            str(getattr(config, "telephony_provider", "none")).casefold() == "twilio"
            and bool(getattr(config, "twilio_account_sid", None))
            and bool(getattr(config, "twilio_auth_token", None))
            and bool(getattr(config, "twilio_from_number", None))
            and bool(getattr(config, "telephony_public_base_url", None))
        ),
    )


async def all_tts_languages_ready(router: TTSReadinessProvider) -> bool:
    """Probe every language route required by the current multilingual product scope."""

    readiness = await router.readiness()
    required_languages = ("ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn")
    return all(
        readiness.get(language, readiness.get(language.split("-")[0], readiness.get("*", False)))
        for language in required_languages
    )
