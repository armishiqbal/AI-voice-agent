from __future__ import annotations

import asyncio

import pytest

from app.integrations.tts.router import AudioChunk, TTSProviderError
from app.services.voice_stream import pipeline_synthesize_clauses


def chunk(sequence: int, language: str = "en") -> AudioChunk:
    return AudioChunk(sequence=sequence, audio=b"\x00\x00", language=language)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,text", [(False, "Hello."), (True, "Hello."), (True, "Hello. Another sentence.")]
)
async def test_legacy_two_argument_provider_works(enabled, text):
    class Provider:
        async def synthesize_stream(self, text, language):
            yield chunk(0, language)

    async def collect():
        return [
            item async for item in pipeline_synthesize_clauses(Provider(), text, enabled=enabled)
        ]

    audio = await asyncio.wait_for(collect(), timeout=1)
    assert any(item.audio for item in audio)


@pytest.mark.asyncio
async def test_prefetch_is_bounded_and_close_cancels_full_queues():
    started = []
    produced = {}
    closed = []

    class Provider:
        async def synthesize_stream(self, text, language):
            started.append(text)
            produced[text] = 0
            try:
                for index in range(1000):
                    produced[text] += 1
                    yield chunk(index, language)
            finally:
                closed.append(text)

    stream = pipeline_synthesize_clauses(Provider(), "First. Second. Third. Fourth.")
    await asyncio.wait_for(anext(stream), timeout=1)
    # Let both producers reach their full queues while downstream is paused.
    for _ in range(5):
        await asyncio.sleep(0)
    assert started == ["First.", "Second."]
    # Four queued, one producer-held, plus at most one already consumed chunk.
    assert all(count <= 6 for count in produced.values())
    await asyncio.wait_for(stream.aclose(), timeout=1)
    assert sorted(closed) == sorted(started)


@pytest.mark.asyncio
async def test_provider_failure_is_expected_error_and_cancels_prefetch():
    closed = []

    class Provider:
        async def synthesize_stream(self, text, language):
            try:
                if text == "First.":
                    raise RuntimeError("unexpected provider error")
                while True:
                    yield chunk(0, language)
            finally:
                closed.append(text)

    async def collect():
        return [item async for item in pipeline_synthesize_clauses(Provider(), "First. Second.")]

    with pytest.raises(TTSProviderError, match="Speech synthesis failed"):
        await asyncio.wait_for(collect(), timeout=1)
    assert "First." in closed


@pytest.mark.asyncio
async def test_clause_order_sequences_and_only_one_final_marker():
    class Provider:
        async def synthesize_stream(self, text, language, voice_id=None):
            assert voice_id == "chosen"
            yield AudioChunk(sequence=7, audio=text.encode(), language=language)
            yield AudioChunk(sequence=8, audio=b"", language=language, is_final=True)

    async def collect():
        return [
            item
            async for item in pipeline_synthesize_clauses(
                Provider(), "First. Second. Third.", voice_id="chosen"
            )
        ]

    audio = await asyncio.wait_for(collect(), timeout=1)
    assert [item.audio for item in audio] == [b"First.", b"Second.", b"Third.", b""]
    assert [item.sequence for item in audio] == [0, 1, 2, 3]
    assert [item.is_final for item in audio] == [False, False, False, True]
