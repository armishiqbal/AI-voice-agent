"""Run a reproducible, human-reviewable benchmark against local TTS workers."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import wave
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import settings

CASE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
ENGINE_SERVICES = {
    "parler": settings.tts_parler_service_url,
    "chatterbox": settings.tts_chatterbox_service_url,
}
MIN_SHORT_CASES_PER_LANGUAGE = 30
MIN_LONG_CASES_PER_LANGUAGE = 10
MAX_DATASET_BYTES = 5_000_000
MAX_CASES_PER_DATASET = 10_000
MAX_AUDIO_BYTES_PER_CASE = 64 * 1024 * 1024


class TTSBenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=CASE_ID_PATTERN)
    language: str = Field(min_length=2, max_length=12)
    category: str = Field(min_length=1, max_length=64)
    length: Literal["short", "long"]
    text: str = Field(min_length=1, max_length=1200)


class TTSBenchmarkDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=64)
    cases: list[TTSBenchmarkCase] = Field(min_length=1, max_length=MAX_CASES_PER_DATASET)

    @model_validator(mode="after")
    def require_unique_ids(self) -> TTSBenchmarkDataset:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("TTS benchmark case ids must be unique")
        return self


def load_dataset(path: Path) -> TTSBenchmarkDataset:
    try:
        if path.stat().st_size > MAX_DATASET_BYTES:
            raise ValueError("Dataset exceeds the 5 MB size limit")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return TTSBenchmarkDataset.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as error:
        raise ValueError(f"Invalid TTS benchmark dataset: {error}") from error


async def benchmark_worker(
    engine: str,
    base_url: str,
    cases: list[TTSBenchmarkCase],
    output_dir: Path,
    *,
    warmup: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, object]:
    """Synthesize cases on one authenticated worker and save reviewable WAVs."""

    if engine not in ENGINE_SERVICES:
        return _worker_failure(engine, "unknown_engine", "Engine is not allowlisted")
    headers = (
        {"Authorization": f"Bearer {settings.tts_service_token}"}
        if settings.tts_service_token
        else {}
    )
    timeout = httpx.Timeout(settings.tts_timeout_seconds, connect=5.0)
    async with httpx.AsyncClient(
        timeout=timeout, transport=transport, follow_redirects=False
    ) as client:
        try:
            if warmup:
                response = await client.post(f"{base_url}/v1/warmup", headers=headers)
                if response.status_code != 200:
                    return _worker_failure(engine, "warmup_failed", response.status_code)
            ready_response = await client.get(f"{base_url}/readyz", headers=headers)
        except httpx.HTTPError as error:
            return _worker_failure(engine, "service_unreachable", type(error).__name__)
        if ready_response.status_code != 200:
            return _worker_failure(engine, "readiness_failed", ready_response.status_code)
        try:
            readiness = ready_response.json()
            supported_languages = set(readiness["supported_languages"])
            model_id = str(readiness["model_id"])
            device = str(readiness["device"])
            is_ready = readiness["ready"] is True and readiness["model_loaded"] is True
            if readiness["engine"] != engine or not isinstance(
                readiness["supported_languages"], list
            ):
                raise ValueError("TTS worker returned an invalid readiness contract")
        except (KeyError, TypeError, ValueError) as error:
            return _worker_failure(engine, "invalid_readiness_contract", str(error))
        if not is_ready:
            return {
                "engine": engine,
                "status": "model_not_warm",
                "model_id": model_id,
                "device": device,
                "supported_languages": sorted(supported_languages),
                "results": [],
            }

        results: list[dict[str, object]] = []
        for case in cases:
            if case.language not in supported_languages:
                results.append(_case_result(case, "unsupported_language"))
                continue
            results.append(
                await _synthesize_case(
                    client,
                    base_url,
                    headers,
                    engine,
                    case,
                    output_dir / engine,
                )
            )

    return {
        "engine": engine,
        "status": "completed",
        "model_id": model_id,
        "device": device,
        "supported_languages": sorted(supported_languages),
        "coverage": _coverage(cases, supported_languages),
        "latency": _latency_summary(results),
        "results": results,
    }


async def _synthesize_case(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    engine: str,
    case: TTSBenchmarkCase,
    output_dir: Path,
) -> dict[str, object]:
    started = perf_counter()
    first_audio_ms: float | None = None
    payload = bytearray()
    sample_rate = 0
    try:
        async with client.stream(
            "POST",
            f"{base_url}/v1/synthesize",
            headers=headers,
            json={"text": case.text, "language": case.language},
        ) as response:
            if response.status_code != 200:
                return _case_result(case, "request_failed", http_status=response.status_code)
            sample_rate = int(response.headers.get("x-audio-sample-rate", "0"))
            encoding = response.headers.get("x-audio-encoding", "")
            if not 8_000 <= sample_rate <= 96_000 or encoding != "pcm_s16le":
                return _case_result(case, "invalid_audio_format")
            async for chunk in response.aiter_bytes():
                if chunk and first_audio_ms is None:
                    first_audio_ms = (perf_counter() - started) * 1000
                if len(payload) + len(chunk) > MAX_AUDIO_BYTES_PER_CASE:
                    return _case_result(case, "audio_exceeds_size_limit")
                payload.extend(chunk)
    except (httpx.HTTPError, ValueError) as error:
        return _case_result(case, "request_failed", error=type(error).__name__)

    total_ms = (perf_counter() - started) * 1000
    if not payload:
        return _case_result(case, "empty_audio", first_audio_ms=first_audio_ms)
    if len(payload) % 2:
        return _case_result(case, "invalid_pcm16_length", byte_count=len(payload))

    duration_seconds = len(payload) / 2 / sample_rate
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{case.id}.wav"
    try:
        with audio_path.open("xb") as raw_file, wave.open(raw_file, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(payload)
    except FileExistsError:
        return _case_result(case, "artifact_already_exists")

    return {
        **_case_result(case, "synthesized"),
        "first_audio_ms": round(first_audio_ms, 2) if first_audio_ms is not None else None,
        "total_ms": round(total_ms, 2),
        "audio_duration_ms": round(duration_seconds * 1000, 2),
        "real_time_factor": round(total_ms / (duration_seconds * 1000), 3),
        "sample_rate": sample_rate,
        "audio_bytes": len(payload),
        "audio_file": str(audio_path),
    }


def _case_result(case: TTSBenchmarkCase, status: str, **values: object) -> dict[str, object]:
    return {
        "case_id": case.id,
        "language": case.language,
        "category": case.category,
        "length": case.length,
        "text": case.text,
        "status": status,
        **values,
    }


def _worker_failure(engine: str, status: str, detail: object) -> dict[str, object]:
    return {"engine": engine, "status": status, "detail": str(detail), "results": []}


def _coverage(
    cases: list[TTSBenchmarkCase], supported_languages: set[str]
) -> dict[str, dict[str, object]]:
    by_language: dict[str, dict[str, object]] = {}
    for language in sorted({case.language for case in cases}):
        short_count = sum(case.language == language and case.length == "short" for case in cases)
        long_count = sum(case.language == language and case.length == "long" for case in cases)
        supported = language in supported_languages
        by_language[language] = {
            "supported_by_worker": supported,
            "short_cases": short_count,
            "long_cases": long_count,
            "minimum_dataset_coverage_met": supported
            and short_count >= MIN_SHORT_CASES_PER_LANGUAGE
            and long_count >= MIN_LONG_CASES_PER_LANGUAGE,
        }
    return by_language


def _latency_summary(results: list[dict[str, object]]) -> dict[str, object]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for result in results:
        if result["status"] == "synthesized":
            groups[str(result["language"])].append(result)

    summaries: dict[str, object] = {}
    for language, rows in sorted(groups.items()):
        first_audio = [
            float(row["first_audio_ms"]) for row in rows if row["first_audio_ms"] is not None
        ]
        total = [float(row["total_ms"]) for row in rows]
        summaries[language] = {
            "successes": len(rows),
            "first_audio_p50_ms": _percentile(first_audio, 0.5),
            "first_audio_p95_ms": _percentile(first_audio, 0.95),
            "total_p50_ms": _percentile(total, 0.5),
            "total_p95_ms": _percentile(total, 0.95),
            "mean_real_time_factor": round(mean(float(row["real_time_factor"]) for row in rows), 3),
        }
    return summaries


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)], 2)


def write_human_review_csv(path: Path, report: dict[str, object]) -> None:
    fields = [
        "engine",
        "model_id",
        "case_id",
        "language",
        "category",
        "length",
        "text",
        "audio_file",
        "reviewer_1_pronunciation_1_to_5",
        "reviewer_1_intelligibility_1_to_5",
        "reviewer_1_naturalness_1_to_5",
        "reviewer_1_pacing_1_to_5",
        "reviewer_1_voice_consistency_1_to_5",
        "reviewer_1_artifacts_1_to_5",
        "reviewer_1_notes",
        "reviewer_2_pronunciation_1_to_5",
        "reviewer_2_intelligibility_1_to_5",
        "reviewer_2_naturalness_1_to_5",
        "reviewer_2_pacing_1_to_5",
        "reviewer_2_voice_consistency_1_to_5",
        "reviewer_2_artifacts_1_to_5",
        "reviewer_2_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        for worker in report["workers"]:
            for result in worker["results"]:
                if result["status"] != "synthesized":
                    continue
                writer.writerow(
                    {
                        "engine": worker["engine"],
                        "model_id": worker["model_id"],
                        "case_id": result["case_id"],
                        "language": result["language"],
                        "category": result["category"],
                        "length": result["length"],
                        "text": result["text"],
                        "audio_file": result["audio_file"],
                    }
                )


async def run_benchmark(
    dataset: TTSBenchmarkDataset,
    output_dir: Path,
    *,
    warmup: bool = False,
    services: dict[str, str | None] | None = None,
) -> dict[str, object]:
    selected_services = ENGINE_SERVICES if services is None else services
    workers: list[dict[str, object]] = []
    for engine, base_url in selected_services.items():
        if base_url is None:
            workers.append(_worker_failure(engine, "service_not_configured", "URL missing"))
            continue
        workers.append(
            await benchmark_worker(
                engine,
                base_url.rstrip("/"),
                dataset.cases,
                output_dir / "audio",
                warmup=warmup,
            )
        )
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_version": dataset.version,
        "case_count": len(dataset.cases),
        "minimum_coverage": {
            "short_per_language": MIN_SHORT_CASES_PER_LANGUAGE,
            "long_per_language": MIN_LONG_CASES_PER_LANGUAGE,
        },
        "workers": workers,
        "human_review": "not_evaluated",
        "release_gate": "not_evaluated",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the configured open-source TTS workers; does not download models."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="Explicitly load/warm each configured model before benchmarking.",
    )
    arguments = parser.parse_args()
    dataset = load_dataset(arguments.dataset)
    output_dir = arguments.output_dir or Path("artifacts/tts-benchmark") / datetime.now(
        UTC
    ).strftime("%Y%m%dT%H%M%SZ")
    if any((output_dir / artifact).exists() for artifact in ("report.json", "human-review.csv")):
        raise SystemExit(
            "Output directory already contains report artifacts; choose a new directory"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run_benchmark(dataset, output_dir, warmup=arguments.warmup))
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_human_review_csv(output_dir / "human-review.csv", report)
    print(
        json.dumps(
            {"report": str(report_path), "workers": report["workers"]}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
