"""Benchmark Fish Audio and ElevenLabs without declaring a winner.

The machine-measured fields are intentionally separated from human judgements. A successful
request is not evidence of good Urdu pronunciation, naturalness, voice cloning, or commercial
cost; those fields require the review protocol in ``docs/TTS_EVALUATION.md``.
"""

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phrase", action="append", help="Additional phrase; repeat for a custom set")
    parser.add_argument("--audio-dir", type=Path, help="Save synthetic benchmark recordings for blinded review")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.core.config import settings
    from app.evaluation.tts_benchmark import benchmark_provider, rows_as_dict
    from app.integrations.tts.elevenlabs import ElevenLabsStreamingProvider
    from app.integrations.tts.fish import FishAudioStreamingProvider

    default_phrases = [
        "Assalam-o-Alaikum, aap ka budget aur preferred city kya hai?",
        "Mujhe Karachi mein available property details chahiye.",
        "DHA Phase 6 mein teen bedroom ka option available hai?",
        "Is property ka payment plan aur down payment kya hai?",
        "Acha, Clifton ya DHA mein koi sasti option dikhain.",
        "I need a rental apartment near a hospital and school.",
        "Lahore mein commercial office ke liye options bata dein.",
        "Investment ke liye expected return ke bare mein verified detail chahiye.",
        "آپ کے پاس اسلام آباد میں گھر کے آپشنز ہیں؟",
        "آپ اس پراپرٹی کی قیمت اور سہولیات بتا سکتے ہیں؟",
        "Please repeat the appointment time slowly.",
        "Monday se Saturday, ten thirty PKT confirm kar dein.",
        "Mujhe English aur Urdu mix mein jawab dein.",
        "What happens if I need to reschedule my visit?",
        "Yeh location family ke liye suitable hai ya nahi?",
        "Builder ke verified documents aur maintenance charges kya hain?",
        "Namaste, mujhe Hindi mein property options chahiye.",
        "مرحبا، أريد خيارات عقارية في كراتشي.",
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਮੈਨੂੰ ਕਿਰਾਏ ਦਾ ਘਰ ਚਾਹੀਦਾ ਹੈ।",
        "আপনি কি ঢাকায় নয়, লাহোরে সম্পত্তি দেখাতে পারেন?",
    ]
    phrases = [(f"phrase-{index + 1:02d}", value) for index, value in enumerate(args.phrase or default_phrases)]

    def summarize(rows: list[object]) -> dict[str, object]:
        successful = [row for row in rows if row.total_ms is not None]
        first_audio = sorted(row.first_audio_ms for row in successful if row.first_audio_ms is not None)
        total = sorted(row.total_ms for row in successful if row.total_ms is not None)
        percentile = lambda values, fraction: round(values[max(0, int(len(values) * fraction) - 1)], 2) if values else None
        return {
            "successful_phrases": len(successful),
            "errors": len(rows) - len(successful),
            "first_audio_p50_ms": percentile(first_audio, 0.50),
            "first_audio_p95_ms": percentile(first_audio, 0.95),
            "total_p50_ms": percentile(total, 0.50),
            "total_p95_ms": percentile(total, 0.95),
            "mean_total_ms": round(statistics.mean(total), 2) if total else None,
        }

    async def run() -> None:
        rows = []
        for provider in (
            FishAudioStreamingProvider(settings.fish_audio_api_key, settings.fish_audio_model, settings.fish_audio_sample_rate),
            ElevenLabsStreamingProvider(settings.elevenlabs_api_key, settings.elevenlabs_voice_id or "", settings.elevenlabs_model),
        ):
            rows.extend(await benchmark_provider(provider, phrases, args.audio_dir))
        print(
            json.dumps(
                {
                    "winner": None,
                    "reason": "No automatic winner. Review the same phrase rows for pronunciation, naturalness, code-switching, voice cloning, commercial cost, and streaming continuity.",
                    "phrase_count": len(phrases),
                    "protocol": {
                        "machine_metrics": ["first_audio_ms", "total_ms", "bytes_received", "chunk_count", "encodings", "error"],
                        "manual_metrics": ["urdu_pronunciation", "code_switching", "naturalness", "intelligibility", "emotion_restraint", "voice_consistency", "voice_cloning", "commercial_cost"],
                        "manual_scores": "not_evaluated",
                    },
                    "summaries": {provider: summarize([row for row in rows if row.provider == provider]) for provider in {row.provider for row in rows}},
                    "rows": rows_as_dict(rows),
                },
                indent=2,
            )
        )

    asyncio.run(run())
