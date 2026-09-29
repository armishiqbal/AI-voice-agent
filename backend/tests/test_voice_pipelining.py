from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.domain.emotions import ENTHUSIASTIC_PROFILE
from app.integrations.tts.router import AudioChunk
from app.services.voice_stream import (
    pipeline_synthesize_clauses,
    split_conversational_clauses,
)


class MockStreamingTTS:
    name = "mock-tts"

    def __init__(self, chunk_delay: float = 0.01) -> None:
        self.chunk_delay = chunk_delay
        self.received_texts: list[str] = []

    async def synthesize_stream(
        self, text: str, language: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        self.received_texts.append(text)
        words = text.split()
        for idx, word in enumerate(words):
            if self.chunk_delay > 0:
                await asyncio.sleep(self.chunk_delay)
            yield AudioChunk(
                sequence=idx,
                audio=f"audio:{word}".encode(),
                language=language,
                sample_rate=24_000,
                encoding="pcm_s16le",
                is_final=False,
            )

    async def is_ready(self) -> bool:
        return True


def test_split_conversational_clauses():
    text = "Ji bilkul, DHA Phase 6 mein 1 Kanal ke houses available hain. Price 6.5 crore hai."
    clauses = split_conversational_clauses(text)
    assert len(clauses) >= 2
    assert clauses[0] == "Ji bilkul,"
    assert "DHA Phase 6 mein" in clauses[1]

    # Without starter
    text_simple = "Hamare paas luxury apartments available hain. Visit schedule kar lein."
    clauses_simple = split_conversational_clauses(text_simple)
    assert len(clauses_simple) == 2
    assert "Hamare paas luxury apartments" in clauses_simple[0]
    assert "Visit schedule" in clauses_simple[1]


@pytest.mark.asyncio
async def test_pipeline_synthesize_clauses_orders_and_completes():
    provider = MockStreamingTTS(chunk_delay=0.005)
    text = "Ji bilkul, DHA Phase 6 mein options hain. Price bohot munasib hai."

    chunks: list[AudioChunk] = []
    async for chunk in pipeline_synthesize_clauses(provider, text, language="ur-Latn"):
        chunks.append(chunk)

    assert len(chunks) > 2
    # Verify monotonic sequences: 0, 1, 2, ...
    sequences = [c.sequence for c in chunks]
    assert sequences == list(range(len(chunks)))
    # Verify final chunk is empty and marked is_final
    assert chunks[-1].is_final is True
    assert chunks[-1].audio == b""
    # Check intermediate chunks
    assert all(not c.is_final for c in chunks[:-1])
    assert all(len(c.audio) > 0 for c in chunks[:-1])


@pytest.mark.asyncio
async def test_next_clause_starts_after_first_audio_is_available():
    second_started = asyncio.Event()
    hold_first = asyncio.Event()

    class Provider:
        async def synthesize_stream(self, text, language):
            if text == "First.":
                yield AudioChunk(sequence=0, audio=b"\x00\x00", language=language)
                await hold_first.wait()
            else:
                second_started.set()
                yield AudioChunk(sequence=0, audio=b"\x00\x00", language=language)

    stream = pipeline_synthesize_clauses(Provider(), "First. Second.")
    try:
        first = await asyncio.wait_for(anext(stream), timeout=1)
        assert first.audio
        assert not second_started.is_set()
        await asyncio.sleep(0)
        assert second_started.is_set()
    finally:
        await asyncio.wait_for(stream.aclose(), timeout=1)
        hold_first.set()


@pytest.mark.asyncio
async def test_pipeline_synthesize_clauses_disabled_fallback():
    provider = MockStreamingTTS(chunk_delay=0.001)
    text = "Single sentence fallback."

    chunks: list[AudioChunk] = []
    async for chunk in pipeline_synthesize_clauses(provider, text, enabled=False):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert provider.received_texts == ["Single sentence fallback."]


@pytest.mark.asyncio
async def test_pipeline_synthesize_clauses_applies_fish_emotion_tag():
    provider = MockStreamingTTS(chunk_delay=0.001)
    provider.name = "fish-audio"
    text = "Ji bilkul, shandar penthouse hai!"

    chunks: list[AudioChunk] = []
    async for chunk in pipeline_synthesize_clauses(
        provider, text, emotion=ENTHUSIASTIC_PROFILE, enabled=True
    ):
        chunks.append(chunk)

    assert len(chunks) > 0
    # First clause should include the Fish Audio tag
    assert any("[enthusiastic]" in t for t in provider.received_texts)


@pytest.mark.asyncio
async def test_pipeline_synthesize_clauses_handles_cancellation():
    provider = MockStreamingTTS(chunk_delay=0.1)
    text = "Ji bilkul, DHA Phase 6 mein options hain. Yeh bohot lamba sentence hai."

    stream = pipeline_synthesize_clauses(provider, text)
    first_chunk = await stream.__anext__()
    assert first_chunk.audio
    # Close generator abruptly (simulating caller barge-in cancellation)
    await stream.aclose()
