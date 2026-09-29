import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.integrations.stt import (
    STTEvent,
    estimated_transcript_lag_ms,
    parse_deepgram_message,
    parse_openai_transcription_event,
    resample_pcm16_16k_to_24k,
    stt_provider_error_code,
)


def test_parse_deepgram_final_result() -> None:
    event = parse_deepgram_message(
        {
            "type": "Results",
            "start": 0.25,
            "duration": 1.4,
            "is_final": True,
            "speech_final": True,
            "channel": {
                "alternatives": [
                    {
                        "transcript": "Mujhe Karachi mein ghar chahiye",
                        "confidence": 0.91,
                        "words": [{"language": "ur"}],
                    }
                ]
            },
        }
    )
    assert event == STTEvent(
        text="Mujhe Karachi mein ghar chahiye",
        language="ur",
        confidence=0.91,
        audio_start_seconds=0.25,
        audio_duration_seconds=1.4,
        is_final=True,
        speech_final=True,
    )


def test_parse_deepgram_audio_cursor_metadata_is_nullable_and_finite() -> None:
    event = parse_deepgram_message(
        {
            "type": "Results",
            "start": "0.5",
            "duration": float("nan"),
            "channel": {"alternatives": [{"transcript": "Karachi"}]},
        }
    )
    assert event is not None
    assert event.audio_start_seconds == 0.5
    assert event.audio_duration_seconds is None


def test_estimated_transcript_lag_uses_processed_audio_cursor_and_skips_invalid_offsets() -> None:
    event = STTEvent(audio_start_seconds=0.5, audio_duration_seconds=1.25)
    assert estimated_transcript_lag_ms(2.0, event) == 250.0
    assert estimated_transcript_lag_ms(1.0, event) is None
    assert estimated_transcript_lag_ms(2.0, STTEvent()) is None


def test_parse_deepgram_explicit_finalize_without_endpointing() -> None:
    event = parse_deepgram_message(
        {
            "type": "Results",
            "is_final": True,
            "speech_final": False,
            "from_finalize": True,
            "channel": {"alternatives": [{"transcript": "DHA mein ghar chahiye"}]},
        }
    )
    assert event == STTEvent(
        text="DHA mein ghar chahiye",
        confidence=0.0,
        is_final=True,
        from_finalize=True,
    )


def test_parse_speech_started_and_ignores_metadata() -> None:
    assert parse_deepgram_message({"type": "SpeechStarted"}) == STTEvent(speech_started=True)
    assert parse_deepgram_message({"type": "Metadata"}) is None


def test_stt_provider_failures_map_to_safe_actionable_codes() -> None:
    assert stt_provider_error_code(
        RuntimeError("received 1013 insufficient_quota.credit_balance_exhausted")
    ) == "provider_insufficient_credits"
    assert stt_provider_error_code(RuntimeError("HTTP 401 unauthorized")) == "provider_auth_rejected"
    assert stt_provider_error_code(TimeoutError("provider handshake timed out")) == "provider_timeout"
    from app.integrations.stt.deepgram import STTProviderError
    assert stt_provider_error_code(
        STTProviderError("safe provider error", code="provider_auth_rejected")
    ) == "provider_auth_rejected"


@pytest.mark.asyncio
async def test_deepgram_turn_boundary_finalizes_without_closing_provider_stream() -> None:
    from app.integrations.stt.deepgram import DeepgramStreamingSTT

    class Connection:
        def __init__(self) -> None:
            self.events: list[tuple[str, bytes | None]] = []

        async def send_media(self, audio: bytes) -> None:
            self.events.append(("media", audio))

        async def send_finalize(self) -> None:
            self.events.append(("finalize", None))

        async def send_close_stream(self) -> None:
            self.events.append(("close", None))

    async def turns():
        yield b"turn one"
        yield b""
        # A browser turn boundary flushes its utterance and keeps the stream.
        yield b"turn two"
        yield b""

    connection = Connection()
    await DeepgramStreamingSTT._send_audio(connection, turns())

    assert connection.events == [
        ("media", b"turn one"),
        ("finalize", None),
        ("media", b"turn two"),
        ("finalize", None),
        ("close", None),
    ]


@pytest.mark.asyncio
async def test_deepgram_sends_keepalive_while_waiting_for_next_turn() -> None:
    from app.integrations.stt.deepgram import DeepgramStreamingSTT

    keepalive_sent = asyncio.Event()

    class Connection:
        async def send_keep_alive(self) -> None:
            keepalive_sent.set()

        async def send_media(self, audio: bytes) -> None:
            assert audio == b"speech"

        async def send_close_stream(self) -> None:
            return None

    async def idle_then_speech():
        await keepalive_sent.wait()
        yield b"speech"

    await DeepgramStreamingSTT._send_audio(
        Connection(), idle_then_speech(), keep_alive_interval_seconds=0.001
    )

    assert keepalive_sent.is_set()


@pytest.mark.asyncio
async def test_deepgram_stream_drains_final_result_after_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.stt.deepgram import DeepgramStreamingSTT

    class Connection:
        def __init__(self) -> None:
            self.listener_done = asyncio.Event()
            self.callbacks: dict[str, object] = {}

        def on(self, event_type: object, callback: object) -> None:
            assert transport_ready.is_set()
            self.callbacks[str(event_type)] = callback

        async def start_listening(self) -> None:
            await self.listener_done.wait()

        async def send_media(self, audio: bytes) -> None:
            assert audio == b"speech"

        async def send_finalize(self) -> None:
            callback = self.callbacks["message"]
            assert callable(callback)
            callback(
                {
                    "type": "Results",
                    "is_final": True,
                    "channel": {"alternatives": [{"transcript": "DHA mein ghar chahiye"}]},
                }
            )

        async def send_close_stream(self) -> None:
            self.listener_done.set()

    connection = Connection()
    transport_ready = asyncio.Event()

    def mark_transport_ready() -> None:
        transport_ready.set()

    class ConnectContext:
        async def __aenter__(self) -> Connection:
            mark_transport_ready()
            return connection

        async def __aexit__(self, *args: object) -> None:
            return None

    class Client:
        def __init__(self, *, api_key: str) -> None:
            del api_key
            self.listen = SimpleNamespace(
                v1=SimpleNamespace(connect=lambda **kwargs: ConnectContext())
            )

    deepgram_module = ModuleType("deepgram")
    deepgram_module.AsyncDeepgramClient = Client  # type: ignore[attr-defined]
    core_module = ModuleType("deepgram.core")
    events_module = ModuleType("deepgram.core.events")
    events_module.EventType = SimpleNamespace(MESSAGE="message", ERROR="error")  # type: ignore[attr-defined]
    deepgram_module.core = core_module  # type: ignore[attr-defined]
    core_module.events = events_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", deepgram_module)
    monkeypatch.setitem(sys.modules, "deepgram.core", core_module)
    monkeypatch.setitem(sys.modules, "deepgram.core.events", events_module)

    async def one_turn():
        yield b"speech"
        yield b""

    provider = DeepgramStreamingSTT(
        api_key="test-key",
        finalize_timeout_seconds=0.2,
        on_transport_ready=mark_transport_ready,
    )
    events = [event async for event in provider.stream(one_turn())]

    assert events == [STTEvent(text="DHA mein ghar chahiye", confidence=0.0, is_final=True)]
    assert transport_ready.is_set()


@pytest.mark.asyncio
async def test_deepgram_error_events_surface_safe_codes_without_provider_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.stt.deepgram import DeepgramStreamingSTT, STTProviderError

    class Connection:
        def __init__(self) -> None:
            self.callbacks: dict[str, object] = {}

        def on(self, event_type: object, callback: object) -> None:
            self.callbacks[str(event_type)] = callback

        async def start_listening(self) -> None:
            await asyncio.Event().wait()

        async def send_media(self, audio: bytes) -> None:
            del audio
            callback = self.callbacks["error"]
            assert callable(callback)
            callback(RuntimeError("HTTP 401 unauthorized private-test-secret"))

        async def send_close_stream(self) -> None:
            return None

    connection = Connection()

    class ConnectContext:
        async def __aenter__(self) -> Connection:
            return connection

        async def __aexit__(self, *args: object) -> None:
            return None

    class Client:
        def __init__(self, *, api_key: str) -> None:
            del api_key
            self.listen = SimpleNamespace(
                v1=SimpleNamespace(connect=lambda **kwargs: ConnectContext())
            )

    deepgram_module = ModuleType("deepgram")
    deepgram_module.AsyncDeepgramClient = Client  # type: ignore[attr-defined]
    core_module = ModuleType("deepgram.core")
    events_module = ModuleType("deepgram.core.events")
    events_module.EventType = SimpleNamespace(MESSAGE="message", ERROR="error")  # type: ignore[attr-defined]
    deepgram_module.core = core_module  # type: ignore[attr-defined]
    core_module.events = events_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", deepgram_module)
    monkeypatch.setitem(sys.modules, "deepgram.core", core_module)
    monkeypatch.setitem(sys.modules, "deepgram.core.events", events_module)

    async def audio():
        yield b"speech"
        await asyncio.Event().wait()

    provider = DeepgramStreamingSTT(api_key="test-key")
    with pytest.raises(STTProviderError) as raised:
        async for _ in provider.stream(audio()):
            pass

    assert raised.value.code == "provider_auth_rejected"
    assert "private-test-secret" not in str(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_side", ("listener", "sender"))
async def test_deepgram_task_failure_is_not_hidden_while_audio_is_open(
    monkeypatch: pytest.MonkeyPatch,
    failure_side: str,
) -> None:
    from app.integrations.stt.deepgram import DeepgramStreamingSTT, STTProviderError

    class Connection:
        def on(self, event_type: object, callback: object) -> None:
            del event_type, callback

        async def start_listening(self) -> None:
            if failure_side == "listener":
                raise RuntimeError("simulated result socket closure")
            await asyncio.Event().wait()

        async def send_media(self, audio: bytes) -> None:
            del audio
            if failure_side == "sender":
                raise RuntimeError("simulated result socket closure")

        async def send_finalize(self) -> None:
            return None

    class ConnectContext:
        async def __aenter__(self) -> Connection:
            return Connection()

        async def __aexit__(self, *args: object) -> None:
            return None

    class Client:
        def __init__(self, *, api_key: str) -> None:
            del api_key
            self.listen = SimpleNamespace(
                v1=SimpleNamespace(connect=lambda **kwargs: ConnectContext())
            )

    deepgram_module = ModuleType("deepgram")
    deepgram_module.AsyncDeepgramClient = Client  # type: ignore[attr-defined]
    core_module = ModuleType("deepgram.core")
    events_module = ModuleType("deepgram.core.events")
    events_module.EventType = SimpleNamespace(MESSAGE="message", ERROR="error")  # type: ignore[attr-defined]
    deepgram_module.core = core_module  # type: ignore[attr-defined]
    core_module.events = events_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", deepgram_module)
    monkeypatch.setitem(sys.modules, "deepgram.core", core_module)
    monkeypatch.setitem(sys.modules, "deepgram.core.events", events_module)

    async def open_audio():
        if failure_side == "sender":
            yield b"audio"
        await asyncio.Event().wait()
        yield b"unreachable"

    provider = DeepgramStreamingSTT(api_key="test-key")
    expected_error = "result listener failed" if failure_side == "listener" else "audio sender failed"
    with pytest.raises(STTProviderError, match=expected_error):
        async for _ in provider.stream(open_audio()):
            pass


def test_openai_realtime_transcription_events_do_not_invent_confidence() -> None:
    assert parse_openai_transcription_event(
        {"type": "conversation.item.input_audio_transcription.delta", "delta": "Mujhe"}
    ) == STTEvent(text="Mujhe", is_final=False)
    assert parse_openai_transcription_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "Mujhe Karachi mein ghar chahiye",
        }
    ) == STTEvent(
        text="Mujhe Karachi mein ghar chahiye",
        is_final=True,
        speech_final=True,
    )
    assert parse_openai_transcription_event({"type": "error"}) is None


def test_openai_audio_resampler_converts_pcm16_16k_to_24k() -> None:
    import struct

    audio = struct.pack("<2h", 0, 12000)
    converted = resample_pcm16_16k_to_24k(audio)
    assert len(converted) == 6
    assert struct.unpack("<3h", converted) == (0, 8000, 12000)
