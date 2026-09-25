from __future__ import annotations

import json
import wave

import httpx
import pytest

from app.evaluation import oss_tts_benchmark as benchmark


@pytest.mark.asyncio
async def test_benchmark_worker_saves_pcm_wav_and_marks_unsupported_language(
    tmp_path, monkeypatch
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/readyz":
            return httpx.Response(
                200,
                json={
                    "ready": True,
                    "engine": "parler",
                    "model_id": "model@revision",
                    "supported_languages": ["en"],
                    "model_loaded": True,
                    "device": "cpu",
                },
            )
        assert request.url.path == "/v1/synthesize"
        assert json.loads(request.content) == {"text": "Hello property seeker.", "language": "en"}
        return httpx.Response(
            200,
            headers={
                "x-audio-sample-rate": "24000",
                "x-audio-encoding": "pcm_s16le",
            },
            content=b"\x00\x01" * 240,
        )

    monkeypatch.setattr(benchmark.settings, "tts_service_token", "worker-secret")
    dataset_cases = [
        benchmark.TTSBenchmarkCase(
            id="english-greeting",
            language="en",
            category="greeting",
            length="short",
            text="Hello property seeker.",
        ),
        benchmark.TTSBenchmarkCase(
            id="arabic-greeting",
            language="ar",
            category="greeting",
            length="short",
            text="مرحبا",
        ),
    ]

    result = await benchmark.benchmark_worker(
        "parler",
        "https://tts.example.test",
        dataset_cases,
        tmp_path,
        transport=httpx.MockTransport(handler),
    )

    assert result["status"] == "completed"
    assert result["model_id"] == "model@revision"
    assert [row["status"] for row in result["results"]] == [
        "synthesized",
        "unsupported_language",
    ]
    assert all(request.headers["authorization"] == "Bearer worker-secret" for request in requests)
    audio_path = tmp_path / "parler" / "english-greeting.wav"
    with wave.open(str(audio_path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 24_000
        assert audio.getnframes() == 240
    original_audio = audio_path.read_bytes()

    repeated = await benchmark.benchmark_worker(
        "parler",
        "https://tts.example.test",
        dataset_cases[:1],
        tmp_path,
        transport=httpx.MockTransport(handler),
    )
    assert repeated["results"][0]["status"] == "artifact_already_exists"
    assert audio_path.read_bytes() == original_audio


@pytest.mark.asyncio
async def test_benchmark_rejects_audio_that_exceeds_the_per_case_limit(
    tmp_path, monkeypatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/readyz":
            return httpx.Response(
                200,
                json={
                    "ready": True,
                    "engine": "parler",
                    "model_id": "model",
                    "supported_languages": ["en"],
                    "model_loaded": True,
                    "device": "cpu",
                },
            )
        return httpx.Response(
            200,
            headers={
                "x-audio-sample-rate": "24000",
                "x-audio-encoding": "pcm_s16le",
            },
            content=b"\x00\x01" * 3,
        )

    monkeypatch.setattr(benchmark, "MAX_AUDIO_BYTES_PER_CASE", 4)
    case = benchmark.TTSBenchmarkCase(
        id="english-long",
        language="en",
        category="property_description",
        length="long",
        text="A long property description.",
    )
    result = await benchmark.benchmark_worker(
        "parler",
        "https://tts.example.test",
        [case],
        tmp_path,
        transport=httpx.MockTransport(handler),
    )
    assert result["results"][0]["status"] == "audio_exceeds_size_limit"
    assert not (tmp_path / "parler" / "english-long.wav").exists()


def test_benchmark_dataset_rejects_duplicate_ids_and_bad_case_ids() -> None:
    case = {
        "id": "same-case",
        "language": "ur-Latn",
        "category": "greeting",
        "length": "short",
        "text": "Assalam-o-Alaikum.",
    }
    with pytest.raises(ValueError, match="unique"):
        benchmark.TTSBenchmarkDataset.model_validate({"version": "v1", "cases": [case, case]})

    with pytest.raises(ValueError):
        benchmark.TTSBenchmarkCase(
            id="../not-a-safe-file-name",
            language="en",
            category="greeting",
            length="short",
            text="Hello.",
        )


def test_dataset_coverage_is_not_mislabeled_as_quality_acceptance() -> None:
    cases = [
        benchmark.TTSBenchmarkCase(
            id="en-short",
            language="en",
            category="greeting",
            length="short",
            text="Hello.",
        )
    ]
    report = benchmark._coverage(cases, {"en"})
    assert report["en"]["minimum_dataset_coverage_met"] is False


def test_benchmark_dataset_file_size_is_bounded(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "oversized.json"
    dataset_path.write_text(" ", encoding="utf-8")
    monkeypatch.setattr(benchmark, "MAX_DATASET_BYTES", 0)
    with pytest.raises(ValueError, match="5 MB"):
        benchmark.load_dataset(dataset_path)
