from __future__ import annotations

import asyncio
import base64
import json
import re
import unicodedata
from collections.abc import AsyncIterator
from contextlib import suppress
from os import getenv
from typing import Any

from app.integrations.tts.router import AudioChunk, TTSProviderError


class OpenAIRealtimeSpeechProvider:
    """Session-scoped, low-latency speech output with verbatim transcript checks."""

    name = "openai-realtime-speech"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-realtime-1.5",
        voice: str = "alloy",
        connect_timeout_seconds: float = 10.0,
        response_timeout_seconds: float = 20.0,
        first_audio_timeout_seconds: float = 1.8,
    ) -> None:
        self.api_key = api_key or getenv("OPENAI_API_KEY")
        self.model = model
        self.voice = voice
        self.connect_timeout_seconds = connect_timeout_seconds
        self.response_timeout_seconds = response_timeout_seconds
        self.first_audio_timeout_seconds = first_audio_timeout_seconds
        self._connection: Any | None = None
        self._connect_lock = asyncio.Lock()
        self._synthesis_lock = asyncio.Lock()

    async def is_ready(self) -> bool:
        if not self.api_key:
            return False
        try:
            from websockets.asyncio.client import connect  # noqa: F401
        except ImportError:
            return False
        return True

    async def warmup(self) -> bool:
        """Open one Realtime session per caller so its first reply avoids setup latency."""
        if not self.api_key:
            return False
        async with self._connect_lock:
            if self._connection is not None:
                return True
            try:
                from websockets.asyncio.client import connect

                connection = await connect(
                    f"wss://api.openai.com/v1/realtime?model={self.model}",
                    additional_headers={"Authorization": f"Bearer {self.api_key}"},
                    open_timeout=self.connect_timeout_seconds,
                    close_timeout=2,
                    max_size=1_048_576,
                )
                await connection.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {
                                "type": "realtime",
                                "output_modalities": ["audio"],
                                "audio": {
                                    "output": {
                                        "format": {"type": "audio/pcm", "rate": 24_000},
                                        "voice": self.voice,
                                    }
                                },
                                "instructions": (
                                    "You are a speech synthesizer, not a conversational assistant. "
                                    "Read each user message aloud exactly as written, preserving every "
                                    "word in the same order. Do not interpret it, answer it, translate "
                                    "it, add a greeting, omit words, or add commentary. Use natural "
                                    "Pakistani UrduLish pronunciation for Roman Urdu and English. "
                                    "The complete spoken transcript for each response must exactly "
                                    "match the corresponding user message."
                                ),
                            },
                        }
                    )
                )
                deadline = asyncio.get_running_loop().time() + self.connect_timeout_seconds
                while asyncio.get_running_loop().time() < deadline:
                    event = await asyncio.wait_for(
                        connection.recv(), timeout=self.connect_timeout_seconds
                    )
                    message = self._decode_event(event)
                    if message.get("type") == "error":
                        raise TTSProviderError("OpenAI Realtime speech session was rejected")
                    if message.get("type") == "session.updated":
                        self._connection = connection
                        return True
                raise TTSProviderError("OpenAI Realtime speech session timed out")
            except TTSProviderError:
                raise
            except Exception as error:
                raise TTSProviderError("OpenAI Realtime speech service is unavailable") from error

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        expected = text.strip()
        if not expected:
            return
        if not self.api_key:
            raise TTSProviderError("OPENAI_API_KEY is not configured")

        async with self._synthesis_lock:
            if voice_id and voice_id != self.voice:
                raise TTSProviderError("OpenAI Realtime voice cannot change during a call")
            await self.warmup()
            connection = self._connection
            if connection is None:
                raise TTSProviderError("OpenAI Realtime speech session is unavailable")

            transcript = ""
            sequence = 0
            pending_audio: list[bytes] = []
            pending_bytes = 0
            completed = False
            await connection.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": expected}],
                        },
                    }
                )
            )
            await connection.send(
                json.dumps({"type": "response.create", "response": {"output_modalities": ["audio"]}})
            )

            async def emit_audio(data: bytes) -> AudioChunk:
                nonlocal sequence
                chunk = AudioChunk(
                    sequence=sequence,
                    audio=data,
                    language=language,
                    sample_rate=24_000,
                    encoding="pcm_s16le",
                )
                sequence += 1
                return chunk

            try:
                loop = asyncio.get_running_loop()
                response_deadline = loop.time() + self.response_timeout_seconds
                first_audio_deadline = min(
                    response_deadline,
                    loop.time() + self.first_audio_timeout_seconds,
                )
                while loop.time() < response_deadline:
                    next_deadline = response_deadline if sequence else first_audio_deadline
                    try:
                        event = await asyncio.wait_for(
                            connection.recv(),
                            timeout=max(0.01, next_deadline - loop.time()),
                        )
                    except TimeoutError as error:
                        if not sequence and loop.time() >= first_audio_deadline:
                            raise TTSProviderError(
                                "OpenAI Realtime did not produce first audio before its deadline"
                            ) from error
                        raise TTSProviderError("OpenAI Realtime speech generation timed out") from error
                    message = self._decode_event(event)
                    event_type = message.get("type")
                    if event_type == "error":
                        raise TTSProviderError("OpenAI Realtime speech generation failed")
                    if event_type == "response.output_audio_transcript.delta":
                        transcript += str(message.get("delta") or "")
                        if not transcript or not _is_spoken_prefix(transcript, expected):
                            raise TTSProviderError("OpenAI Realtime speech did not follow the approved text")
                        while pending_audio:
                            data = pending_audio.pop(0)
                            pending_bytes -= len(data)
                            yield await emit_audio(data)
                    elif event_type == "response.output_audio_transcript.done":
                        transcript = str(message.get("transcript") or transcript)
                        if not _is_spoken_exactly(transcript, expected):
                            raise TTSProviderError("OpenAI Realtime speech did not match the approved text")
                        while pending_audio:
                            data = pending_audio.pop(0)
                            pending_bytes -= len(data)
                            yield await emit_audio(data)
                    elif event_type == "response.output_audio.delta":
                        encoded = message.get("delta")
                        if not isinstance(encoded, str) or not encoded:
                            continue
                        try:
                            data = base64.b64decode(encoded, validate=True)
                        except (ValueError, TypeError) as error:
                            raise TTSProviderError("OpenAI Realtime returned malformed audio") from error
                        if not data or len(data) % 2:
                            raise TTSProviderError("OpenAI Realtime returned invalid PCM audio")
                        if not _is_spoken_prefix(transcript, expected):
                            pending_bytes += len(data)
                            if pending_bytes > 1_000_000:
                                raise TTSProviderError("OpenAI Realtime speech exceeded the validation buffer")
                            pending_audio.append(data)
                            continue
                        yield await emit_audio(data)
                    elif event_type == "response.done":
                        response = message.get("response") or {}
                        if response.get("status") != "completed":
                            raise TTSProviderError("OpenAI Realtime speech response did not complete")
                        if not _is_spoken_exactly(transcript, expected):
                            raise TTSProviderError("OpenAI Realtime speech did not match the approved text")
                        if not sequence:
                            raise TTSProviderError("OpenAI Realtime returned no audio")
                        completed = True
                        yield AudioChunk(
                            sequence=sequence,
                            audio=b"",
                            language=language,
                            sample_rate=24_000,
                            encoding="pcm_s16le",
                            is_final=True,
                        )
                        return
                raise TTSProviderError("OpenAI Realtime speech generation timed out")
            except asyncio.CancelledError:
                await self._cancel_response(connection)
                raise
            except TTSProviderError:
                await self._cancel_response(connection)
                raise
            except Exception as error:
                await self._close_connection(connection)
                raise TTSProviderError("OpenAI Realtime speech service is unavailable") from error
            finally:
                if not completed and self._connection is connection:
                    await self._close_connection(connection)

    async def aclose(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            with suppress(Exception):
                await connection.close()

    async def _close_connection(self, connection: Any) -> None:
        if self._connection is connection:
            self._connection = None
        with suppress(Exception):
            await connection.close()

    async def _cancel_response(self, connection: Any) -> None:
        try:
            await connection.send(json.dumps({"type": "response.cancel"}))
        except Exception:  # noqa: BLE001 - cancellation may race a disconnect
            await self._close_connection(connection)

    @staticmethod
    def _decode_event(event: str | bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(event)
        except (json.JSONDecodeError, TypeError) as error:
            raise TTSProviderError("OpenAI Realtime returned a malformed event") from error
        if not isinstance(decoded, dict):
            raise TTSProviderError("OpenAI Realtime returned a malformed event")
        return decoded


def _spoken_words(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def _is_spoken_prefix(actual: str, expected: str) -> bool:
    actual_words = _spoken_words(actual)
    expected_words = _spoken_words(expected)
    if len(actual_words) > len(expected_words):
        return False
    for index, word in enumerate(actual_words):
        if index < len(actual_words) - 1 and word != expected_words[index]:
            return False
        if index == len(actual_words) - 1 and not expected_words[index].startswith(word):
            return False
    return True


def _is_spoken_exactly(actual: str, expected: str) -> bool:
    return _spoken_words(actual) == _spoken_words(expected)
