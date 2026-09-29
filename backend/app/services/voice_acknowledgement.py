"""Bounded, non-factual voice acknowledgements used while a real turn is processed."""

import asyncio

from app.integrations.tts.router import AudioChunk, TTSProvider, TTSProviderError

ACKNOWLEDGEMENTS = {
    "ur-Latn": "Ji, ek second.",
    "ur-Arab": "جی، ایک لمحہ۔",
    "en": "Sure, one moment.",
    "hi": "जी, एक क्षण।",
    "ar": "حسنًا، لحظة من فضلك.",
    "pa": "جی، اک پل۔",
    "bn": "জি, এক মুহূর্ত।",
}
MAX_ACKNOWLEDGEMENT_AUDIO_BYTES = 128_000
ACKNOWLEDGEMENT_PREPARE_TIMEOUT_SECONDS = 12.0


def acknowledgement_text(language: str) -> str | None:
    return ACKNOWLEDGEMENTS.get(language)


async def prepare_acknowledgement(
    provider: TTSProvider,
    language: str,
) -> tuple[AudioChunk, ...]:
    """Synthesize a short filler before listening, with strict memory and output bounds."""

    text = acknowledgement_text(language)
    if text is None:
        raise TTSProviderError("No spoken acknowledgement is defined for this language")
    chunks: list[AudioChunk] = []
    total_bytes = 0
    async for chunk in provider.synthesize_stream(text, language):
        if not chunk.audio:
            continue
        total_bytes += len(chunk.audio)
        if total_bytes > MAX_ACKNOWLEDGEMENT_AUDIO_BYTES:
            raise TTSProviderError("Voice acknowledgement exceeded its audio limit")
        chunks.append(chunk)
    if not chunks:
        raise TTSProviderError("Voice acknowledgement returned no audio")
    return tuple(chunks)


class VoiceAcknowledgementCache:
    """Share one bounded acknowledgement synthesis across sessions in this process."""

    def __init__(self) -> None:
        self._audio: dict[tuple[int, str], tuple[AudioChunk, ...]] = {}
        self._pending: dict[
            tuple[int, str], asyncio.Task[tuple[AudioChunk, ...]]
        ] = {}

    def get(self, provider: TTSProvider, language: str) -> tuple[AudioChunk, ...] | None:
        return self._audio.get((id(provider), language))

    def warm(
        self, provider: TTSProvider, language: str
    ) -> asyncio.Task[tuple[AudioChunk, ...]] | None:
        """Start one synthesis per provider/language, or reuse cached/in-flight work."""
        key = (id(provider), language)
        if key in self._audio:
            return None
        task = self._pending.get(key)
        if task is not None and not task.done():
            return task
        if task is not None:
            self._pending.pop(key, None)
        task = asyncio.create_task(self._prepare(key, provider, language))
        self._pending[key] = task
        task.add_done_callback(lambda completed: self._finish(key, completed))
        return task

    async def aclose(self) -> None:
        """Cancel unfinished provider requests before the shared TTS client closes."""
        tasks = list(self._pending.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._pending.clear()

    async def _prepare(
        self, key: tuple[int, str], provider: TTSProvider, language: str
    ) -> tuple[AudioChunk, ...]:
        async with asyncio.timeout(ACKNOWLEDGEMENT_PREPARE_TIMEOUT_SECONDS):
            chunks = await prepare_acknowledgement(provider, language)
        self._audio[key] = chunks
        return chunks

    def _finish(
        self,
        key: tuple[int, str],
        task: asyncio.Task[tuple[AudioChunk, ...]],
    ) -> None:
        if self._pending.get(key) is task:
            self._pending.pop(key, None)
        if not task.cancelled():
            # Retrieve failures even when every waiting session timed out.
            task.exception()
