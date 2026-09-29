from app.core.config import Settings
from app.integrations.stt.deepgram import DeepgramStreamingSTT, STTProvider, UnavailableSTTProvider
from app.integrations.stt.openai_realtime import OpenAIRealtimeSTT


def build_stt_provider(config: Settings) -> STTProvider:
    if config.stt_provider != "deepgram":
        return UnavailableSTTProvider()
    return DeepgramStreamingSTT(
        api_key=config.deepgram_api_key,
        model=config.stt_model,
        language=config.stt_language,
        endpointing=config.stt_endpointing_ms,
        utterance_end_ms=config.stt_utterance_end_ms,
        sample_rate=config.stt_sample_rate,
        finalize_timeout_seconds=config.stt_finalize_timeout_seconds,
    )


def build_english_hybrid_stt(config: Settings) -> STTProvider:
    """Use browser VAD plus a bounded provider endpoint for English hybrid voice."""
    return DeepgramStreamingSTT(
        api_key=config.deepgram_api_key,
        model=config.stt_model,
        language="en",
        endpointing=config.stt_endpointing_ms,
        utterance_end_ms=config.stt_utterance_end_ms,
        sample_rate=config.stt_sample_rate,
        finalize_timeout_seconds=config.stt_finalize_timeout_seconds,
    )


def build_urdu_hybrid_stt(config: Settings) -> STTProvider:
    """Use Nova-3 Urdu with browser VAD, provider finalization, and real-estate hints."""
    return DeepgramStreamingSTT(
        api_key=config.deepgram_api_key,
        model="nova-3",
        language="ur",
        endpointing=config.stt_endpointing_ms,
        utterance_end_ms=config.stt_utterance_end_ms,
        sample_rate=config.stt_sample_rate,
        keyterms=("DHA", "Karachi", "Lahore", "Islamabad", "crore", "lakh", "marla", "kanal"),
        finalize_timeout_seconds=config.stt_finalize_timeout_seconds,
    )


def build_openai_realtime_stt(config: Settings) -> STTProvider:
    return OpenAIRealtimeSTT(
        api_key=config.openai_api_key,
        model=config.openai_realtime_transcription_model,
        realtime_model=config.openai_realtime_tts_model,
        finalization_timeout_seconds=config.openai_realtime_transcription_timeout_seconds,
    )
