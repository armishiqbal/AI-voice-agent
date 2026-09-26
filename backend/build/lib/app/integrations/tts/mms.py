from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from threading import Lock

from app.integrations.tts.router import AudioChunk, TTSProviderError


class MmsVitsProvider:
    """Local Hugging Face MMS VITS provider.

    MMS checkpoints are language-specific. Create one instance per language
    and register them with ``TTSRouter``. The model is loaded lazily and the
    generated waveform is chunked after synthesis; it is not token-level
    streaming, so latency must be measured before using it for live calls.
    """

    name = "mms-vits"

    def __init__(self, model_id: str, device: str = "auto", chunk_ms: int = 80) -> None:
        self.model_id = model_id
        self.device = device
        self.chunk_ms = chunk_ms
        self._tokenizer = None
        self._model = None
        self._sample_rate = 16_000
        self._load_lock = Lock()

    async def is_ready(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return False
        return True

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        del voice_id
        if not text.strip():
            return
        try:
            audio, sample_rate = await asyncio.to_thread(self._synthesize, text)
        except Exception as error:
            raise TTSProviderError(f"MMS synthesis failed: {error}") from error
        chunk_size = max(2, int(sample_rate * self.chunk_ms / 1000) * 2)
        for sequence, offset in enumerate(range(0, len(audio), chunk_size)):
            yield AudioChunk(
                sequence=sequence,
                audio=audio[offset : offset + chunk_size],
                language=language,
                sample_rate=sample_rate,
            )

    def _synthesize(self, text: str) -> tuple[bytes, int]:
        import numpy as np
        import torch
        from transformers import AutoTokenizer, VitsModel

        if self._model is None or self._tokenizer is None:
            with self._load_lock:
                if self._model is None or self._tokenizer is None:
                    self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
                    self._model = VitsModel.from_pretrained(self.model_id)
                    target = self.device
                    if target == "auto":
                        target = "cuda" if torch.cuda.is_available() else "cpu"
                    self._model.to(target)
                    self._model.eval()
        inputs = self._tokenizer(text, return_tensors="pt")
        model_device = next(self._model.parameters()).device
        inputs = {key: value.to(model_device) for key, value in inputs.items()}
        with torch.no_grad():
            waveform = self._model(**inputs).waveform[0].detach().cpu().numpy()
        pcm = np.clip(waveform, -1.0, 1.0)
        self._sample_rate = int(self._model.config.sampling_rate)
        return (pcm * 32767).astype(np.int16).tobytes(), self._sample_rate
