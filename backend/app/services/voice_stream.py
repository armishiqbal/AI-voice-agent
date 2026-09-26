from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import aclosing

from app.domain.emotions import AcousticEmotionProfile
from app.domain.phonetics import apply_phonetic_transliteration
from app.integrations.tts.router import AudioChunk, TTSProvider, TTSProviderError

CONVERSATIONAL_STARTERS = (
    "ji bilkul sir,",
    "ji bilkul,",
    "ji zaroor,",
    "sahi hai,",
    "bilkul sir,",
    "bilkul,",
    "acha,",
    "walaikum assalam,",
    "assalam-o-alaikum,",
    "shukriya,",
    "theek hai,",
    "zaroor,",
)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.?!])\s+|\n+")


def split_conversational_clauses(text: str) -> list[str]:
    """Split response text into an early acknowledgment clause followed by natural speech sentences.

    An introductory acknowledgment can be synthesized before the remaining sentences.
    Actual first-audio latency depends on the provider and must be measured.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    clauses: list[str] = []
    lowered = cleaned.lower()

    # 1. Check for conversational discourse starters
    matched_starter = None
    for starter in CONVERSATIONAL_STARTERS:
        if lowered.startswith(starter):
            matched_starter = starter
            break

    if matched_starter:
        starter_len = len(matched_starter)
        intro = cleaned[:starter_len].strip()
        remainder = cleaned[starter_len:].strip()
        if intro:
            clauses.append(intro)
        cleaned = remainder

    if cleaned:
        # 2. Split remaining sentences
        parts = [part.strip() for part in SENTENCE_SPLIT_RE.split(cleaned) if part.strip()]
        for part in parts:
            # If a sentence is long (> 16 words) and has commas, subdivide at the first major pause
            words = part.split()
            if len(words) > 16 and "," in part:
                comma_index = part.find(",")
                first_half = part[: comma_index + 1].strip()
                second_half = part[comma_index + 1 :].strip()
                if first_half:
                    clauses.append(first_half)
                if second_half:
                    clauses.append(second_half)
            else:
                clauses.append(part)

    return clauses or [text.strip()]


async def _provider_stream(
    provider: TTSProvider, text: str, language: str, voice_id: str | None
) -> AsyncIterator[AudioChunk]:
    # Preserve the existing two-argument adapter contract when no override was
    # requested. Do not catch TypeError and retry a potentially side-effectful call.
    stream = None
    try:
        stream = (
            provider.synthesize_stream(text, language)
            if voice_id is None
            else provider.synthesize_stream(text, language, voice_id)
        )
        async for chunk in stream:
            yield chunk
    except TTSProviderError:
        raise
    except Exception as error:
        raise TTSProviderError("Speech synthesis failed") from error
    finally:
        close = getattr(stream, "aclose", None)
        if close is not None:
            await close()


async def _clause_worker(
    provider: TTSProvider,
    clause_text: str,
    language: str,
    voice_id: str | None,
    queue: asyncio.Queue[AudioChunk | Exception | None],
) -> None:
    try:
        async with aclosing(_provider_stream(provider, clause_text, language, voice_id)) as stream:
            async for chunk in stream:
                if chunk.audio:
                    await queue.put(chunk)
    except Exception as exc:  # noqa: BLE001
        await queue.put(exc)
    else:
        # No blocking queue write in finally: cancellation must not wait for a
        # consumer that has already stopped draining a bounded prefetch queue.
        await queue.put(None)


async def pipeline_synthesize_clauses(
    provider: TTSProvider,
    text: str,
    language: str = "ur-Latn",
    voice_id: str | None = None,
    emotion: AcousticEmotionProfile | None = None,
    enabled: bool = True,
) -> AsyncIterator[AudioChunk]:
    """Stream clauses in order with one bounded look-ahead synthesis task."""
    if not text.strip():
        return

    # Normalize Pakistani entities and abbreviations for clean TTS pronunciation
    normalized_text = apply_phonetic_transliteration(text)

    if not enabled:
        async with aclosing(
            _provider_stream(provider, normalized_text, language, voice_id)
        ) as stream:
            async for chunk in stream:
                yield chunk
        return

    clauses = split_conversational_clauses(normalized_text)
    if len(clauses) <= 1:
        single_text = clauses[0] if clauses else normalized_text
        if emotion and emotion.fish_audio_tag and getattr(provider, "name", "") == "fish-audio":
            single_text = f"{emotion.fish_audio_tag} {single_text}"
        async with aclosing(_provider_stream(provider, single_text, language, voice_id)) as stream:
            async for chunk in stream:
                yield chunk
        return

    # Multi-clause pipelining
    global_sequence = 0
    last_sample_rate = 24_000
    last_encoding = "pcm_s16le"

    clause_queues: list[asyncio.Queue[AudioChunk | Exception | None]] = [
        asyncio.Queue(maxsize=4) for _ in clauses
    ]
    tasks: list[asyncio.Task[None]] = []

    # Launch clause 0 and clause 1 immediately for early prefetching
    def launch_clause(index: int) -> None:
        if index < len(clauses) and index >= len(tasks):
            clause_str = clauses[index]
            if (
                index == 0
                and emotion
                and emotion.fish_audio_tag
                and getattr(provider, "name", "") == "fish-audio"
            ):
                clause_str = f"{emotion.fish_audio_tag} {clause_str}"
            task = asyncio.create_task(
                _clause_worker(provider, clause_str, language, voice_id, clause_queues[index])
            )
            tasks.append(task)

    try:
        launch_clause(0)
        if len(clauses) > 1:
            launch_clause(1)

        for index, queue in enumerate(clause_queues):
            # Prefetch subsequent clause
            if index + 1 < len(clauses):
                launch_clause(index + 1)

            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                last_sample_rate = item.sample_rate
                last_encoding = item.encoding
                yield AudioChunk(
                    sequence=global_sequence,
                    audio=item.audio,
                    language=item.language or language,
                    sample_rate=item.sample_rate,
                    encoding=item.encoding,
                    is_final=False,
                )
                global_sequence += 1

        if global_sequence > 0:
            yield AudioChunk(
                sequence=global_sequence,
                audio=b"",
                language="",
                sample_rate=last_sample_rate,
                encoding=last_encoding,
                is_final=True,
            )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
