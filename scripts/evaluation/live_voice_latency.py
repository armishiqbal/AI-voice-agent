"""Exercise the live local browser voice WebSocket with generated speech.

This is a live provider smoke check, not a human quality or physical-microphone test.
Caller input defaults to local macOS speech so an exhausted input-synthesis account does not
prevent verification of the real STT, agent and TTS route.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import struct
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.evaluation.voice_acceptance import voice_acceptance_failures
from app.integrations.tts.openai_realtime import (
    OpenAIRealtimeSpeechProvider,
)

ORIGIN = "http://localhost:5173"
FRAME_SAMPLES_16K = round(16_000 * 4096 / 48_000)
FRAME_SECONDS = 4096 / 48_000
SILENCE_FRAMES = 5  # 426.7 ms, just over the browser's 425 ms VAD threshold.
MACOS_SAY_TIMEOUT_SECONDS = 20
PHRASES = (
    "Mujhe Karachi mein ghar chahiye, mera budget paanch crore hai.",
    "Rent par lena hai.",
    "DHA mein koi sasti option hai?",
)


class LiveVoiceSmokeError(RuntimeError):
    """A failed smoke run that retains turns completed before the failure."""

    def __init__(
        self,
        message: str,
        turns: list[dict[str, Any]],
        failed_turn: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.turns = turns
        self.failed_turn = failed_turn


class LiveVoiceTurnFailure(RuntimeError):
    """A failed turn together with bounded, transcript-only diagnostics."""

    def __init__(self, message: str, partial_turn: dict[str, Any]) -> None:
        super().__init__(message)
        self.partial_turn = partial_turn


def resample_24k_to_16k(audio: bytes) -> bytes:
    if len(audio) % 2:
        raise ValueError("Synthetic provider audio is not complete PCM16")
    samples = [sample[0] for sample in struct.iter_unpack("<h", audio)]
    if not samples:
        return b""
    output_count = max(1, round(len(samples) * 2 / 3))
    output: list[int] = []
    for index in range(output_count):
        source = index * 1.5
        left = min(int(source), len(samples) - 1)
        right = min(left + 1, len(samples) - 1)
        fraction = source - left
        value = round(samples[left] * (1 - fraction) + samples[right] * fraction)
        output.append(max(-32768, min(32767, value)))
    return struct.pack(f"<{len(output)}h", *output)


async def synthesize_openai_inputs() -> list[bytes]:
    provider = OpenAIRealtimeSpeechProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_realtime_tts_model,
        voice=settings.openai_tts_voice,
    )
    results: list[bytes] = []
    try:
        for phrase in PHRASES:
            chunks = bytearray()
            async for chunk in provider.synthesize_stream(phrase, "ur-Latn"):
                chunks.extend(chunk.audio)
            if not chunks:
                raise RuntimeError("The speech provider returned no generated input audio")
            results.append(resample_24k_to_16k(bytes(chunks)))
    finally:
        await provider.aclose()
    return results


def synthesize_macos_inputs() -> list[bytes]:
    """Create local 16 kHz speech input without spending provider credits."""

    if sys.platform != "darwin":
        raise RuntimeError("macOS speech input is available only on macOS; select openai-realtime")
    results: list[bytes] = []
    with tempfile.TemporaryDirectory(prefix="awaaz-live-voice-") as directory:
        for index, phrase in enumerate(PHRASES, start=1):
            output_path = Path(directory) / f"turn-{index}.wav"
            try:
                subprocess.run(
                    [
                        "say",
                        "--file-format=WAVE",
                        "--data-format=LEI16@16000",
                        f"--output-file={output_path}",
                        phrase,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=MACOS_SAY_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(
                    f"macOS speech synthesis timed out for generated turn {index}"
                ) from error
            with wave.open(str(output_path), "rb") as source:
                if (
                    source.getnchannels() != 1
                    or source.getsampwidth() != 2
                    or source.getframerate() != 16_000
                    or source.getcomptype() != "NONE"
                ):
                    raise RuntimeError("macOS speech input did not produce mono PCM16 at 16 kHz")
                audio = source.readframes(source.getnframes())
            if not audio:
                raise RuntimeError(f"macOS speech input was empty for turn {index}")
            results.append(audio)
    return results


async def receive_json(websocket: Any, deadline: float) -> dict[str, Any]:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise TimeoutError("Timed out waiting for the live voice service")
    message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=remaining))
    if not isinstance(message, dict):
        raise TypeError("Voice service returned a malformed event")
    return message


async def wait_for_state(websocket: Any, state: str, timeout_seconds: float = 20) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        event = await receive_json(websocket, deadline)
        if event.get("type") == "state" and event.get("state") == state:
            return
        if event.get("type") in {"error", "stt_unavailable"}:
            raise RuntimeError(
                f"Voice setup failed: {event.get('type')} ({event.get('reason') or 'no reason code'})"
            )


async def send_paced_audio(websocket: Any, audio: bytes) -> float:
    if len(audio) % 2:
        raise ValueError("Input frame source is not complete PCM16")
    samples = memoryview(audio).cast("h")
    frame_count = (len(samples) + FRAME_SAMPLES_16K - 1) // FRAME_SAMPLES_16K
    loop = asyncio.get_running_loop()
    started = loop.time()
    last_voice_sent_at = started
    for index in range(frame_count):
        start = index * FRAME_SAMPLES_16K
        end = min(start + FRAME_SAMPLES_16K, len(samples))
        await websocket.send(samples[start:end].tobytes())
        last_voice_sent_at = loop.time()
        if index + 1 < frame_count:
            target = started + (index + 1) * FRAME_SECONDS
            await asyncio.sleep(max(0, target - loop.time()))
    for silence_index in range(SILENCE_FRAMES):
        await websocket.send(bytes(FRAME_SAMPLES_16K * 2))
        target = last_voice_sent_at + (silence_index + 1) * FRAME_SECONDS
        await asyncio.sleep(max(0, target - loop.time()))
    await websocket.send(json.dumps({"type": "audio_turn_end"}))
    return last_voice_sent_at


async def run_turn(websocket: Any, phrase: str, audio: bytes, number: int) -> dict[str, Any]:
    await websocket.send(json.dumps({"type": "audio_turn_start"}))
    last_voice_sent_at = await send_paced_audio(websocket, audio)
    timeline_started_at = time.perf_counter()
    event_timeline: list[dict[str, object]] = []
    deadline = asyncio.get_running_loop().time() + 45
    first_audio_at: float | None = None
    first_acknowledgement_at: float | None = None
    first_substantive_audio_at: float | None = None
    transcript: str | None = None
    reply: str | None = None
    audio_bytes = 0
    final_audio = False
    final_transcript_at: float | None = None
    decision_latency_ms: float | None = None
    response_reason: str | None = None
    latest_transcript: str | None = None
    latest_transcript_status: dict[str, object] | None = None

    def record_timeline(event_name: str) -> None:
        event_timeline.append(
            {"event": event_name, "elapsed_ms": round((time.perf_counter() - timeline_started_at) * 1000, 1)}
        )

    def partial_turn(failure: str | None = None) -> dict[str, Any]:
        return {
            "turn": number,
            "input_phrase": phrase,
            "latest_transcript": latest_transcript,
            "latest_transcript_status": latest_transcript_status,
            "reply": reply,
            "agent_decision_latency_ms": decision_latency_ms,
            "response_reason": response_reason,
            "transcription_recovery": response_reason == "transcription_incomplete",
            "final_transcript_received": final_transcript_at is not None,
            "event_timeline_from_last_voice_frame": event_timeline,
            "last_voice_to_final_transcript_ms": round(
                (final_transcript_at - last_voice_sent_at) * 1000, 1
            ) if final_transcript_at else None,
            "last_voice_to_acknowledgement_audio_ms": round(
                (first_acknowledgement_at - last_voice_sent_at) * 1000, 1
            ) if first_acknowledgement_at else None,
            "last_voice_to_substantive_audio_ms": round(
                (first_substantive_audio_at - last_voice_sent_at) * 1000, 1
            ) if first_substantive_audio_at else None,
            "acknowledgement_audio_received": first_acknowledgement_at is not None,
            "audio_bytes": audio_bytes,
            "final_audio_received": final_audio,
            "failure": failure,
        }

    last_event = "no server event"
    while asyncio.get_running_loop().time() < deadline:
        try:
            try:
                event = await receive_json(websocket, deadline)
            except Exception as error:
                raise LiveVoiceTurnFailure(
                    f"Turn {number} ended while waiting for events ({type(error).__name__})",
                    partial_turn(type(error).__name__),
                ) from error
        except ConnectionClosed as error:
            raise RuntimeError(
                f"Voice socket closed during turn {number}; last event: {last_event}"
            ) from error
        event_type = event.get("type")
        last_event = str(event_type)
        if event_type == "transcript":
            latest_transcript = str(event.get("text") or "")
            latest_transcript_status = {
                "is_final": event.get("is_final") is True,
                "speech_final": event.get("speech_final") is True,
                "language": event.get("language"),
                "confidence": event.get("confidence"),
            }
            if event.get("is_final"):
                transcript = latest_transcript
                final_transcript_at = time.perf_counter()
                record_timeline("final_transcript")
            else:
                record_timeline("interim_transcript")
        elif event_type == "agent_response":
            decision = event.get("decision")
            if isinstance(decision, dict):
                reply = str(decision.get("spoken_text") or "")
                reason = decision.get("reason")
                response_reason = reason if isinstance(reason, str) else None
            latency_value = event.get("latency_ms")
            decision_latency_ms = latency_value if isinstance(latency_value, (int, float)) else None
            record_timeline("agent_response")
        elif event_type == "audio_chunk":
            encoded = event.get("audio_base64")
            if isinstance(encoded, str) and encoded:
                chunk = base64.b64decode(encoded, validate=True)
                audio_bytes += len(chunk)
                if chunk and first_audio_at is None:
                    first_audio_at = time.perf_counter()
                    if event.get("acknowledgement") is True:
                        record_timeline("first_acknowledgement_audio")
                if chunk and event.get("acknowledgement") is True and first_acknowledgement_at is None:
                    first_acknowledgement_at = time.perf_counter()
                if chunk and event.get("acknowledgement") is not True and first_substantive_audio_at is None:
                    first_substantive_audio_at = time.perf_counter()
                    record_timeline("first_substantive_audio")
            final_audio = final_audio or event.get("is_final") is True
        elif event_type in {"agent_unavailable", "audio_unavailable", "stt_unavailable"}:
            reason = event.get("reason")
            detail = f" ({reason})" if isinstance(reason, str) and reason else ""
            message = f"Turn {number} failed at {event_type}{detail}"
            record_timeline(str(event_type))
            raise LiveVoiceTurnFailure(message, partial_turn(message))
        elif event_type == "state" and event.get("state") == "listening" and final_audio:
            now = time.perf_counter()
            return {
                "turn": number,
                "input_phrase": phrase,
                "transcript": transcript,
                "latest_transcript": latest_transcript,
                "latest_transcript_status": latest_transcript_status,
                "reply": reply,
                "agent_decision_latency_ms": decision_latency_ms,
                "response_reason": response_reason,
                "transcription_recovery": response_reason == "transcription_incomplete",
                "final_transcript_received": final_transcript_at is not None,
                "event_timeline_from_last_voice_frame": event_timeline,
                "last_voice_to_final_transcript_ms": round((final_transcript_at - last_voice_sent_at) * 1000, 1)
                if final_transcript_at else None,
                "last_voice_to_first_audio_ms": round((first_audio_at - last_voice_sent_at) * 1000, 1)
                if first_audio_at else None,
                "acknowledgement_audio_received": first_acknowledgement_at is not None,
                "last_voice_to_acknowledgement_audio_ms": round((first_acknowledgement_at - last_voice_sent_at) * 1000, 1)
                if first_acknowledgement_at else None,
                "last_voice_to_substantive_audio_ms": round((first_substantive_audio_at - last_voice_sent_at) * 1000, 1)
                if first_substantive_audio_at else None,
                "final_transcript_to_substantive_audio_ms": round((first_substantive_audio_at - final_transcript_at) * 1000, 1)
                if first_substantive_audio_at and final_transcript_at else None,
                "response_complete_ms": round((now - last_voice_sent_at) * 1000, 1),
                "audio_bytes": audio_bytes,
                "final_audio_received": final_audio,
                "input_audio_bytes": len(audio),
            }
    message = f"Turn {number} did not complete within the response deadline after {last_event}"
    raise LiveVoiceTurnFailure(message, partial_turn(message))


async def run(
    base_url: str,
    voice_mode: str = "openai",
    input_source: str = "macos-say",
) -> dict[str, Any]:
    audio_inputs = (
        synthesize_macos_inputs()
        if input_source == "macos-say"
        else await synthesize_openai_inputs()
    )
    parsed = urlparse(base_url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{parsed.netloc}/v1/voice"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/v1/voice/session",
            headers={"Origin": ORIGIN},
            json={"mode": voice_mode},
        )
        response.raise_for_status()
        ticket = response.json()["ticket"]
    turns: list[dict[str, Any]] = []
    async with connect(ws_url, additional_headers={"Origin": ORIGIN}, max_size=1_048_576) as websocket:
        await websocket.send(json.dumps({"type": "authenticate", "ticket": ticket, "language": "ur-Latn"}))
        await wait_for_state(websocket, "listening")
        await websocket.send(json.dumps({"type": "booking_contact", "contact": None}))
        await websocket.send(json.dumps({"type": "audio_start", "sample_rate": 16_000, "encoding": "linear16"}))
        deadline = asyncio.get_running_loop().time() + 20
        while True:
            event = await receive_json(websocket, deadline)
            if event.get("type") == "state" and event.get("state") == "listening" and event.get("audio_started"):
                break
            if event.get("type") in {"error", "stt_unavailable"}:
                raise RuntimeError(
                    f"Audio input setup failed: {event.get('type')} "
                    f"({event.get('reason') or 'no reason code'})"
                )
        for number, (phrase, audio) in enumerate(zip(PHRASES, audio_inputs, strict=True), start=1):
            try:
                turn = await run_turn(websocket, phrase, audio, number)
            except Exception as error:
                failed_turn = (
                    error.partial_turn if isinstance(error, LiveVoiceTurnFailure) else None
                )
                raise LiveVoiceSmokeError(
                    f"Live voice run stopped on turn {number}: {error}", turns, failed_turn
                ) from error
            turns.append(turn)
            print(
                json.dumps(
                    {
                        "turn": number,
                        "transcript": turn["transcript"],
                        "first_audio_ms": turn["last_voice_to_first_audio_ms"],
                        "substantive_audio_ms": turn["last_voice_to_substantive_audio_ms"],
                        "final_audio_received": turn["final_audio_received"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    result = {
        "status": "completed",
        "voice_mode": voice_mode,
        "method": f"Live local FastAPI/WebSocket with {input_source}-generated synthetic PCM speech paced at the browser AudioWorklet cadence (4096 samples at 48 kHz, mono 16 kHz input). Five silence frames model the 425 ms browser VAD threshold; {voice_mode} uses its configured finalization behavior.",
        "input_source": input_source,
        "capture_frame_ms": round(FRAME_SECONDS * 1000, 3),
        "silence_frames": SILENCE_FRAMES,
        "silence_ms": round(SILENCE_FRAMES * FRAME_SECONDS * 1000, 1),
        "target_ms": 2000,
        "turns": turns,
        "all_turns_returned_audio": all(turn["final_audio_received"] and turn["audio_bytes"] > 0 for turn in turns),
        "all_turns_answered": all(
            turn["final_transcript_received"] and not turn["transcription_recovery"]
            for turn in turns
        ),
        "transcription_recovery_count": sum(
            turn["transcription_recovery"] for turn in turns
        ),
        "all_first_audio_under_target": all(
            turn["last_voice_to_first_audio_ms"] is not None
            and turn["last_voice_to_first_audio_ms"] < 2000
            for turn in turns
        ),
        "all_substantive_answers_under_target": all(
            not turn["transcription_recovery"]
            and turn["last_voice_to_substantive_audio_ms"] is not None
            and turn["last_voice_to_substantive_audio_ms"] < 2000
            for turn in turns
        ),
        "limitations": [
            "Synthetic speech, not a physical microphone or human quality review",
            "Local WebSocket loopback excludes browser playback/audio-device audibility",
            "Three turns are diagnostic samples, not a statistically meaningful latency percentile",
        ],
    }
    acceptance_failures = voice_acceptance_failures(turns, target_ms=2_000)
    result["acceptance_status"] = "passed" if not acceptance_failures else "failed"
    result["acceptance_failures"] = acceptance_failures
    return result


def write_artifact(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temporary_path.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--voice-mode", choices=("openai", "hybrid"), default="openai")
    parser.add_argument(
        "--input-source",
        choices=("macos-say", "openai-realtime"),
        default="macos-say",
        help="Generate synthetic caller speech locally or spend OpenAI credits to synthesize it",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/evaluation/live-voice-latency-current.json",
    )
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args.api_url, args.voice_mode, args.input_source))
        exit_code = 0 if result["acceptance_status"] == "passed" else 1
    except Exception as error:  # noqa: BLE001 - persist failed live evidence before exiting
        turns = getattr(error, "turns", [])
        result = {
            "status": "failed",
            "voice_mode": args.voice_mode,
            "input_source": args.input_source,
            "failure": f"{type(error).__name__}: {error}"[:500],
            "turns": turns if isinstance(turns, list) else [],
            "completed_turn_count": len(turns) if isinstance(turns, list) else 0,
            "failed_turn": error.failed_turn if isinstance(error, LiveVoiceSmokeError) else None,
            "limitations": [
                "Failed smoke run; partial turns are diagnostic and do not count as a pass",
                "Synthetic speech, not a physical microphone or human quality review",
            ],
        }
        exit_code = 1
    write_artifact(args.output, result)
    if args.voice_mode == "hybrid":
        canonical = ROOT / "artifacts/evaluation/live-voice-latency-hybrid-current.json"
        if canonical.resolve() != args.output.resolve():
            write_artifact(canonical, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
