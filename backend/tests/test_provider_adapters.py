from __future__ import annotations

import asyncio
import json

import pytest

from app.core.config import Settings
from app.integrations.llm import build_decision_provider
from app.integrations.rag import build_knowledge_store
from app.integrations.rag.pinecone import PineconeKnowledgeStore, RetrievedChunk
from app.integrations.tts import build_tts_router
from app.services.retrieval import GroundedRetriever


def test_llm_provider_is_explicitly_disabled_without_key() -> None:
    assert build_decision_provider(Settings(openai_api_key=None)) is None


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
    router = build_tts_router(Settings(local_tts_enabled=True))
    assert {"ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn"}.issubset(router.providers)


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


@pytest.mark.asyncio
async def test_openai_realtime_stt_finishes_if_empty_input_has_no_more_server_events(monkeypatch) -> None:
    import websockets.asyncio.client

    class Connection:
        def __init__(self) -> None:
            self.events: asyncio.Queue[str] = asyncio.Queue()

        async def send(self, value: str) -> None:
            message = json.loads(value)
            if message["type"] == "session.update":
                await self.events.put(json.dumps({"type": "session.updated"}))

        async def recv(self) -> str:
            return await self.events.get()

    connection = Connection()

    class ConnectionContext:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(websockets.asyncio.client, "connect", lambda *args, **kwargs: ConnectionContext())

    async def empty_audio():
        if False:
            yield b""

    from app.integrations.stt.openai_realtime import OpenAIRealtimeSTT

    async def collect():
        return [event async for event in OpenAIRealtimeSTT("test-key").stream(empty_audio())]

    assert await asyncio.wait_for(collect(), timeout=2) == []
