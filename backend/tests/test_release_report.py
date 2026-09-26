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
    monkeypatch.setattr(release, "build_openai_realtime_stt", lambda config: SimpleNamespace(is_ready=AsyncMock(return_value=True)))
    monkeypatch.setattr(release, "build_openai_tts_router", lambda config: SimpleNamespace(readiness=AsyncMock(return_value={"*": True})))
    report = release.build_release_report(Path(__file__).resolve().parents[2], Settings(_env_file=None))
    assert report["provider_readiness"]["openai_voice_ready"] is True
    assert report["provider_readiness"]["standard_voice_ready"] is False
    assert report["gates"]["live_voice_latency"]["status"] == "requires live measurement"
    assert report["multiturn_conversations"]["total"] >= 40
