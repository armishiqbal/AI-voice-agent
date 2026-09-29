"""Streaming speech-to-text contracts and optional provider adapters."""

from app.integrations.stt.deepgram import (
    DeepgramStreamingSTT,
    STTEvent,
    STTProvider,
    STTProviderError,
    UnavailableSTTProvider,
    parse_deepgram_message,
    stt_provider_error_code,
)
from app.integrations.stt.factory import (
    build_english_hybrid_stt,
    build_openai_realtime_stt,
    build_stt_provider,
    build_urdu_hybrid_stt,
)
from app.integrations.stt.openai_realtime import (
    OpenAIRealtimeSTT,
    parse_openai_transcription_event,
    resample_pcm16_16k_to_24k,
)

__all__ = [
    "DeepgramStreamingSTT",
    "OpenAIRealtimeSTT",
    "STTEvent",
    "STTProvider",
    "STTProviderError",
    "UnavailableSTTProvider",
    "build_english_hybrid_stt",
    "build_openai_realtime_stt",
    "build_stt_provider",
    "build_urdu_hybrid_stt",
    "parse_deepgram_message",
    "parse_openai_transcription_event",
    "resample_pcm16_16k_to_24k",
    "stt_provider_error_code",
]
