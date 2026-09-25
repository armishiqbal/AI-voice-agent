from __future__ import annotations

import asyncio
import base64
import json
import struct
from collections.abc import AsyncIterator
from os import getenv
from typing import Any

from app.integrations.stt.deepgram import STTEvent, STTProviderError


def resample_pcm16_16k_to_24k(audio: bytes) -> bytes:
    """Linearly resample mono PCM16LE from the browser's 16 kHz contract to 24 kHz."""
    if len(audio) % 2:
        raise STTProviderError("OpenAI Realtime requires complete PCM16 samples")
    if not audio:
        return b""
    samples = struct.unpack(f"<{len(audio) // 2}h", audio)
    output_count = max(1, round(len(samples) * 1.5))
    output: list[int] = []
    for index in range(output_count):
        source = index * 2 / 3
        left = min(int(source), len(samples) - 1)
        right = min(left + 1, len(samples) - 1)
        fraction = source - left
        sample = round(samples[left] * (1 - fraction) + samples[right] * fraction)
        output.append(max(-32768, min(32767, sample)))
    return struct.pack(f"<{len(output)}h", *output)


def parse_openai_transcription_event(message: object) -> STTEvent | None:
    if not isinstance(message, dict):
        return None
    event_type = message.get("type")
    if event_type == "conversation.item.input_audio_transcription.delta":
        text = str(message.get("delta") or "")
        return STTEvent(text=text, is_final=False) if text else None
    if event_type == "conversation.item.input_audio_transcription.completed":
        text = str(message.get("transcript") or "").strip()
        return STTEvent(text=text, is_final=True, speech_final=True) if text else None
    return None


class OpenAIRealtimeSTT:
    """Server-side Realtime transcription adapter; it never sends caller text to an LLM here."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-live-transcribe") -> None:
        self.api_key = api_key or getenv("OPENAI_API_KEY")
        self.model = model

    async def is_ready(self) -> bool:
        if not self.api_key:
            return False
        try:
            import websockets  # noqa: F401
        except ImportError:
            return False
        return True

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        if not self.api_key:
            raise STTProviderError("OPENAI_API_KEY is not configured")
        try:
            from websockets.asyncio.client import connect
        except ImportError as error:
            raise STTProviderError(
                "Install the voice-openai extra for Realtime transcription"
            ) from error

        url = "wss://api.openai.com/v1/realtime?intent=transcription"
        try:
            async with connect(
                url,
                additional_headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                open_timeout=10,
                close_timeout=3,
                max_size=1_048_576,
            ) as connection:
                await connection.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {
                                "type": "transcription",
                                "audio": {
                                    "input": {
                                        "format": {"type": "audio/pcm", "rate": 24_000},
                                        "transcription": {
                                            "model": self.model,
                                            "delay": "low",
                                        },
                                        "turn_detection": None,
                                    }
                                },
                            },
                        }
                    )
                )
                ready = await self._wait_for_session(connection)
                if not ready:
                    raise STTProviderError("OpenAI Realtime rejected the transcription session")

                async def send_audio() -> None:
                    async for frame in audio:
                        # The browser emits zero-length frame as an end-of-turn marker and
                        # one-byte 0x00 as a speech-start marker. Real frames are even-sized.
                        if frame == b"":
                            await connection.send(json.dumps({"type": "input_audio_buffer.commit"}))
                        elif frame == b"\x00":
                            continue
                        else:
                            pcm = resample_pcm16_16k_to_24k(frame)
                            await connection.send(
                                json.dumps(
                                    {
                                        "type": "input_audio_buffer.append",
                                        "audio": base64.b64encode(pcm).decode("ascii"),
                                    }
                                )
                            )

                sender = asyncio.create_task(send_audio())
                try:
                    while True:
                        if sender.done():
                            error = sender.exception()
                            if error:
                                raise error
                            # Drain pending transcription events briefly after audio_end.
                            try:
                                raw = await asyncio.wait_for(connection.recv(), timeout=1.0)
                            except TimeoutError:
                                return
                        else:
                            raw = await connection.recv()
                        try:
                            message: Any = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        event = parse_openai_transcription_event(message)
                        if event is not None:
                            yield event
                        elif isinstance(message, dict) and message.get("type") == "error":
                            error = message.get("error")
                            code = error.get("code") if isinstance(error, dict) else None
                            if code != "input_audio_buffer_commit_empty":
                                raise STTProviderError("OpenAI Realtime transcription failed")
                finally:
                    if not sender.done():
                        sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)
        except STTProviderError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise STTProviderError("OpenAI Realtime transcription is unavailable") from error

    async def _wait_for_session(self, connection: Any) -> bool:
        for _ in range(4):
            try:
                raw = await asyncio.wait_for(connection.recv(), timeout=10)
            except TimeoutError:
                return False
            try:
                message = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(message, dict) and message.get("type") == "session.updated":
                return True
            if isinstance(message, dict) and message.get("type") == "error":
                return False
        return False
