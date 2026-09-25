from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from os import getenv
from typing import Any, Protocol


@dataclass(frozen=True)
class STTEvent:
    text: str = ""
    language: str = "und"
    confidence: float | None = None
    is_final: bool = False
    speech_final: bool = False
    speech_started: bool = False


class STTProvider(Protocol):
    async def is_ready(self) -> bool: ...

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]: ...


class STTProviderError(RuntimeError):
    """Expected speech provider failure that can be surfaced to the client."""


class UnavailableSTTProvider:
    async def is_ready(self) -> bool:
        return False

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        del audio
        raise STTProviderError("Streaming STT is not configured")
        yield  # pragma: no cover - keeps this function an async generator


def _value(message: object, key: str, default: Any = None) -> Any:
    if isinstance(message, dict):
        return message.get(key, default)
    return getattr(message, key, default)


def parse_deepgram_message(message: object) -> STTEvent | None:
    """Convert SDK result objects or test dictionaries into our stable event."""

    message_type = _value(message, "type", "")
    if message_type == "SpeechStarted":
        return STTEvent(speech_started=True)
    if message_type != "Results":
        return None
    channel = _value(message, "channel", {})
    alternatives = _value(channel, "alternatives", []) or []
    if not alternatives:
        return None
    alternative = alternatives[0]
    text = str(_value(alternative, "transcript", "") or "").strip()
    words = _value(alternative, "words", []) or []
    language = _value(alternative, "language")
    if not language and words:
        language = _value(words[0], "language")
    return STTEvent(
        text=text,
        language=str(language or "und"),
        confidence=float(_value(alternative, "confidence", 0.0) or 0.0),
        is_final=bool(_value(message, "is_final", False)),
        speech_final=bool(_value(message, "speech_final", False)),
    )


class DeepgramStreamingSTT:
    """Deepgram Listen v1 adapter with provider-neutral events."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "nova-3",
        language: str = "multi",
        endpointing: int = 300,
        utterance_end_ms: int = 1000,
        sample_rate: int = 16_000,
    ) -> None:
        self.api_key = api_key or getenv("DEEPGRAM_API_KEY")
        self.model = model
        self.language = language
        self.endpointing = endpointing
        self.utterance_end_ms = utterance_end_ms
        self.sample_rate = sample_rate

    async def is_ready(self) -> bool:
        if not self.api_key:
            return False
        try:
            import deepgram  # noqa: F401
        except ImportError:
            return False
        return True

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]:
        if not self.api_key:
            raise STTProviderError("DEEPGRAM_API_KEY is not configured")
        try:
            from deepgram import AsyncDeepgramClient
            from deepgram.core.events import EventType
        except ImportError as error:
            raise STTProviderError(
                "Install the voice-deepgram extra to enable streaming STT"
            ) from error

        events: asyncio.Queue[STTEvent] = asyncio.Queue()
        client = AsyncDeepgramClient(api_key=self.api_key)
        async with client.listen.v1.connect(
            model=self.model,
            language=self.language,
            encoding="linear16",
            channels=1,
            sample_rate=self.sample_rate,
            interim_results=True,
            utterance_end_ms=str(self.utterance_end_ms),
            vad_events=True,
            endpointing=self.endpointing,
            smart_format=True,
        ) as connection:

            def on_message(message: object) -> None:
                event = parse_deepgram_message(message)
                if event is not None:
                    events.put_nowait(event)

            connection.on(EventType.MESSAGE, on_message)
            listen_task = asyncio.create_task(connection.start_listening())
            sender_task = asyncio.create_task(self._send_audio(connection, audio))
            sender_finished_at: float | None = None
            try:
                while True:
                    if not events.empty():
                        yield events.get_nowait()
                    elif sender_task.done():
                        if sender_finished_at is None:
                            sender_finished_at = asyncio.get_running_loop().time()
                        elif asyncio.get_running_loop().time() - sender_finished_at >= 1.0:
                            break
                        await asyncio.sleep(0.01)
                    else:
                        await asyncio.sleep(0.01)
                while not events.empty():
                    yield events.get_nowait()
            finally:
                if not sender_task.done():
                    sender_task.cancel()
                if not listen_task.done():
                    listen_task.cancel()
                await asyncio.gather(sender_task, listen_task, return_exceptions=True)

    @staticmethod
    async def _send_audio(connection: Any, audio: AsyncIterator[bytes]) -> None:
        async for chunk in audio:
            if chunk:
                await connection.send_media(chunk)
        await connection.send_finalize()
