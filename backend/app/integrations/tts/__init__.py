"""Provider-neutral multilingual text-to-speech contracts."""

from app.integrations.tts.elevenlabs import ElevenLabsStreamingProvider
from app.integrations.tts.factory import build_openai_tts_router, build_tts_router
from app.integrations.tts.fish import FishAudioStreamingProvider
from app.integrations.tts.mms import MmsVitsProvider
from app.integrations.tts.openai import OpenAISpeechProvider
from app.integrations.tts.router import (
    AudioChunk,
    TTSProvider,
    TTSProviderError,
    TTSRouter,
    UnavailableTTSProvider,
    detect_language,
    segment_text,
)
from app.integrations.tts.service import HTTPTextToSpeechProvider

__all__ = [
    "AudioChunk",
    "ElevenLabsStreamingProvider",
    "FishAudioStreamingProvider",
    "HTTPTextToSpeechProvider",
    "MmsVitsProvider",
    "OpenAISpeechProvider",
    "TTSProvider",
    "TTSProviderError",
    "TTSRouter",
    "UnavailableTTSProvider",
    "build_openai_tts_router",
    "build_tts_router",
    "detect_language",
    "segment_text",
]
