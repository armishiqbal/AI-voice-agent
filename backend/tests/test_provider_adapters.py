from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.config import Settings
from app.integrations.llm import (
    LLMDecisionError,
    OpenAIStructuredDecisionProvider,
    build_decision_provider,
)
from app.integrations.rag import build_knowledge_store
from app.integrations.rag.pinecone import PineconeKnowledgeStore, RetrievedChunk
from app.integrations.stt import build_english_hybrid_stt, build_urdu_hybrid_stt
from app.integrations.tts import build_tts_router
from app.services.retrieval import GroundedRetriever


def test_llm_provider_is_explicitly_disabled_without_key() -> None:
    assert build_decision_provider(Settings(openai_api_key=None)) is None


def test_structured_decision_provider_uses_bounded_single_attempt(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    provider = build_decision_provider(
        Settings(openai_api_key="test-key", llm_decision_timeout_seconds=2.5)
    )

    assert provider is not None
    assert captured == {"api_key": "test-key", "timeout": 2.5, "max_retries": 0}


def test_structured_decision_provider_uses_fallback_cooldown_after_failure(monkeypatch) -> None:
    calls = 0

    class FailedCompletions:
        def parse(self, **kwargs):
            nonlocal calls
            calls += 1
            raise TimeoutError("synthetic provider timeout")

    class Client:
        beta = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FailedCompletions()))

    provider = OpenAIStructuredDecisionProvider.__new__(OpenAIStructuredDecisionProvider)
    provider.client = Client()
    provider.model = "synthetic"
    provider.timeout_seconds = 0.5
    provider._retry_after = 0.0
    provider._request_lock = threading.Lock()
    provider._request_future = None
    provider._request_executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr("app.integrations.llm.time.monotonic", lambda: 100.0)

    with pytest.raises(LLMDecisionError):
        provider.decide("system", "first turn")
    assert provider.failure_cooldown_remaining == 30.0
    assert provider.last_failure_category == "timeout"
    with pytest.raises(LLMDecisionError, match="short failure cooldown"):
        provider.decide("system", "follow-up turn")

    assert calls == 1
    provider._request_executor.shutdown(wait=True)


def test_structured_decision_provider_retains_sanitized_rate_limit_failure() -> None:
    class RateLimitedCompletions:
        def parse(self, **kwargs):
            del kwargs
            error = RuntimeError("provider details are not included in readiness")
            error.status_code = 429
            raise error

    class Client:
        beta = types.SimpleNamespace(chat=types.SimpleNamespace(completions=RateLimitedCompletions()))

    provider = OpenAIStructuredDecisionProvider.__new__(OpenAIStructuredDecisionProvider)
    provider.client = Client()
    provider.model = "synthetic"
    provider.timeout_seconds = 0.5
    provider._retry_after = 0.0
    provider._last_failure_category = None
    provider._request_lock = threading.Lock()
    provider._request_future = None
    provider._request_executor = ThreadPoolExecutor(max_workers=1)
    try:
        with pytest.raises(LLMDecisionError):
            provider.decide("system", "request")
        assert provider.last_failure_category == "rate_limited"
    finally:
        provider._request_executor.shutdown(wait=True)


def test_structured_decision_provider_enforces_wall_clock_deadline() -> None:
    release_request = threading.Event()
    calls = 0

    class SlowCompletions:
        def parse(self, **kwargs):
            nonlocal calls
            del kwargs
            calls += 1
            release_request.wait(timeout=1)
            raise TimeoutError("synthetic provider timeout")

    class Client:
        beta = types.SimpleNamespace(chat=types.SimpleNamespace(completions=SlowCompletions()))

    provider = OpenAIStructuredDecisionProvider.__new__(OpenAIStructuredDecisionProvider)
    provider.client = Client()
    provider.model = "synthetic"
    provider.timeout_seconds = 0.03
    provider._retry_after = 0.0
    provider._request_lock = threading.Lock()
    provider._request_future = None
    provider._request_executor = ThreadPoolExecutor(max_workers=1)
    started = time.perf_counter()

    try:
        with pytest.raises(LLMDecisionError, match="wall-clock deadline"):
            provider.decide("system", "one slow turn")
        assert time.perf_counter() - started < 0.2
        with pytest.raises(LLMDecisionError, match="failure cooldown"):
            provider.decide("system", "must not start a second request")
        assert calls == 1
    finally:
        release_request.set()
        provider._request_executor.shutdown(wait=True)


def test_knowledge_store_is_explicitly_disabled_without_complete_config() -> None:
    assert (
        build_knowledge_store(
            Settings(openai_api_key=None, pinecone_api_key=None, pinecone_index=None)
        )
        is None
    )


def test_pinecone_upsert_maps_source_metadata(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeIndex:
        def upsert(self, **kwargs):
            captured.update(kwargs)

    class FakePinecone:
        def __init__(self, api_key):
            assert api_key == "test"

        def Index(self, name):
            assert name == "estate"
            return FakeIndex()

    monkeypatch.setitem(
        __import__("sys").modules, "pinecone", type("M", (), {"Pinecone": FakePinecone})
    )

    class Embeddings:
        def embed(self, texts):
            assert texts == ["verified price"]
            return [[0.1, 0.2]]

    store = PineconeKnowledgeStore("test", "estate", Embeddings())
    store.upsert(
        [RetrievedChunk("src-1", "verified price", 1.0, {"city": "Karachi", "version": "v1"})]
    )
    assert captured["namespace"] == "default"
    assert captured["vectors"][0]["metadata"]["text"] == "verified price"


def test_grounded_retriever_filters_rag_by_sql_selected_properties() -> None:
    calls: dict[str, object] = {}

    class Store:
        def query(self, text, metadata_filter, top_k):
            calls.update(text=text, metadata_filter=metadata_filter, top_k=top_k)
            return []

    from app.domain.fixtures import demo_properties

    selected = demo_properties()[:2]
    GroundedRetriever(Store()).context_for("payment plan", selected, top_k=3)
    assert calls["metadata_filter"] == {"property_id": {"$in": ["PROP-001", "PROP-002"]}}


def test_local_tts_registers_every_supported_language_without_loading_models() -> None:
    router = build_tts_router(Settings(_env_file=None, local_tts_enabled=True))
    assert {"ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn"}.issubset(router.providers)


def test_english_hybrid_stt_uses_english_instead_of_unsupported_urdu_multilingual_route() -> None:
    config = Settings(stt_language="multi", deepgram_api_key="test")
    provider = build_english_hybrid_stt(config)
    assert provider.language == "en"
    assert provider.endpointing == config.stt_endpointing_ms


def test_urdu_hybrid_stt_uses_nova3_urdu_and_real_estate_keyterms() -> None:
    config = Settings(deepgram_api_key="test")
    provider = build_urdu_hybrid_stt(config)
    assert provider.model == "nova-3"
    assert provider.language == "ur"
    assert provider.endpointing == config.stt_endpointing_ms
    assert "DHA" in provider.keyterms
    assert "crore" in provider.keyterms


def test_openai_realtime_stt_uses_session_language_and_only_adds_urdu_lish_hint_for_urdu() -> None:
    from app.integrations.stt import OpenAIRealtimeSTT

    provider = OpenAIRealtimeSTT("test-key")
    provider.configure_response_language("ur-Latn")
    assert provider.language == "ur"
    assert "Roman Urdu" in provider.transcription_prompt
    assert "ghar" in provider.transcription_prompt

    provider.configure_response_language("hi")
    assert provider.language == "hi"
    assert provider.transcription_prompt is None


def test_open_source_tts_routes_arabic_separately_from_indic_languages() -> None:
    router = build_tts_router(
        Settings(
            tts_provider="opensource",
            tts_parler_service_url="http://127.0.0.1:8021",
            tts_chatterbox_service_url="http://127.0.0.1:8022",
            tts_service_token="worker-token",
        )
    )

    assert router.providers["ar"].name == "opensource-chatterbox"
    assert router.providers["ur-Latn"].name == "opensource-parler"
    assert router.providers["bn"].name == "opensource-parler"


def test_fish_audio_defaults_to_balanced_low_latency_mode() -> None:
    config = Settings(_env_file=None, fish_audio_api_key="test-key", tts_provider="fish")
    provider = build_tts_router(config).providers["ur-Latn"]
    assert provider.name == "fish-audio"
    assert provider.latency == "balanced"


@pytest.mark.asyncio
async def test_openai_realtime_stt_finishes_if_empty_input_has_no_more_server_events(monkeypatch) -> None:
    import websockets.asyncio.client

    class Connection:
        def __init__(self) -> None:
            self.events: asyncio.Queue[str] = asyncio.Queue()
            self.session_update: dict[str, object] | None = None

        async def send(self, value: str) -> None:
            message = json.loads(value)
            if message["type"] == "session.update":
                self.session_update = message
                await self.events.put(json.dumps({"type": "session.updated"}))

        async def recv(self) -> str:
            return await self.events.get()

        async def close(self) -> None:
            return None

    connection = Connection()
    async def fake_connect(*args, **kwargs):
        return connection

    monkeypatch.setattr(websockets.asyncio.client, "connect", fake_connect)

    async def empty_audio():
        if False:
            yield b""

    from app.integrations.stt import STTEvent
    from app.integrations.stt.openai_realtime import (
        OpenAIRealtimeSTT,
        parse_openai_transcription_event,
    )

    assert parse_openai_transcription_event(
        {"type": "input_audio_buffer.speech_started"}
    ) == STTEvent(speech_started=True)

    async def collect():
        return [event async for event in OpenAIRealtimeSTT("test-key").stream(empty_audio())]

    assert await asyncio.wait_for(collect(), timeout=2) == []


@pytest.mark.asyncio
async def test_openai_realtime_stt_waits_for_delayed_final_after_audio_commit(monkeypatch) -> None:
    import websockets.asyncio.client

    from app.integrations.stt import STTEvent

    class Connection:
        def __init__(self) -> None:
            self.events: asyncio.Queue[str] = asyncio.Queue()
            self.session_update: dict[str, object] | None = None

        async def send(self, value: str) -> None:
            message = json.loads(value)
            if message["type"] == "session.update":
                self.session_update = message
                await self.events.put(json.dumps({"type": "session.updated"}))
            elif message["type"] == "input_audio_buffer.commit":
                asyncio.get_running_loop().call_later(
                    1.15,
                    self.events.put_nowait,
                    json.dumps({
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": "turn-1",
                        "transcript": "Find a property in Karachi",
                    }),
                )

        async def recv(self) -> str:
            return await self.events.get()

        async def close(self) -> None:
            return None

    connection = Connection()
    async def fake_connect(*args, **kwargs):
        return connection

    monkeypatch.setattr(websockets.asyncio.client, "connect", fake_connect)

    async def audio():
        yield b"\x01\x00" * 320
        yield b""

    from app.integrations.stt.openai_realtime import OpenAIRealtimeSTT

    events = [
        event
        async for event in OpenAIRealtimeSTT(
            "test-key",
            finalization_timeout_seconds=2,
            language="ur",
            transcription_prompt="Preserve Pakistani Urdu-English code-switching.",
        ).stream(audio())
    ]
    assert events == [
        STTEvent(
            text="Find a property in Karachi",
            is_final=True,
            speech_final=True,
        )
    ]
    assert connection.session_update is not None
    assert connection.session_update["session"]["audio"]["input"]["turn_detection"] is None
    transcription = connection.session_update["session"]["audio"]["input"]["transcription"]
    assert transcription["language"] == "ur"
    assert transcription["prompt"] == "Preserve Pakistani Urdu-English code-switching."
