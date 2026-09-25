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
    )


def build_openai_realtime_stt(config: Settings) -> STTProvider:
    return OpenAIRealtimeSTT(
        api_key=config.openai_api_key,
        model=config.openai_realtime_transcription_model,
    )
