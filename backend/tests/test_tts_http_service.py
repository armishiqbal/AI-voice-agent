from __future__ import annotations

import asyncio
import sys
import threading
from types import ModuleType

import httpx
import pytest
from fastapi.testclient import TestClient
from scripts.voice import run_tts
from services.tts import app as tts_app
from services.tts.app import ChatterboxEngine, ParlerEngine, _InferenceLease

from app.integrations.tts.service import HTTPTextToSpeechProvider


class FakeEngine:
    loaded = False
    device = "cpu"

    def __init__(self) -> None:
        self.loaded = False
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text: str, language: str) -> tuple[bytes, int]:
        self.calls.append((text, language))
        self.loaded = True
        return b"\x01\x00" * 8, 24_000


@pytest.mark.asyncio
async def test_cancelled_synthesis_holds_slot_until_model_thread_finishes() -> None:
    started = threading.Event()
    finish = threading.Event()
    slot = asyncio.Semaphore(1)
    await slot.acquire()
    lease = _InferenceLease(slot.release)

    class BlockingEngine:
        def synthesize(self, text: str, language: str) -> tuple[bytes, int]:
            del text, language
            started.set()
            if not finish.wait(timeout=2):
                raise TimeoutError("test synthesis was not released")
            return b"\x01\x00", 24_000

    synthesis = asyncio.create_task(lease.synthesize(BlockingEngine(), "Hello", "en"))
    assert await asyncio.to_thread(started.wait, 2)
    synthesis.cancel()
    with pytest.raises(asyncio.CancelledError):
        await synthesis

    lease.close()
    assert slot.locked()

    finish.set()
    await asyncio.wait_for(slot.acquire(), timeout=2)
    slot.release()


def test_local_tts_worker_auth_language_and_stream_contract(monkeypatch) -> None:
    engine = FakeEngine()
    monkeypatch.setattr(tts_app, "ENGINE_NAME", "parler")
    monkeypatch.setattr(tts_app, "SERVICE_TOKEN", "service-secret")
    monkeypatch.setattr(tts_app, "_dependencies_available", lambda _: True)
    monkeypatch.setattr(tts_app, "_get_engine", lambda: engine)

    with TestClient(tts_app.app) as client:
        assert client.get("/readyz").status_code == 401
        ready = client.get("/readyz", headers={"Authorization": "Bearer service-secret"})
        assert ready.json() == {
            "ready": False,
            "engine": "parler",
            "model_id": tts_app.MODEL_ID,
            "model_revision": tts_app.MODEL_REVISION,
            "description_tokenizer_revision": tts_app.PARLER_DESCRIPTION_MODEL_REVISION,
            "supported_languages": sorted(tts_app._ENGINE_LANGUAGES["parler"]),
            "model_loaded": False,
            "device": "cpu",
        }

        unsupported = client.post(
            "/v1/synthesize",
            json={"text": "Hello", "language": "ar"},
            headers={"Authorization": "Bearer service-secret"},
        )
        assert unsupported.status_code == 422

        warmup = client.post("/v1/warmup", headers={"Authorization": "Bearer service-secret"})
        assert warmup.status_code == 200
        assert warmup.json()["ready"] is True

        warmed = client.get("/readyz", headers={"Authorization": "Bearer service-secret"})
        assert warmed.json()["ready"] is True

        response = client.post(
            "/v1/synthesize",
            json={"text": "First sentence. Second sentence.", "language": "en"},
            headers={"Authorization": "Bearer service-secret"},
        )
        assert response.status_code == 200
        assert response.headers["x-audio-sample-rate"] == "24000"
        assert response.headers["x-audio-encoding"] == "pcm_s16le"
        assert response.content == b"\x01\x00" * 16
        assert engine.calls == [
            ("Hello. I can help you find a property.", "en"),
            ("First sentence.", "en"),
            ("Second sentence.", "en"),
        ]


def test_tts_worker_refuses_to_start_without_service_token(monkeypatch) -> None:
    monkeypatch.setattr(tts_app, "SERVICE_TOKEN", None)
    with pytest.raises(RuntimeError, match="TTS_SERVICE_TOKEN"), TestClient(tts_app.app):
        pass


def test_tts_worker_requires_immutable_model_revision(monkeypatch) -> None:
    monkeypatch.setattr(tts_app, "MODEL_REVISION", "main")
    monkeypatch.setattr(tts_app, "SERVICE_TOKEN", "test-token")
    with pytest.raises(RuntimeError, match="immutable commit SHA"), TestClient(tts_app.app):
        pass


def test_chatterbox_load_uses_pinned_snapshot_and_v3_local_loader(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def download_snapshot(**kwargs):
        calls["snapshot"] = kwargs
        return "/models/chatterbox-pinned"

    class FakeChatterbox:
        @classmethod
        def from_local(cls, checkpoint_dir, device, t3_model=None):
            calls["from_local"] = (checkpoint_dir, device, t3_model)
            return object()

    hub = ModuleType("huggingface_hub")
    hub.snapshot_download = download_snapshot
    chatterbox = ModuleType("chatterbox")
    chatterbox.__path__ = []
    multilingual = ModuleType("chatterbox.mtl_tts")
    multilingual.ChatterboxMultilingualTTS = FakeChatterbox
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "chatterbox", chatterbox)
    monkeypatch.setitem(sys.modules, "chatterbox.mtl_tts", multilingual)
    monkeypatch.setattr(tts_app, "MODEL_ID", "ResembleAI/chatterbox")
    monkeypatch.setattr(tts_app, "MODEL_REVISION", "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18")

    engine = object.__new__(ChatterboxEngine)
    engine._model = None
    engine._device = "cpu"
    engine._inference_lock = threading.Lock()
    engine._load()

    snapshot = calls["snapshot"]
    assert snapshot["revision"] == tts_app.MODEL_REVISION
    assert "t3_mtl23ls_v3.safetensors" in snapshot["allow_patterns"]
    assert calls["from_local"] == (
        "/models/chatterbox-pinned",
        "cpu",
        "v3",
    )


def test_parler_load_pins_model_and_description_tokenizer(monkeypatch) -> None:
    calls: dict[str, object] = {"tokenizers": []}

    def download_snapshot(**kwargs):
        calls["snapshot"] = kwargs
        return "/models/parler-pinned"

    class FakeTextEncoder:
        _name_or_path = "google/flan-t5-large"

    class FakeModel:
        config = type("Config", (), {"text_encoder": FakeTextEncoder()})()

        def to(self, device):
            calls["device"] = device
            return self

        def eval(self):
            return self

    class FakeParler:
        @classmethod
        def from_pretrained(cls, model_path, token=None):
            calls["parler_load"] = (model_path, token)
            return FakeModel()

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            calls["tokenizers"].append((model_id, kwargs))
            return object()

    hub = ModuleType("huggingface_hub")
    hub.snapshot_download = download_snapshot
    parler = ModuleType("parler_tts")
    parler.ParlerTTSForConditionalGeneration = FakeParler
    transformers = ModuleType("transformers")
    transformers.AutoTokenizer = FakeTokenizer
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "parler_tts", parler)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setenv("HF_TOKEN", "gated-model-token")

    engine = object.__new__(ParlerEngine)
    engine._model = None
    engine._tokenizer = None
    engine._description_tokenizer = None
    engine._device = "cpu"
    engine._inference_lock = threading.Lock()
    engine._load()

    assert calls["snapshot"]["revision"] == tts_app.MODEL_REVISION
    assert calls["snapshot"]["token"] == "gated-model-token"
    assert calls["parler_load"] == ("/models/parler-pinned", "gated-model-token")
    assert calls["tokenizers"][0][0] == "/models/parler-pinned"
    assert calls["tokenizers"][1] == (
        tts_app.PARLER_DESCRIPTION_MODEL_ID,
        {
            "revision": tts_app.PARLER_DESCRIPTION_MODEL_REVISION,
            "token": "gated-model-token",
        },
    )


def test_tts_launcher_refuses_to_start_without_service_token(monkeypatch) -> None:
    monkeypatch.setenv("TTS_SERVICE_HOST", "127.0.0.1")
    monkeypatch.delenv("TTS_SERVICE_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="TTS_SERVICE_TOKEN"):
        run_tts.main()


@pytest.mark.asyncio
async def test_remote_tts_adapter_checks_health_and_rechunks_pcm(monkeypatch) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/readyz":
            return httpx.Response(
                200,
                json={
                    "ready": True,
                    "model_loaded": True,
                    "engine": "parler",
                    "supported_languages": ["en", "ur-Latn"],
                },
            )
        return httpx.Response(
            200,
            headers={"x-audio-sample-rate": "24000", "x-audio-encoding": "pcm_s16le"},
            content=b"\x02\x00" * 2_000,
        )

    transport = httpx.MockTransport(handler)
    client_type = httpx.AsyncClient

    def mock_client(**kwargs):
        return client_type(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)
    provider = HTTPTextToSpeechProvider(
        "https://tts.local",
        "parler",
        required_languages={"en", "ur-Latn"},
        api_key="secret",
        chunk_ms=80,
    )

    assert await provider.is_ready()
    chunks = [chunk async for chunk in provider.synthesize_stream("Hello", "en")]

    assert [len(chunk.audio) for chunk in chunks] == [3_840, 160]
    assert all(chunk.sample_rate == 24_000 for chunk in chunks)
    assert all(chunk.encoding == "pcm_s16le" for chunk in chunks)
    assert all(request.headers["authorization"] == "Bearer secret" for request in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "ready": True,
            "model_loaded": True,
            "engine": "parler",
            "supported_languages": ["en", "ur-Latn"],
        },
        {
            "ready": True,
            "model_loaded": True,
            "engine": "chatterbox",
            "supported_languages": ["en", "ur-Arab"],
        },
        {
            "ready": True,
            "model_loaded": False,
            "engine": "parler",
            "supported_languages": ["en", "ur-Arab"],
        },
        {"ready": True, "model_loaded": True, "engine": "parler"},
        {
            "ready": True,
            "model_loaded": True,
            "engine": "parler",
            "supported_languages": "en,ur-Arab",
        },
    ],
    ids=["missing-language", "wrong-engine", "model-not-loaded", "missing-list", "malformed-list"],
)
async def test_remote_tts_readiness_fails_closed_for_incompatible_worker(
    monkeypatch, payload: dict[str, object]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async_client_type = httpx.AsyncClient

    def mock_client(**kwargs):
        return async_client_type(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)
    provider = HTTPTextToSpeechProvider(
        "https://tts.local",
        "parler",
        required_languages={"en", "ur-Arab"},
        api_key="secret",
    )
    assert await provider.is_ready() is False


def test_remote_tts_service_requires_https_and_a_token() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        HTTPTextToSpeechProvider(
            "http://tts.example.com",
            "parler",
            required_languages={"en"},
            api_key="secret",
        )
    with pytest.raises(ValueError, match="authentication token"):
        HTTPTextToSpeechProvider("https://tts.example.com", "parler", required_languages={"en"})
