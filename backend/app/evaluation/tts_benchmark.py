from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.integrations.tts.router import TTSProvider, TTSProviderError


@dataclass(frozen=True)
class TTSBenchmarkRow:
    provider: str
    phrase_id: str
    first_audio_ms: float | None
    total_ms: float | None
    bytes_received: int
    chunk_count: int
    encodings: tuple[str, ...]
    error: str | None


async def benchmark_provider(
    provider: TTSProvider, phrases: list[tuple[str, str]], audio_directory: Path | None = None
) -> list[TTSBenchmarkRow]:
    rows: list[TTSBenchmarkRow] = []
    for phrase_id, text in phrases:
        started = time.perf_counter()
        first_audio: float | None = None
        received = 0
        chunk_count = 0
        encodings: set[str] = set()
        error: str | None = None
        recording = bytearray()
        try:
            async for chunk in provider.synthesize_stream(text, "ur-Latn"):
                if chunk.audio and first_audio is None:
                    first_audio = (time.perf_counter() - started) * 1000
                if audio_directory is not None:
                    if len(recording) + len(chunk.audio) > 10_000_000:
                        raise TTSProviderError("Benchmark recording exceeded 10 MB")
                    recording.extend(chunk.audio)
                received += len(chunk.audio)
                chunk_count += 1
                encodings.add(chunk.encoding)
            if received == 0:
                raise TTSProviderError("Provider returned no audio")
        except TTSProviderError as exc:
            error = str(exc)
        if audio_directory is not None and error is None and recording:
            if encodings != {"audio/mpeg"}:
                raise ValueError("Recording export currently supports MPEG providers only")
            audio_directory.mkdir(parents=True, exist_ok=True)
            name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{provider.name}-{phrase_id}")
            (audio_directory / f"{name}.mp3").write_bytes(recording)
        rows.append(
            TTSBenchmarkRow(
                provider.name,
                phrase_id,
                first_audio,
                (time.perf_counter() - started) * 1000 if error is None else None,
                received,
                chunk_count,
                tuple(sorted(encodings)),
                error,
            )
        )
    return rows


def rows_as_dict(rows: list[TTSBenchmarkRow]) -> list[dict[str, object]]:
    return [asdict(row) for row in rows]
