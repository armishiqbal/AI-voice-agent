import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.evaluation import release
from app.integrations.providers import ProviderReadiness


def test_release_accepts_openai_voice_without_claiming_latency(monkeypatch) -> None:
    monkeypatch.setattr(release, "provider_readiness", lambda config: ProviderReadiness(
        deepgram=False, openai=True, fish_audio=False, elevenlabs=False, pinecone=False,
        multilingual_tts=False, calendar=False, gmail=False, telephony=False,
    ))
    monkeypatch.setattr(
        release,
        "build_openai_realtime_stt",
        lambda config: SimpleNamespace(
            is_ready=AsyncMock(return_value=True),
            warmup=AsyncMock(return_value=True),
            aclose=AsyncMock(),
        ),
    )
    monkeypatch.setattr(release, "build_openai_tts_router", lambda config: SimpleNamespace(readiness=AsyncMock(return_value={"*": True})))
    monkeypatch.setattr(release, "build_tts_router", lambda config: SimpleNamespace(readiness=AsyncMock(return_value={"ur-Latn": True, "en": True})))
    report = release.build_release_report(Path(__file__).resolve().parents[2], Settings(_env_file=None))
    assert report["provider_readiness"]["openai_voice_ready"] is True
    assert report["provider_readiness"]["standard_voice_ready"] is False
    assert report["gates"]["live_voice_latency"]["status"] == "requires physical-microphone, human-quality, and p95 measurement"
    assert report["multiturn_conversations"]["total"] >= 40


def test_release_report_uses_live_readiness_when_supplied(monkeypatch) -> None:
    monkeypatch.setattr(release, "provider_readiness", lambda config: ProviderReadiness(
        deepgram=False, openai=False, fish_audio=False, elevenlabs=False, pinecone=False,
        multilingual_tts=False, calendar=False, gmail=False, telephony=False,
    ))
    monkeypatch.setattr(
        release,
        "build_openai_realtime_stt",
        lambda config: SimpleNamespace(
            is_ready=AsyncMock(return_value=False),
            warmup=AsyncMock(return_value=False),
            aclose=AsyncMock(),
        ),
    )
    monkeypatch.setattr(release, "build_openai_tts_router", lambda config: SimpleNamespace(readiness=AsyncMock(return_value={"*": False})))
    monkeypatch.setattr(release, "build_tts_router", lambda config: SimpleNamespace(readiness=AsyncMock(return_value={"ur-Latn": False, "en": False})))
    report = release.build_release_report(
        Path(__file__).resolve().parents[2],
        Settings(_env_file=None),
        {
            "status": "ready",
            "mode": "live",
            "providers": {"live_voice_pipeline_ready": True},
        },
    )

    assert report["provider_readiness"]["live_voice_pipeline_ready"] is False
    assert report["gates"]["live_voice_latency"]["provider_readiness"] is True
    assert report["gates"]["live_voice_latency"]["readiness_source"] == "live_api"
    assert report["runtime_readiness"]["status"] == "ready"


def test_runtime_readiness_sanitizes_provider_payload(monkeypatch) -> None:
    response = SimpleNamespace(
        is_success=True,
        status_code=200,
        json=lambda: {
            "status": "ready",
            "mode": "live",
            "application": {"database_ready": True, "internal_detail": "discard"},
            "structured_reasoning": {"status": "provider_error", "raw_error": "discard"},
            "live_voice": {"status": "configured_unverified", "verification": "configuration_only"},
            "providers": {"hybrid_voice_ready": True, "live_voice_pipeline_ready": True, "bad": "discard"},
            "secret": "discard",
        },
    )
    monkeypatch.setattr(release.httpx, "get", lambda *args, **kwargs: response)

    readiness = release.read_runtime_readiness("http://localhost:8000/")

    assert readiness == {
        "status": "ready",
        "mode": "live",
        "database_ready": True,
        "structured_reasoning_status": "provider_error",
        "live_voice_status": "configured_unverified",
        "live_voice_verification": "configuration_only",
        "providers": {"hybrid_voice_ready": True, "live_voice_pipeline_ready": True},
    }


def test_fresh_synthetic_voice_smoke_is_reported_without_passing_human_gate(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "evaluation" / "live-voice-latency-hybrid-current.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "voice_mode": "hybrid",
        "turns": [
            {"final_transcript_received": True, "transcription_recovery": False, "final_audio_received": True, "audio_bytes": 200, "last_voice_to_substantive_audio_ms": 1_500},
            {"final_transcript_received": True, "transcription_recovery": False, "final_audio_received": True, "audio_bytes": 300, "last_voice_to_substantive_audio_ms": 1_700},
        ],
    }))

    smoke = release.load_synthetic_voice_smoke(tmp_path)

    assert smoke["status"] == "passed synthetic loopback"
    assert smoke["all_substantive_answers_under_two_seconds"] is True
    assert "excludes physical mic" in smoke["scope"]


def test_synthetic_audio_delivery_reports_latency_misses_separately(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "evaluation" / "live-voice-latency-hybrid-current.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "voice_mode": "hybrid",
        "turns": [
            {"final_transcript_received": True, "transcription_recovery": False, "final_audio_received": True, "audio_bytes": 200, "last_voice_to_substantive_audio_ms": 1_500},
            {"final_transcript_received": True, "transcription_recovery": False, "final_audio_received": True, "audio_bytes": 300, "last_voice_to_substantive_audio_ms": 2_500},
        ],
    }))

    smoke = release.load_synthetic_voice_smoke(tmp_path)

    assert smoke["status"] == "completed synthetic loopback with latency misses"
    assert smoke["final_audio_on_every_turn"] is True
    assert smoke["latency_target_met_on_every_turn"] is False


def test_fast_spoken_recovery_is_not_passed_as_a_successful_voice_loop(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "evaluation" / "live-voice-latency-hybrid-current.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "voice_mode": "hybrid",
        "turns": [
            {
                "final_transcript_received": False,
                "transcription_recovery": True,
                "final_audio_received": True,
                "audio_bytes": 200,
                "last_voice_to_substantive_audio_ms": 500,
            }
        ],
    }))

    smoke = release.load_synthetic_voice_smoke(tmp_path)

    assert smoke["status"] == "completed synthetic loopback with transcript misses"
    assert smoke["final_audio_on_every_turn"] is True
    assert smoke["latency_target_met_on_every_turn"] is True
    assert smoke["acceptance_status"] == "failed"
    assert smoke["acceptance_failures"] == ["final_transcript_missing"]


def test_failed_synthetic_voice_smoke_invalidates_previous_success(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "evaluation" / "live-voice-latency-hybrid-current.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "status": "failed",
        "voice_mode": "hybrid",
        "failure": "Live voice run stopped on turn 2: provider unavailable",
        "turns": [
            {"final_audio_received": True, "audio_bytes": 200},
        ],
    }))

    smoke = release.load_synthetic_voice_smoke(tmp_path)

    assert smoke["status"] == "failed synthetic voice loop"
    assert smoke["completed_turn_count"] == 1
    assert "provider unavailable" in smoke["failure"]


def test_partial_synthetic_voice_smoke_is_not_reported_as_passed(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "evaluation" / "live-voice-latency-hybrid-current.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "status": "partial",
        "voice_mode": "hybrid",
        "completed_turn_count": 3,
        "observed_turn_count": 4,
        "turns": [{"final_audio_received": True} for _ in range(4)],
        "sessions": [{"status": "failed", "failure": "provider timeout"}],
    }))

    smoke = release.load_synthetic_voice_smoke(tmp_path)

    assert smoke["status"] == "incomplete synthetic voice loop"
    assert smoke["completed_turn_count"] == 3
    assert smoke["failure"] == "provider timeout"


def test_stale_synthetic_voice_smoke_is_not_counted_as_current(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "evaluation" / "live-voice-latency-hybrid-current.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"voice_mode": "hybrid", "turns": []}))
    old = time.time() - (25 * 60 * 60)
    os.utime(path, (old, old))

    smoke = release.load_synthetic_voice_smoke(tmp_path)

    assert smoke["status"] == "stale; rerun the synthetic voice loop"
