import json
import sys

import pytest

from app.evaluation.voice_acceptance import voice_acceptance_failures


def test_voice_acceptance_requires_final_transcript_audio_and_sub_two_second_answer() -> None:
    turns = [
        {
            "final_transcript_received": True,
            "transcription_recovery": False,
            "final_audio_received": True,
            "audio_bytes": 8000,
            "last_voice_to_substantive_audio_ms": 1_999,
        }
    ]

    assert voice_acceptance_failures(turns, target_ms=2_000) == []


def test_voice_acceptance_does_not_count_acknowledgement_as_an_answer() -> None:
    turns = [
        {
            "final_transcript_received": False,
            "transcription_recovery": True,
            "final_audio_received": True,
            "audio_bytes": 8000,
            "last_voice_to_acknowledgement_audio_ms": 430,
            "last_voice_to_substantive_audio_ms": 7_700,
        }
    ]

    assert voice_acceptance_failures(turns, target_ms=2_000) == [
        "final_transcript_missing",
        "substantive_response_over_target",
    ]


def test_voice_acceptance_rejects_missing_final_audio_and_empty_runs() -> None:
    assert voice_acceptance_failures([], target_ms=2_000) == ["no_turns"]
    assert voice_acceptance_failures(
        [
            {
                "final_transcript_received": True,
                "transcription_recovery": False,
                "final_audio_received": False,
                "audio_bytes": 0,
                "last_voice_to_substantive_audio_ms": None,
            }
        ],
        target_ms=2_000,
    ) == ["final_audio_missing", "substantive_audio_missing"]


def test_live_voice_cli_preserves_failed_artifact_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from scripts.evaluation import live_voice_latency

    report = {
        "status": "completed",
        "acceptance_status": "failed",
        "acceptance_failures": ["substantive_response_over_target"],
    }
    artifact = tmp_path / "live-voice.json"
    monkeypatch.setattr(live_voice_latency, "run", lambda *args: report)
    monkeypatch.setattr(live_voice_latency.asyncio, "run", lambda awaitable: awaitable)
    monkeypatch.setattr(
        sys,
        "argv",
        ["live_voice_latency.py", "--voice-mode", "openai", "--output", str(artifact)],
    )

    with pytest.raises(SystemExit) as error:
        live_voice_latency.main()

    assert error.value.code == 1
    assert json.loads(artifact.read_text()) == report
