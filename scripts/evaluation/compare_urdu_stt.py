"""Compare current OpenAI Realtime and Deepgram Nova-3 Urdu turn-finalization latency.

Uses short generated UrduLish phrases paced at the browser AudioWorklet cadence.
This is provider-billed synthetic evidence, not a human accuracy evaluation.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from live_voice_latency import FRAME_SECONDS, PHRASES, resample_24k_to_16k

from app.core.config import settings
from app.integrations.stt.deepgram import DeepgramStreamingSTT, STTEvent
from app.integrations.stt.openai_realtime import OpenAIRealtimeSTT
from app.integrations.tts.openai_realtime import OpenAIRealtimeSpeechProvider

FRAME_SAMPLES = round(16_000 * FRAME_SECONDS)
SILENCE_FRAMES = 5


async def speech_inputs() -> list[bytes]:
    provider = OpenAIRealtimeSpeechProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_realtime_tts_model,
        voice=settings.openai_tts_voice,
    )
    results: list[bytes] = []
    try:
        for phrase in PHRASES:
            audio = bytearray()
            async for chunk in provider.synthesize_stream(phrase, "ur-Latn"):
                audio.extend(chunk.audio)
            if not audio:
                raise RuntimeError("The speech provider returned no generated input audio")
            results.append(resample_24k_to_16k(bytes(audio)))
    finally:
        await provider.aclose()
    return results


async def run_provider(name: str, provider: Any, audio_inputs: list[bytes]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        for phrase, audio in zip(PHRASES, audio_inputs, strict=True):
            voice_end_at: float | None = None
            speech_frames = [
                audio[offset : offset + FRAME_SAMPLES * 2]
                for offset in range(0, len(audio), FRAME_SAMPLES * 2)
            ]

            async def frames(frames_for_turn: list[bytes] = speech_frames):
                nonlocal voice_end_at
                loop = asyncio.get_running_loop()
                started = loop.time()
                for index, frame in enumerate(frames_for_turn):
                    deadline = started + index * FRAME_SECONDS
                    delay = deadline - loop.time()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    yield frame
                    if index == len(frames_for_turn) - 1:
                        voice_end_at = loop.time()
                for index in range(SILENCE_FRAMES):
                    deadline = started + (len(frames_for_turn) + index) * FRAME_SECONDS
                    delay = deadline - loop.time()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    yield b"\x00" * FRAME_SAMPLES * 2
                yield b""

            final: STTEvent | None = None
            finalized_at: float | None = None
            async for event in provider.stream(frames()):
                if event.is_final and event.text:
                    final = event
                    finalized_at = asyncio.get_running_loop().time()
            if final is None or finalized_at is None or voice_end_at is None:
                raise RuntimeError(f"{name} did not finalize: {phrase}")
            results.append(
                {
                    "input_phrase": phrase,
                    "transcript": final.text,
                    "detected_language": final.language,
                    "confidence": final.confidence,
                    "end_of_voice_to_final_ms": round(
                        (finalized_at - voice_end_at) * 1000, 1
                    ),
                }
            )
    finally:
        close = getattr(provider, "aclose", None)
        if close is not None:
            await close()
    return results


async def run() -> dict[str, Any]:
    if not settings.openai_api_key or not settings.deepgram_api_key:
        raise RuntimeError("Both OpenAI and Deepgram credentials are required for this comparison")
    audio_inputs = await speech_inputs()
    openai = OpenAIRealtimeSTT(
        api_key=settings.openai_api_key,
        model=settings.openai_realtime_transcription_model,
        realtime_model=settings.openai_realtime_tts_model,
        finalization_timeout_seconds=settings.openai_realtime_transcription_timeout_seconds,
    )
    openai.configure_response_language("ur-Latn")
    deepgram = DeepgramStreamingSTT(
        api_key=settings.deepgram_api_key,
        model="nova-3",
        language="ur",
        endpointing=settings.stt_endpointing_ms,
        utterance_end_ms=1000,
        sample_rate=16_000,
    )
    deepgram_keyterms = DeepgramStreamingSTT(
        api_key=settings.deepgram_api_key,
        model="nova-3",
        language="ur",
        endpointing=settings.stt_endpointing_ms,
        utterance_end_ms=1000,
        sample_rate=16_000,
        keyterms=("DHA", "Karachi", "Lahore", "Islamabad", "crore", "lakh", "marla", "kanal"),
    )
    return {
        "method": f"Same three OpenAI-Realtime-generated UrduLish phrases paced at the browser's 4096-sample/48kHz AudioWorklet cadence, with five silence frames before commit/finalize; Deepgram endpointing={settings.stt_endpointing_ms} ms.",
        "voice_end_definition": "Time the final audio frame was handed to the provider's input stream; provider finalization follows five 85.3 ms silence frames.",
        "synthetic_input_only": True,
        "providers": {
            "openai_realtime": await run_provider("OpenAI Realtime", openai, audio_inputs),
            "deepgram_nova_3_urdu": await run_provider("Deepgram Nova-3 Urdu", deepgram, audio_inputs),
            "deepgram_nova_3_urdu_keyterms": await run_provider(
                "Deepgram Nova-3 Urdu with keyterms", deepgram_keyterms, audio_inputs
            ),
        },
        "limitations": [
            "Synthetic speech, not real UrduLish speakers or a microphone",
            "Three phrases cannot establish recognition accuracy or a latency percentile",
            "Provider results do not include agent reasoning, TTS, browser playback, or audibility",
        ],
    }


def main() -> None:
    output = ROOT / "artifacts/evaluation/urdu-stt-live-comparison.json"
    result = asyncio.run(run())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
