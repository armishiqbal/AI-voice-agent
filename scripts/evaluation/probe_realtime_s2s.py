"""Probe native Realtime speech-to-speech with a required trusted local-agent tool call."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.integrations.stt.openai_realtime import resample_pcm16_16k_to_24k
from app.integrations.tts.openai_realtime import (
    OpenAIRealtimeSpeechProvider,
    _is_spoken_exactly,
)

MODEL = "gpt-realtime-2.1-mini"
PHRASE = "Mujhe Karachi mein ghar chahiye, mera budget paanch crore hai."
ORIGIN = "http://localhost:5173"
FRAME_SAMPLES_16K = round(16_000 * 4096 / 48_000)
FRAME_SECONDS = 4096 / 48_000


async def synthesize_input() -> bytes:
    provider = OpenAIRealtimeSpeechProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_realtime_tts_model,
        voice=settings.openai_tts_voice,
    )
    audio = bytearray()
    try:
        async for chunk in provider.synthesize_stream(PHRASE, "ur-Latn"):
            audio.extend(chunk.audio)
    finally:
        await provider.aclose()
    if not audio:
        raise RuntimeError("No UrduLish source speech was generated")
    return bytes(audio)


async def wait_event(websocket: Any, deadline: float) -> dict[str, Any]:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise TimeoutError("Realtime speech-to-speech probe timed out")
    event = json.loads(await asyncio.wait_for(websocket.recv(), timeout=remaining))
    if not isinstance(event, dict):
        raise TypeError("Realtime returned a malformed event")
    if event.get("type") == "error":
        error = event.get("error")
        code = error.get("code") if isinstance(error, dict) else "unknown"
        raise RuntimeError(f"Realtime rejected the probe event ({code})")
    return event


async def send_audio(websocket: Any, audio24k: bytes) -> float:
    # The browser captures 4096 samples at 48 kHz, then sends 16 kHz PCM frames.
    audio16k = bytearray()
    for offset in range(0, len(audio24k), 48_000):
        # Resample in bounded 2-second windows, preserving the current session's rate contract.
        audio16k.extend(_resample_24k_window_to_16k(audio24k[offset:offset + 48_000]))
    samples = memoryview(bytes(audio16k)).cast("h")
    count = (len(samples) + FRAME_SAMPLES_16K - 1) // FRAME_SAMPLES_16K
    loop = asyncio.get_running_loop()
    started = loop.time()
    for index in range(count):
        left = index * FRAME_SAMPLES_16K
        frame = samples[left:min(left + FRAME_SAMPLES_16K, len(samples))].tobytes()
        audio24 = resample_pcm16_16k_to_24k(frame)
        await websocket.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(audio24).decode("ascii"),
        }))
        if index + 1 < count:
            await asyncio.sleep(max(0, started + (index + 1) * FRAME_SECONDS - loop.time()))
    last_voice_at = loop.time()
    for index in range(5):
        silence = bytes(FRAME_SAMPLES_16K * 2)
        await websocket.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(resample_pcm16_16k_to_24k(silence)).decode("ascii"),
        }))
        await asyncio.sleep(max(0, last_voice_at + (index + 1) * FRAME_SECONDS - loop.time()))
    await websocket.send(json.dumps({"type": "input_audio_buffer.commit"}))
    return last_voice_at


def _resample_24k_window_to_16k(audio: bytes) -> bytes:
    if len(audio) % 2:
        audio = audio[:-1]
    samples = [sample[0] for sample in __import__("struct").iter_unpack("<h", audio)]
    count = max(1, round(len(samples) * 2 / 3))
    import struct

    output: list[int] = []
    for index in range(count):
        source = index * 1.5
        left = min(int(source), len(samples) - 1)
        right = min(left + 1, len(samples) - 1)
        fraction = source - left
        output.append(round(samples[left] * (1 - fraction) + samples[right] * fraction))
    return struct.pack(f"<{len(output)}h", *output)


async def resolve_with_agent(base_url: str, transcript: str) -> dict[str, Any]:
    conversation_id = f"s2s-probe-{time.time_ns()}"
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/v1/conversations/{quote(conversation_id, safe='')}/turn",
            json={"text": transcript, "language": "ur-Latn"},
        )
        response.raise_for_status()
        return response.json()


async def run(base_url: str) -> dict[str, Any]:
    source_audio = await synthesize_input()
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI credentials are not configured in the local environment")
    parsed = urlparse("wss://api.openai.com/v1/realtime")
    ws_url = f"{parsed.geturl()}?model={MODEL}"
    started = time.perf_counter()
    async with connect(
        ws_url,
        additional_headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        open_timeout=15,
        close_timeout=5,
        max_size=1_048_576,
    ) as websocket:
        await websocket.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": ["audio"],
                "instructions": (
                    "You are the speech front end for a Pakistani UrduLish real-estate assistant. "
                    "For each caller turn, call resolve_real_estate_turn with the caller's words "
                    "transcribed faithfully. Do not answer from memory and do not speak before "
                    "the server tool returns. After the tool result, read its spoken_text exactly. "
                    "Do not add, omit, paraphrase, translate, or infer property facts."
                ),
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24_000},
                        "transcription": {
                            "model": "gpt-live-transcribe",
                            "language": "ur",
                            "prompt": "Pakistani Urdu and English code-switching; preserve real-estate terms such as Karachi, DHA, budget, crore, buy, and rent.",
                        },
                        "turn_detection": None,
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24_000},
                        "voice": "alloy",
                    },
                },
                "tools": [{
                    "type": "function",
                    "name": "resolve_real_estate_turn",
                    "description": "Transcribe this caller turn for the trusted real-estate agent. This function must be called before responding.",
                    "parameters": {
                        "type": "object",
                        "properties": {"transcript": {"type": "string"}},
                        "required": ["transcript"],
                        "additionalProperties": False,
                    },
                }],
                "tool_choice": "auto",
            },
        }))
        deadline = asyncio.get_running_loop().time() + 20
        while (await wait_event(websocket, deadline)).get("type") != "session.updated":
            pass

        last_voice_at = await send_audio(websocket, source_audio)
        await websocket.send(json.dumps({"type": "response.create", "response": {"tool_choice": "required", "output_modalities": ["text"]}}))

        transcript = ""
        tool_call: dict[str, Any] | None = None
        transcription_event: str | None = None
        initial_response_done = False
        deadline = asyncio.get_running_loop().time() + 30
        while not initial_response_done:
            event = await wait_event(websocket, deadline)
            kind = event.get("type")
            if kind == "conversation.item.input_audio_transcription.completed":
                transcription_event = str(event.get("transcript") or "")
            elif kind == "response.function_call_arguments.done":
                try:
                    arguments = json.loads(str(event.get("arguments") or "{}"))
                except json.JSONDecodeError:
                    arguments = {}
                if isinstance(arguments, dict):
                    transcript = str(arguments.get("transcript") or "").strip()
                tool_call = {
                    "call_id": event.get("call_id"),
                    "name": event.get("name"),
                    "arguments": arguments,
                }
            elif kind == "response.output_item.done":
                item = event.get("item")
                if isinstance(item, dict) and item.get("type") == "function_call":
                    try:
                        arguments = json.loads(str(item.get("arguments") or "{}"))
                    except json.JSONDecodeError:
                        arguments = {}
                    if isinstance(arguments, dict):
                        transcript = str(arguments.get("transcript") or "").strip()
                    tool_call = {
                        "call_id": item.get("call_id"),
                        "name": item.get("name"),
                        "arguments": arguments,
                    }
            elif kind == "response.done":
                initial_response_done = True
        if not tool_call or not tool_call.get("call_id") or not transcript:
            raise RuntimeError("Realtime did not request the trusted real-estate tool with a transcript")

        agent_start = time.perf_counter()
        result = await resolve_with_agent(base_url, transcript)
        decision = result.get("decision") or {}
        spoken_text = str(decision.get("spoken_text") or "")
        if not spoken_text:
            raise RuntimeError("The trusted agent returned no spoken response")
        agent_ms = (time.perf_counter() - agent_start) * 1000
        await websocket.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": tool_call["call_id"],
                "output": json.dumps({
                    "spoken_text": spoken_text,
                    "decision_kind": decision.get("kind"),
                    "property_ids": decision.get("property_ids", []),
                }, ensure_ascii=False),
            },
        }))
        answer_requested_at = time.perf_counter()
        await websocket.send(json.dumps({"type": "response.create", "response": {"tool_choice": "none", "output_modalities": ["audio"]}}))

        first_audio_at: float | None = None
        transcript_out = ""
        audio_bytes = 0
        deadline = asyncio.get_running_loop().time() + 30
        while True:
            event = await wait_event(websocket, deadline)
            kind = event.get("type")
            if kind == "response.output_audio_transcript.delta":
                transcript_out += str(event.get("delta") or "")
            elif kind == "response.output_audio_transcript.done":
                transcript_out = str(event.get("transcript") or transcript_out)
            elif kind == "response.output_audio.delta":
                encoded = event.get("delta")
                if isinstance(encoded, str) and encoded:
                    audio = base64.b64decode(encoded, validate=True)
                    audio_bytes += len(audio)
                    if audio and first_audio_at is None:
                        first_audio_at = time.perf_counter()
            elif kind == "response.done":
                break

    first_audio_ms = round((first_audio_at - last_voice_at) * 1000, 1) if first_audio_at else None
    return {
        "model": MODEL,
        "architecture": "Native Realtime speech-to-speech with required function call; function output comes from the local trusted FastAPI/LangGraph agent; no response audio is requested until that result is returned.",
        "user_phrase": PHRASE,
        "tool_transcript": transcript,
        "provider_transcription_event": transcription_event,
        "trusted_agent_reply": spoken_text,
        "spoken_transcript": transcript_out,
        "spoken_text_exact_match": _is_spoken_exactly(transcript_out, spoken_text),
        "tool_call": tool_call,
        "agent_decision_latency_ms": round(agent_ms, 1),
        "speech_end_to_first_audio_ms": first_audio_ms,
        "first_audio_after_tool_result_ms": round((first_audio_at - answer_requested_at) * 1000, 1) if first_audio_at else None,
        "audio_bytes": audio_bytes,
        "audio_completed": audio_bytes > 0,
        "provider_probe_elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "target_ms": 2000,
        "under_target": first_audio_ms is not None and first_audio_ms < 2000,
        "limitations": [
            "One synthetic UrduLish input phrase; not a physical microphone or native-speaker evaluation",
            "Tool output uses a real local agent turn and current empty live inventory; Calendar, email, booking and interruption are not exercised",
            "Audio transcript matching is evaluation evidence only; production streaming must gate unapproved speech before playback",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evaluation/probe-realtime-s2s.json")
    args = parser.parse_args()
    result = asyncio.run(run(args.api_url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
