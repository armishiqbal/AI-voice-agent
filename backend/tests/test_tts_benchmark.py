from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.evaluation.tts_benchmark import benchmark_provider
from app.integrations.tts.router import AudioChunk, TTSProviderError


class RecordingProvider:
    name = "test-provider"

    async def is_ready(self) -> bool:
        return True

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        yield AudioChunk(0, b"one", language, encoding="audio/mpeg")
        if text == "fail":
            raise TTSProviderError("fixture failure")
        yield AudioChunk(1, b"two", language, encoding="audio/mpeg")


@pytest.mark.asyncio
async def test_benchmark_records_only_completed_streams(tmp_path: Path) -> None:
    rows = await benchmark_provider(
        RecordingProvider(), [("good", "ok"), ("bad", "fail")], tmp_path
    )
    assert (tmp_path / "test-provider-good.mp3").read_bytes() == b"onetwo"
    assert not (tmp_path / "test-provider-bad.mp3").exists()
    assert rows[0].bytes_received == 6
    assert rows[1].error == "fixture failure"
    assert rows[1].total_ms is None
