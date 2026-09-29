from __future__ import annotations

import asyncio
import base64
import json
import struct
from collections.abc import AsyncIterator
from dataclasses import replace
from os import getenv
from typing import Any

from app.integrations.stt.deepgram import (
    STTEvent,
    STTProviderError,
    stt_provider_error_code,
)


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
    if event_type == "input_audio_buffer.speech_started":
        return STTEvent(speech_started=True)
    if event_type == "conversation.item.input_audio_transcription.delta":
        text = str(message.get("delta") or "")
        return STTEvent(text=text, is_final=False) if text else None
    if event_type == "conversation.item.input_audio_transcription.completed":
        text = str(message.get("transcript") or "").strip()
        return STTEvent(text=text, is_final=True, speech_final=True) if text else None
    return None


class OpenAIRealtimeSTT:
    """Server-side Realtime transcription adapter; it never sends caller text to an LLM here."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-live-transcribe",
        realtime_model: str = "gpt-realtime-1.5",
        finalization_timeout_seconds: float = 8.0,
        language: str | None = None,
        transcription_prompt: str | None = None,
    ) -> None:
        self.api_key = api_key or getenv("OPENAI_API_KEY")
        self.model = model
        self.realtime_model = realtime_model
        self.finalization_timeout_seconds = finalization_timeout_seconds
        self.language = language
        self.transcription_prompt = transcription_prompt
        self._connection: Any | None = None
        self._connection_lock = asyncio.Lock()

    def configure_response_language(self, response_language: str) -> bool:
        """Apply the UI language to this session's next Realtime STT stream."""
        language = response_language.split("-", 1)[0]
        prompt = (
            "Transcribe Pakistani Urdu-English speech exactly. Preserve code-switching. "
            "Write Urdu words in Latin script (Roman Urdu) and English words in English. "
            "Real-estate terms: ghar, makan, Karachi, DHA, budget, crore, lakh, kiraya, "
            "khareed. Do not translate or add words."
            if response_language in {"ur-Latn", "ur-Arab"}
            else None
        )
        changed = language != self.language or prompt != self.transcription_prompt
        self.language = language
        self.transcription_prompt = prompt
        return changed

    async def is_ready(self) -> bool:
        if not self.api_key:
            return False
        try:
            import websockets  # noqa: F401
        except ImportError:
            return False
        return True

    async def warmup(self) -> bool:
        """Open and configure the caller's Realtime STT connection before mic capture."""
        if not self.api_key:
            return False
        async with self._connection_lock:
            if self._connection is not None:
                return True
            try:
                from websockets.asyncio.client import connect

                connection = await connect(
                    f"wss://api.openai.com/v1/realtime?model={self.realtime_model}",
                    additional_headers={"Authorization": f"Bearer {self.api_key}"},
                    open_timeout=10,
                    close_timeout=3,
                    max_size=1_048_576,
                )
                await connection.send(json.dumps({"type": "session.update", "session": self._session()}))
                if not await self._wait_for_session(connection):
                    await connection.close()
                    return False
                self._connection = connection
                return True
            except STTProviderError:
                raise
            except Exception as error:
                raise STTProviderError(
                    "OpenAI Realtime transcription is unavailable",
                    code=stt_provider_error_code(error),
                ) from error

    async def aclose(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            await connection.close()

    def _session(self) -> dict[str, object]:
        return {
            "type": "realtime",
            "output_modalities": ["text"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": 24_000},
                    "transcription": {
                        "model": self.model,
                        "delay": "low",
                        **({"language": self.language} if self.language else {}),
                        **({"prompt": self.transcription_prompt} if self.transcription_prompt else {}),
                    },
                    # Browser VAD already owns the turn boundary. Manual
                    # commits avoid waiting for a second server-side VAD pass.
                    "turn_detection": None,
                },
            },
        }

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        if not self.api_key:
            raise STTProviderError("OPENAI_API_KEY is not configured")
        try:
            if not await self.warmup():
                raise STTProviderError("OpenAI Realtime rejected the transcription session")
            connection = self._connection
            if connection is None:
                raise STTProviderError("OpenAI Realtime transcription is unavailable")

            commit_sent = asyncio.Event()

            async def send_audio() -> None:
                async for frame in audio:
                    # An empty frame forces a commit for explicit end-of-audio.
                    # The browser VAD's end marker is ignored; server VAD already
                    # detects the silence in the PCM stream.
                    if frame == b"":
                        await connection.send(json.dumps({"type": "input_audio_buffer.commit"}))
                        commit_sent.set()
                    elif frame in {b"\x00", b"\x02"}:
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

            partials: dict[str, str] = {}
            sender = asyncio.create_task(send_audio())
            receiver = asyncio.create_task(connection.recv())
            final_received = False
            final_deadline: float | None = None
            try:
                while True:
                    if sender.done():
                        error = sender.exception()
                        if error:
                            raise error
                        if final_received:
                            return
                        timeout_seconds = 1.0
                        if commit_sent.is_set():
                            loop = asyncio.get_running_loop()
                            if final_deadline is None:
                                final_deadline = loop.time() + self.finalization_timeout_seconds
                            timeout_seconds = final_deadline - loop.time()
                            if timeout_seconds <= 0:
                                raise STTProviderError(
                                    "OpenAI Realtime transcription did not finish before its deadline"
                                )
                        try:
                            raw = await asyncio.wait_for(receiver, timeout=timeout_seconds)
                        except TimeoutError:
                            if commit_sent.is_set():
                                raise STTProviderError(
                                    "OpenAI Realtime transcription did not finish before its deadline"
                                )
                            return
                    else:
                        done, _ = await asyncio.wait(
                            {sender, receiver},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if receiver in done:
                            raw = receiver.result()
                        else:
                            error = sender.exception()
                            if error:
                                raise error
                            continue
                    receiver = asyncio.create_task(connection.recv())
                    try:
                        message: Any = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    event = parse_openai_transcription_event(message)
                    if event is not None:
                        item_id = str(message.get("item_id") or "current")
                        if event.is_final:
                            partials.pop(item_id, None)
                        else:
                            if len(partials) >= 32 and item_id not in partials:
                                partials.pop(next(iter(partials)))
                            partials[item_id] = (partials.get(item_id, "") + event.text)[-4000:]
                            event = replace(event, text=partials[item_id])
                        if event.is_final:
                            final_received = True
                        yield event
                    elif isinstance(message, dict) and message.get("type") == "error":
                        error = message.get("error")
                        code = error.get("code") if isinstance(error, dict) else None
                        if code != "input_audio_buffer_commit_empty":
                            raise STTProviderError("OpenAI Realtime transcription failed")
            finally:
                for task in (sender, receiver):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(sender, receiver, return_exceptions=True)
        except STTProviderError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self.aclose()
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
                raise STTProviderError(
                    "OpenAI Realtime rejected the transcription session",
                    code=stt_provider_error_code(RuntimeError(json.dumps(message))),
                )
        return False
