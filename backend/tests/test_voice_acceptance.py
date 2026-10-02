import asyncio
import json
import sys

import pytest

from app.evaluation.voice_acceptance import voice_acceptance_failures


def test_latency_summary_reports_nearest_rank_and_sample_eligibility() -> None:
    from scripts.evaluation.live_voice_latency import summarize_latency

    turns = [
        {"last_voice_to_substantive_audio_ms": value}
        for value in range(100, 120)
    ]

    summary = summarize_latency(turns)

    assert summary["last_voice_to_substantive_audio_ms"] == {
        "sample_count": 20,
        "p50": 109.0,
        "p95": 118.0,
        "min": 100.0,
        "max": 119.0,
        "p95_sample_eligible": True,
    }
    assert summary["agent_decision_latency_ms"]["sample_count"] == 0
    assert summary["agent_decision_latency_ms"]["p95_sample_eligible"] is False


def test_multi_session_voice_run_summarizes_sessions_and_partial_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.evaluation import live_voice_latency

    successful_turn = {
        "final_transcript_received": True,
        "transcription_recovery": False,
        "final_audio_received": True,
        "audio_bytes": 200,
        "last_voice_to_first_audio_ms": 900,
        "last_voice_to_substantive_audio_ms": 1_500,
    }

    async def session_succeeded(*args):
        return {
            "status": "completed",
            "turns": [dict(successful_turn) for _ in range(3)],
            "acceptance_status": "passed",
            "acceptance_failures": [],
        }

    class SessionFailed(RuntimeError):
        def __init__(self) -> None:
            super().__init__("provider timed out")
            self.turns = [dict(successful_turn)]
            self.failed_turn = {"failure": "timeout", "final_audio_received": False}

    async def session_failed(*args):
        raise SessionFailed()

    outcomes = iter((session_succeeded, session_failed))

    async def run_session(*args):
        return await next(outcomes)(*args)

    monkeypatch.setattr(live_voice_latency, "_run_once", run_session)
    result = asyncio.run(live_voice_latency.run("http://localhost:8000", runs=2))

    assert result["status"] == "partial"
    assert result["acceptance_status"] == "failed"
    assert result["runs_completed"] == 1
    assert result["completed_turn_count"] == 4
    assert result["observed_turn_count"] == 5
    assert result["latency_summary_ms"]["last_voice_to_substantive_audio_ms"]["sample_count"] == 4
    assert "session_failed" in result["acceptance_failures"]


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
