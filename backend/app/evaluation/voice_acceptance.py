"""Acceptance checks for end-of-speech to spoken-answer voice runs."""

from collections.abc import Mapping, Sequence
from math import isfinite


def voice_acceptance_failures(
    turns: Sequence[Mapping[str, object]], *, target_ms: float
) -> list[str]:
    """Return failed voice gates; fast acknowledgement audio never counts as an answer."""

    if not turns:
        return ["no_turns"]

    failures: list[str] = []
    if any(
        turn.get("final_transcript_received") is not True
        or turn.get("transcription_recovery") is not False
        for turn in turns
    ):
        failures.append("final_transcript_missing")

    def has_final_audio(turn: Mapping[str, object]) -> bool:
        audio_bytes = turn.get("audio_bytes")
        return (
            turn.get("final_audio_received") is True
            and isinstance(audio_bytes, int)
            and not isinstance(audio_bytes, bool)
            and audio_bytes > 0
        )

    if any(not has_final_audio(turn) for turn in turns):
        failures.append("final_audio_missing")

    def substantive_latency(turn: Mapping[str, object]) -> float | None:
        value = turn.get("last_voice_to_substantive_audio_ms")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value < 0
        ):
            return None
        return float(value)

    if any(substantive_latency(turn) is None for turn in turns):
        failures.append("substantive_audio_missing")
    if any(
        latency is not None and latency >= target_ms
        for latency in (substantive_latency(turn) for turn in turns)
    ):
        failures.append("substantive_response_over_target")

    return failures
