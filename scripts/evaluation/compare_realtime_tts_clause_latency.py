"""Compare first-audio latency for whole replies versus sentence-level TTS requests.

This is a provider-billed diagnostic. It warms each session with the same short
acknowledgement used by the live call path, validates complete speech output, and
does not represent STT, agent, browser playback, human quality, or p95 latency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.integrations.tts.openai_realtime import OpenAIRealtimeSpeechProvider
from app.services.voice_stream import (
    pipeline_synthesize_clauses,
    split_conversational_clauses,
)

PHRASES = (
    "50,000,000 PKR budget note kar liya. Karachi ke liye aap ghar khareedna chahte hain ya rent par lena hai?",
    "Verified listings abhi load nahi hain. Karachi ke liye 50,000,000 PKR budget note kar liya; data load hote hi check karunga.",
)


async def measure_first_audio(text: str, split_clauses: bool) -> float:
    provider = OpenAIRealtimeSpeechProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_realtime_tts_model,
        voice=settings.openai_tts_voice,
    )
    try:
        if not await provider.warmup():
            raise RuntimeError("Realtime TTS warmup failed")
        async for _ in provider.synthesize_stream("Ji, dekh raha hoon.", "ur-Latn"):
            pass

        started = time.perf_counter()
        first_audio_ms: float | None = None
        async for chunk in pipeline_synthesize_clauses(
            provider, text, "ur-Latn", enabled=split_clauses
        ):
            if chunk.audio and first_audio_ms is None:
                first_audio_ms = (time.perf_counter() - started) * 1000
        if first_audio_ms is None:
            raise RuntimeError("TTS returned no audio")
        return round(first_audio_ms, 1)
    finally:
        await provider.aclose()


async def run(repeats: int) -> dict[str, object]:
    samples: list[dict[str, object]] = []
    for phrase_index, phrase in enumerate(PHRASES):
        for repeat in range(repeats):
            order = (repeat + phrase_index) % 2
            measured: dict[str, float] = {}
            strategies = (False, True) if order == 0 else (True, False)
            for split in strategies:
                strategy = "sentence_level" if split else "single_request"
                measured[strategy] = await measure_first_audio(phrase, split)
            samples.append(
                {
                    "phrase": phrase,
                    "clauses": split_conversational_clauses(phrase),
                    "repeat": repeat + 1,
                    **measured,
                }
            )

    single = [float(row["single_request"]) for row in samples]
    sentence = [float(row["sentence_level"]) for row in samples]
    return {
        "method": "Paired session-warmed OpenAI Realtime TTS; each response was fully synthesized and transcript-validated. First non-empty audio latency only.",
        "provider": "OpenAI Realtime TTS",
        "repeats_per_phrase": repeats,
        "sample_count": len(samples),
        "single_request_median_ms": round(statistics.median(single), 1),
        "sentence_level_median_ms": round(statistics.median(sentence), 1),
        "limitation": "Provider-only diagnostic; excludes STT, agent, network transit, browser playback, human speech quality, and latency percentiles.",
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 10:
        parser.error("--repeats must be between 1 and 10")
    report = asyncio.run(run(args.repeats))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
