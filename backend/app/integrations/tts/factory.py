from app.core.config import Settings
from app.integrations.tts.elevenlabs import ElevenLabsStreamingProvider
from app.integrations.tts.fish import FishAudioStreamingProvider
from app.integrations.tts.mms import MmsVitsProvider
from app.integrations.tts.openai import OpenAISpeechProvider
from app.integrations.tts.router import TTSRouter, UnavailableTTSProvider
from app.integrations.tts.service import HTTPTextToSpeechProvider


def build_tts_router(config: Settings) -> TTSRouter:
    """Build the configured multilingual router without downloading models at import time."""

    if config.tts_provider == "opensource":
        providers = {}
        if config.tts_parler_service_url:
            parler = HTTPTextToSpeechProvider(
                config.tts_parler_service_url,
                "parler",
                required_languages={"ur-Latn", "ur-Arab", "en", "hi", "pa", "bn"},
                api_key=config.tts_service_token,
                timeout_seconds=config.tts_timeout_seconds,
            )
            providers.update(
                {
                    "ur-Latn": parler,
                    "ur-Arab": parler,
                    "en": parler,
                    "hi": parler,
                    "pa": parler,
                    "bn": parler,
                }
            )
        if config.tts_chatterbox_service_url:
            chatterbox = HTTPTextToSpeechProvider(
                config.tts_chatterbox_service_url,
                "chatterbox",
                required_languages={"ar"},
                api_key=config.tts_service_token,
                timeout_seconds=config.tts_timeout_seconds,
            )
            providers["ar"] = chatterbox
        return TTSRouter(
            providers,
            fallback=UnavailableTTSProvider(
                "The open-source TTS service for this language is not configured"
            ),
        )

    if config.tts_provider == "fish":
        provider = FishAudioStreamingProvider(
            config.fish_audio_api_key,
            model=config.fish_audio_model,
            sample_rate=config.fish_audio_sample_rate,
            latency=config.fish_audio_latency,
            default_reference_id=config.fish_audio_reference_id,
        )
        return TTSRouter(
            {"ur-Latn": provider, "ur-Arab": provider, "en": provider, "*": provider},
            fallback=UnavailableTTSProvider("Fish Audio is unavailable"),
            voices={
                "ur-Latn": config.fish_audio_reference_id or "",
                "ur-Arab": config.fish_audio_reference_id or "",
                "en": config.fish_audio_reference_id or "",
                "*": config.fish_audio_reference_id or "",
            },
        )
    if config.tts_provider == "elevenlabs":
        provider = ElevenLabsStreamingProvider(
            config.elevenlabs_api_key, config.elevenlabs_voice_id or "", config.elevenlabs_model
        )
        return TTSRouter(
            {"ur-Latn": provider, "ur-Arab": provider, "en": provider, "*": provider},
            fallback=UnavailableTTSProvider("ElevenLabs is unavailable"),
            voices={
                "ur-Latn": config.elevenlabs_voice_id or "",
                "ur-Arab": config.elevenlabs_voice_id or "",
                "en": config.elevenlabs_voice_id or "",
                "*": config.elevenlabs_voice_id or "",
            },
        )
    if not config.local_tts_enabled:
        return TTSRouter({}, fallback=UnavailableTTSProvider("Local TTS is disabled"))
    urdu = MmsVitsProvider(config.tts_urdu_model)
    english = MmsVitsProvider(config.tts_english_model)
    hindi = MmsVitsProvider(config.tts_hindi_model)
    arabic = MmsVitsProvider(config.tts_arabic_model)
    punjabi = MmsVitsProvider(config.tts_punjabi_model)
    bengali = MmsVitsProvider(config.tts_bengali_model)
    return TTSRouter(
        {
            "ur-Latn": urdu,
            "ur-Arab": urdu,
            "en": english,
            "hi": hindi,
            "ar": arabic,
            "pa": punjabi,
            "bn": bengali,
        },
        voices={
            "ur-Latn": "urdu",
            "ur-Arab": "urdu",
            "en": "english",
            "hi": "hindi",
            "ar": "arabic",
            "pa": "punjabi",
            "bn": "bengali",
        },
    )


def build_openai_tts_router(config: Settings) -> TTSRouter:
    provider = OpenAISpeechProvider(
        api_key=config.openai_api_key,
        model=config.openai_tts_model,
        voice=config.openai_tts_voice,
        timeout_seconds=config.tts_timeout_seconds,
    )
    return TTSRouter(
        {"*": provider}, fallback=UnavailableTTSProvider("OpenAI speech is unavailable")
    )
