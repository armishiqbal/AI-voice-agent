from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
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
    from_finalize: bool = False


class STTProvider(Protocol):
    async def is_ready(self) -> bool: ...

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[STTEvent]: ...


class STTProviderError(RuntimeError):
    """Expected speech provider failure that can be surfaced to the client."""

    def __init__(self, message: str, *, code: str = "provider_unavailable") -> None:
        super().__init__(message)
        self.code = code


def stt_provider_error_code(error: BaseException) -> str:
    """Map upstream failures to safe, stable UI codes without exposing provider payloads."""
    explicit_code = getattr(error, "code", None)
    safe_codes = {
        "provider_insufficient_credits",
        "provider_rate_limited",
        "provider_auth_rejected",
        "provider_timeout",
        "provider_unavailable",
    }
    if isinstance(explicit_code, str) and explicit_code in safe_codes:
        return explicit_code
    messages: list[str] = []
    current: BaseException | None = error
    while current is not None:
        messages.append(str(current).lower())
        current = current.__cause__ or current.__context__
    detail = " ".join(messages)
    if any(value in detail for value in ("insufficient_quota", "credit_balance_exhausted", "insufficient credits")):
        return "provider_insufficient_credits"
    if any(value in detail for value in ("rate limit", "rate_limit", "too many requests", "http 429")):
        return "provider_rate_limited"
    if any(value in detail for value in ("invalid_api_key", "unauthorized", "http 401", "authentication")):
        return "provider_auth_rejected"
    if isinstance(error, TimeoutError) or "timed out" in detail or "timeout" in detail:
        return "provider_timeout"
    return "provider_unavailable"


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
        from_finalize=bool(_value(message, "from_finalize", False)),
    )


class DeepgramStreamingSTT:
    """Deepgram Listen v1 adapter with provider-neutral events."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "nova-3",
        language: str = "multi",
        endpointing: int | bool = 300,
        utterance_end_ms: int = 1000,
        sample_rate: int = 16_000,
        keyterms: tuple[str, ...] = (),
        finalize_timeout_seconds: float = 6.0,
        on_transport_ready: Callable[[], None] | None = None,
    ) -> None:
        self.api_key = api_key or getenv("DEEPGRAM_API_KEY")
        self.model = model
        self.language = language
        self.endpointing = endpointing
        self.utterance_end_ms = utterance_end_ms
        self.sample_rate = sample_rate
        self.keyterms = keyterms
        self.finalize_timeout_seconds = finalize_timeout_seconds
        self.on_transport_ready = on_transport_ready

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
        provider_errors: asyncio.Queue[BaseException] = asyncio.Queue()
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
            **({"keyterm": list(self.keyterms)} if self.keyterms else {}),
        ) as connection:
            if self.on_transport_ready is not None:
                self.on_transport_ready()

            def on_message(message: object) -> None:
                event = parse_deepgram_message(message)
                if event is not None:
                    events.put_nowait(event)

            def on_error(error: object) -> None:
                if isinstance(error, BaseException):
                    provider_errors.put_nowait(error)
                else:
                    provider_errors.put_nowait(RuntimeError(type(error).__name__))

            connection.on(EventType.MESSAGE, on_message)
            connection.on(EventType.ERROR, on_error)
            listen_task = asyncio.create_task(connection.start_listening())
            sender_task = asyncio.create_task(self._send_audio(connection, audio))
            try:
                while True:
                    if not provider_errors.empty():
                        upstream_error = provider_errors.get_nowait()
                        raise STTProviderError(
                            "Deepgram streaming provider reported an error",
                            code=stt_provider_error_code(upstream_error),
                        ) from upstream_error
                    if not events.empty():
                        yield events.get_nowait()
                    elif listen_task.done():
                        if listen_task.cancelled():
                            raise STTProviderError("Deepgram result listener was cancelled")
                        listener_error = listen_task.exception()
                        if listener_error is not None:
                            raise STTProviderError("Deepgram result listener failed") from listener_error
                        if not sender_task.done():
                            raise STTProviderError(
                                "Deepgram result listener closed during audio input"
                            )
                        break
                    elif sender_task.done():
                        if sender_task.cancelled():
                            raise STTProviderError("Deepgram audio sender was cancelled")
                        sender_error = sender_task.exception()
                        if sender_error is not None:
                            raise STTProviderError("Deepgram audio sender failed") from sender_error
                        try:
                            await asyncio.wait_for(
                                asyncio.shield(listen_task),
                                timeout=self.finalize_timeout_seconds,
                            )
                        except TimeoutError as error:
                            raise STTProviderError(
                                "Deepgram final result drain timed out"
                            ) from error
                        if not events.empty():
                            continue
                        break
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
    async def _send_audio(
        connection: Any,
        audio: AsyncIterator[bytes],
        keep_alive_interval_seconds: float = 5.0,
    ) -> None:
        iterator = audio.__aiter__()
        next_chunk = asyncio.create_task(anext(iterator))
        try:
            while True:
                done, _ = await asyncio.wait(
                    {next_chunk}, timeout=keep_alive_interval_seconds
                )
                if not done:
                    # Deepgram closes a live connection after prolonged input
                    # silence. Keep the conversation stream available while the
                    # agent speaks or the caller pauses between turns.
                    await connection.send_keep_alive()
                    continue
                try:
                    chunk = next_chunk.result()
                except StopAsyncIteration:
                    break
                if chunk == b"":
                    # Flush this utterance without closing the conversation
                    # socket. Closing here races with the next browser turn and
                    # forces a new provider handshake for every utterance.
                    await connection.send_finalize()
                elif chunk:
                    await connection.send_media(chunk)
                next_chunk = asyncio.create_task(anext(iterator))
        finally:
            if not next_chunk.done():
                next_chunk.cancel()
            # Always retrieve the task result: iterator exhaustion and caller
            # cancellation can race, leaving StopAsyncIteration unobserved.
            await asyncio.gather(next_chunk, return_exceptions=True)
        # The input iterator ends only when the browser session ends or fails.
        await connection.send_close_stream()
