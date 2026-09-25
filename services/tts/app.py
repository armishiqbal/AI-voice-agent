from __future__ import annotations

import asyncio
import hmac
import importlib.util
import logging
import os
import re
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Protocol

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

LOGGER = logging.getLogger("awaaz.tts")
ENGINE_NAME = os.getenv("TTS_ENGINE", "parler").casefold()
SERVICE_TOKEN = os.getenv("TTS_SERVICE_TOKEN") or None
MODEL_ID = os.getenv(
    "TTS_MODEL_ID",
    "ai4bharat/indic-parler-tts"
    if ENGINE_NAME == "parler"
    else "ResembleAI/chatterbox",
)
DEVICE = os.getenv("TTS_SERVICE_DEVICE", "auto").casefold()
QUEUE_WAIT_SECONDS = float(os.getenv("TTS_QUEUE_WAIT_SECONDS", "2"))
MAX_TEXT_CHARS = int(os.getenv("TTS_MAX_TEXT_CHARS", "1200"))
_DEFAULT_MODEL_REVISIONS = {
    "parler": "7b527af5ee8ed1f9a28d80b19703ed9bb8ba10ca",
    "chatterbox": "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18",
}
MODEL_REVISION = os.getenv("TTS_MODEL_REVISION") or _DEFAULT_MODEL_REVISIONS.get(
    ENGINE_NAME, ""
)
PARLER_DESCRIPTION_MODEL_ID = os.getenv(
    "TTS_PARLER_DESCRIPTION_TOKENIZER_MODEL_ID", "google/flan-t5-large"
)
PARLER_DESCRIPTION_MODEL_REVISION = os.getenv(
    "TTS_PARLER_DESCRIPTION_TOKENIZER_REVISION",
    "0613663d0d48ea86ba8cb3d7a44f0f65dc596a2a",
)

_ENGINE_LANGUAGES: dict[str, frozenset[str]] = {
    "parler": frozenset({"ur-Latn", "ur-Arab", "en", "hi", "pa", "bn"}),
    "chatterbox": frozenset({"ar", "en", "hi"}),
}


class SpeechEngine(Protocol):
    @property
    def loaded(self) -> bool: ...

    @property
    def device(self) -> str: ...

    def synthesize(self, text: str, language: str) -> tuple[bytes, int]: ...


class SynthesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    language: str = Field(min_length=2, max_length=12)


class ParlerEngine:
    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._description_tokenizer = None
        self._device = _select_device()
        self._inference_lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    def synthesize(self, text: str, language: str) -> tuple[bytes, int]:
        import torch

        with self._inference_lock:
            return self._synthesize_locked(text, language, torch)

    def _synthesize_locked(self, text: str, language: str, torch) -> tuple[bytes, int]:
        self._load()
        if language == "ur-Latn":
            style = "A clear speaker delivers Pakistani Urdu in a conversational style."
        elif language in {"ur-Arab", "pa", "bn", "hi"}:
            style = "A clear native speaker delivers the requested language conversationally."
        else:
            style = "A clear speaker delivers Indian English conversationally."
        description = f"{style} The voice is warm, natural, and easy to understand, with a moderate pace."
        description_inputs = self._description_tokenizer(
            description, return_tensors="pt"
        ).to(self._device)
        prompt_inputs = self._tokenizer(text, return_tensors="pt").to(self._device)
        with torch.inference_mode():
            audio = self._model.generate(
                input_ids=description_inputs.input_ids,
                attention_mask=description_inputs.attention_mask,
                prompt_input_ids=prompt_inputs.input_ids,
                prompt_attention_mask=prompt_inputs.attention_mask,
            )
        sample_rate = int(self._model.config.sampling_rate)
        return _pcm16_bytes(audio), sample_rate

    def _load(self) -> None:
        if (
            self._model is not None
            and self._tokenizer is not None
            and self._description_tokenizer is not None
        ):
            return
        from huggingface_hub import snapshot_download
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        token = os.getenv("HF_TOKEN")
        model_snapshot = snapshot_download(
            repo_id=MODEL_ID,
            revision=MODEL_REVISION,
            repo_type="model",
            token=token,
        )
        model = ParlerTTSForConditionalGeneration.from_pretrained(
            model_snapshot, token=token
        ).to(self._device)
        model.eval()
        tokenizer = AutoTokenizer.from_pretrained(model_snapshot, token=token)
        description_model_id = model.config.text_encoder._name_or_path
        if description_model_id != PARLER_DESCRIPTION_MODEL_ID:
            raise RuntimeError(
                "Configured Parler description tokenizer model does not match "
                "the model's text encoder"
            )
        description_tokenizer = AutoTokenizer.from_pretrained(
            PARLER_DESCRIPTION_MODEL_ID,
            revision=PARLER_DESCRIPTION_MODEL_REVISION,
            token=token,
        )
        self._model = model
        self._tokenizer = tokenizer
        self._description_tokenizer = description_tokenizer


class ChatterboxEngine:
    def __init__(self) -> None:
        self._model = None
        self._device = _select_device()
        self._inference_lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    def synthesize(self, text: str, language: str) -> tuple[bytes, int]:
        import torch

        with self._inference_lock:
            return self._synthesize_locked(text, language, torch)

    def _synthesize_locked(self, text: str, language: str, torch) -> tuple[bytes, int]:
        self._load()
        with torch.inference_mode():
            audio = self._model.generate(text, language_id=language)
        return _pcm16_bytes(audio), int(self._model.sr)

    def _load(self) -> None:
        if self._model is not None:
            return
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        from huggingface_hub import snapshot_download

        model_snapshot = snapshot_download(
            repo_id=MODEL_ID,
            repo_type="model",
            revision=MODEL_REVISION,
            token=os.getenv("HF_TOKEN"),
            allow_patterns=[
                "ve.pt",
                "t3_mtl23ls_v3.safetensors",
                "s3gen.pt",
                "grapheme_mtl_merged_expanded_v1.json",
                "conds.pt",
                "Cangjie5_TC.json",
            ],
        )
        self._model = ChatterboxMultilingualTTS.from_local(
            model_snapshot, device=self._device, t3_model="v3"
        )


def _select_device() -> str:
    import torch

    if DEVICE != "auto":
        if DEVICE == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("TTS_SERVICE_DEVICE=cuda but CUDA is unavailable")
        if DEVICE == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("TTS_SERVICE_DEVICE=mps but MPS is unavailable")
        if DEVICE not in {"cpu", "cuda", "mps"}:
            raise RuntimeError("TTS_SERVICE_DEVICE must be auto, cpu, cuda, or mps")
        return DEVICE
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _pcm16_bytes(audio: object) -> bytes:
    import numpy as np

    waveform = audio
    if hasattr(waveform, "detach"):
        waveform = waveform.detach().to("cpu").numpy()
    samples = np.asarray(waveform, dtype=np.float32).squeeze()
    if samples.ndim != 1 or samples.size == 0:
        raise ValueError("TTS model returned an empty or non-mono waveform")
    samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0)
    return (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def _dependencies_available(engine: str) -> bool:
    common = importlib.util.find_spec("torch") is not None
    if engine == "parler":
        return common and all(
            importlib.util.find_spec(module)
            for module in ("parler_tts", "transformers", "huggingface_hub")
        )
    if engine == "chatterbox":
        return common and all(
            importlib.util.find_spec(module)
            for module in ("chatterbox", "transformers", "huggingface_hub")
        )
    return False


@lru_cache(maxsize=1)
def _get_engine() -> SpeechEngine:
    if ENGINE_NAME == "parler":
        return ParlerEngine()
    if ENGINE_NAME == "chatterbox":
        return ChatterboxEngine()
    raise RuntimeError("TTS_ENGINE must be parler or chatterbox")


def _authorize(authorization: str | None) -> None:
    if SERVICE_TOKEN is None:
        raise HTTPException(status_code=503, detail="TTS service authentication is not configured")
    expected = f"Bearer {SERVICE_TOKEN}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid TTS service credentials")


def _sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?؟۔])\s+", text.strip()) if part]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if SERVICE_TOKEN is None:
        raise RuntimeError("TTS_SERVICE_TOKEN must be configured before starting the worker")
    if not re.fullmatch(r"[0-9a-f]{40}", MODEL_REVISION):
        raise RuntimeError("TTS_MODEL_REVISION must be a full immutable commit SHA")
    if ENGINE_NAME == "parler" and not re.fullmatch(
        r"[0-9a-f]{40}", PARLER_DESCRIPTION_MODEL_REVISION
    ):
        raise RuntimeError(
            "TTS_PARLER_DESCRIPTION_TOKENIZER_REVISION must be a full immutable commit SHA"
        )
    yield


app = FastAPI(
    title="Awaaz local TTS worker",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
_generation_slot = asyncio.Semaphore(1)


class _InferenceLease:
    """Keep the worker slot leased until cancelled thread inference really stops.

    Cancelling ``asyncio.to_thread`` only cancels its awaiter; the native/model work
    continues in the thread. Releasing the semaphore at that point can create an
    unbounded queue of abandoned inference threads during repeated barge-ins.
    """

    def __init__(self, release_slot: Callable[[], None]) -> None:
        self._release_slot = release_slot
        self._in_flight = 0
        self._close_requested = False
        self._released = False

    async def synthesize(
        self, engine: SpeechEngine, text: str, language: str
    ) -> tuple[bytes, int]:
        task = asyncio.create_task(asyncio.to_thread(engine.synthesize, text, language))
        self._in_flight += 1
        task.add_done_callback(self._inference_finished)
        return await asyncio.shield(task)

    def close(self) -> None:
        self._close_requested = True
        self._release_if_idle()

    def _inference_finished(self, task: asyncio.Task[tuple[bytes, int]]) -> None:
        self._in_flight -= 1
        # Consume failures from a thread task that its HTTP request abandoned.
        if not task.cancelled():
            task.exception()
        self._release_if_idle()

    def _release_if_idle(self) -> None:
        if self._close_requested and self._in_flight == 0 and not self._released:
            self._released = True
            self._release_slot()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    _authorize(authorization)
    if ENGINE_NAME not in _ENGINE_LANGUAGES:
        raise HTTPException(status_code=503, detail="Unknown TTS engine")
    available = _dependencies_available(ENGINE_NAME)
    try:
        engine = _get_engine() if available else None
        model_loaded = engine.loaded if engine else False
        device = engine.device if engine else DEVICE
    except Exception:  # noqa: BLE001 - readiness must fail closed
        available = False
        model_loaded = False
        device = DEVICE
    return {
        "ready": available and model_loaded,
        "engine": ENGINE_NAME,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "description_tokenizer_revision": (
            PARLER_DESCRIPTION_MODEL_REVISION if ENGINE_NAME == "parler" else None
        ),
        "supported_languages": sorted(_ENGINE_LANGUAGES[ENGINE_NAME]),
        "model_loaded": model_loaded,
        "device": device,
    }


@app.post("/v1/warmup")
async def warmup(
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """Explicitly download/load the model and run one smoke synthesis before traffic."""

    _authorize(authorization)
    if not _dependencies_available(ENGINE_NAME):
        raise HTTPException(
            status_code=503, detail="TTS engine dependencies are not installed"
        )
    language, phrase = (
        ("en", "Hello. I can help you find a property.")
        if ENGINE_NAME == "parler"
        else ("ar", "مرحباً، كيف يمكنني مساعدتك؟")
    )
    try:
        await asyncio.wait_for(_generation_slot.acquire(), timeout=QUEUE_WAIT_SECONDS)
    except TimeoutError as error:
        raise HTTPException(status_code=503, detail="TTS worker is busy") from error
    lease = _InferenceLease(_generation_slot.release)
    started = asyncio.get_running_loop().time()
    try:
        engine = _get_engine()
        audio, sample_rate = await lease.synthesize(engine, phrase, language)
    except asyncio.CancelledError:
        lease.close()
        raise
    except Exception as error:
        lease.close()
        LOGGER.exception("TTS warmup failed for engine %s", ENGINE_NAME)
        raise HTTPException(
            status_code=503, detail="TTS model warmup failed"
        ) from error
    lease.close()
    return {
        "ready": bool(audio),
        "engine": ENGINE_NAME,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "description_tokenizer_revision": (
            PARLER_DESCRIPTION_MODEL_REVISION if ENGINE_NAME == "parler" else None
        ),
        "device": engine.device,
        "sample_rate": sample_rate,
        "warmup_ms": round((asyncio.get_running_loop().time() - started) * 1000, 2),
    }


@app.post("/v1/synthesize")
async def synthesize(
    request: SynthesisRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    _authorize(authorization)
    if len(request.text) > MAX_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="Text exceeds the configured limit")
    if request.language not in _ENGINE_LANGUAGES.get(ENGINE_NAME, frozenset()):
        raise HTTPException(
            status_code=422, detail="Language is not supported by this TTS engine"
        )
    if not _dependencies_available(ENGINE_NAME):
        raise HTTPException(
            status_code=503, detail="TTS engine dependencies are not installed"
        )
    try:
        await asyncio.wait_for(_generation_slot.acquire(), timeout=QUEUE_WAIT_SECONDS)
    except TimeoutError as error:
        raise HTTPException(status_code=503, detail="TTS worker is busy") from error

    sentences = _sentences(request.text)
    if not sentences:
        _generation_slot.release()
        raise HTTPException(
            status_code=422, detail="Text must contain spoken characters"
        )
    lease = _InferenceLease(_generation_slot.release)
    try:
        engine = _get_engine()
        first_audio, sample_rate = await lease.synthesize(
            engine, sentences[0], request.language
        )
    except asyncio.CancelledError:
        lease.close()
        raise
    except Exception as error:
        lease.close()
        LOGGER.exception("TTS synthesis failed for engine %s", ENGINE_NAME)
        raise HTTPException(status_code=503, detail="TTS synthesis failed") from error

    async def stream() -> AsyncIterator[bytes]:
        try:
            yield first_audio
            for sentence in sentences[1:]:
                audio, next_sample_rate = await lease.synthesize(
                    engine, sentence, request.language
                )
                if next_sample_rate != sample_rate:
                    raise RuntimeError("TTS sample rate changed inside a response")
                yield audio
        finally:
            lease.close()

    return StreamingResponse(
        stream(),
        media_type="application/octet-stream",
        headers={
            "X-Audio-Sample-Rate": str(sample_rate),
            "X-Audio-Encoding": "pcm_s16le",
            "X-TTS-Engine": ENGINE_NAME,
        },
        background=BackgroundTask(lease.close),
    )
