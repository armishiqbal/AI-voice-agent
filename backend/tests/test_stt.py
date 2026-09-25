from app.integrations.stt import (
    STTEvent,
    parse_deepgram_message,
    parse_openai_transcription_event,
    resample_pcm16_16k_to_24k,
)


def test_parse_deepgram_final_result() -> None:
    event = parse_deepgram_message(
        {
            "type": "Results",
            "is_final": True,
            "speech_final": True,
            "channel": {
                "alternatives": [
                    {
                        "transcript": "Mujhe Karachi mein ghar chahiye",
                        "confidence": 0.91,
                        "words": [{"language": "ur"}],
                    }
                ]
            },
        }
    )
    assert event == STTEvent(
        text="Mujhe Karachi mein ghar chahiye",
        language="ur",
        confidence=0.91,
        is_final=True,
        speech_final=True,
    )


def test_parse_speech_started_and_ignores_metadata() -> None:
    assert parse_deepgram_message({"type": "SpeechStarted"}) == STTEvent(speech_started=True)
    assert parse_deepgram_message({"type": "Metadata"}) is None


def test_openai_realtime_transcription_events_do_not_invent_confidence() -> None:
    assert parse_openai_transcription_event(
        {"type": "conversation.item.input_audio_transcription.delta", "delta": "Mujhe"}
    ) == STTEvent(text="Mujhe", is_final=False)
    assert parse_openai_transcription_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "Mujhe Karachi mein ghar chahiye",
        }
    ) == STTEvent(
        text="Mujhe Karachi mein ghar chahiye",
        is_final=True,
        speech_final=True,
    )
    assert parse_openai_transcription_event({"type": "error"}) is None


def test_openai_audio_resampler_converts_pcm16_16k_to_24k() -> None:
    import struct

    audio = struct.pack("<2h", 0, 12000)
    converted = resample_pcm16_16k_to_24k(audio)
    assert len(converted) == 6
    assert struct.unpack("<3h", converted) == (0, 8000, 12000)
