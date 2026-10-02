#!/usr/bin/env python3
"""Summarize privacy-minimized native-speaker voice acceptance CSV evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import NamedTuple


SCORES = (
    "turn_taking_score",
    "urduLish_naturalness_score",
    "grounding_score",
    "concision_score",
    "recovery_score",
    "action_safety_score",
    "handoff_quality_score",
)
REQUIRED = (
    "session_date_utc",
    "app_commit",
    "session_code",
    "speaker_code",
    "reviewer_code",
    "browser_version",
    "device_class",
    "microphone_type",
    "output_device_type",
    "capture_mode",
    "provider",
    "model",
    "scenario_id",
    "language",
    "participation_consent",
    "recording_consent",
    "transcript_received",
    "meaning_preserved",
    "first_audio_audible",
    "audio_cutoff_or_overlap",
    "speech_end_to_first_audible_ms",
    *SCORES,
    "blocking_issue",
    "failure_code",
    "redacted_notes",
)
YES_NO_FIELDS = (
    "participation_consent",
    "recording_consent",
    "transcript_received",
    "meaning_preserved",
    "first_audio_audible",
    "audio_cutoff_or_overlap",
    "blocking_issue",
)


class EvidenceError(Exception):
    """Raised when the evidence file cannot be interpreted safely."""


class Turn(NamedTuple):
    row_number: int
    values: dict[str, str]


def read_turns(path: Path) -> list[Turn]:
    try:
        stream = path.open(newline="", encoding="utf-8-sig")
    except OSError as exc:
        raise EvidenceError(f"cannot read {path}: {exc}") from exc

    with stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise EvidenceError("CSV is missing its header row")
        missing = sorted(set(REQUIRED) - set(reader.fieldnames))
        if missing:
            raise EvidenceError(f"CSV is missing required columns: {', '.join(missing)}")

        turns: list[Turn] = []
        for row_number, raw in enumerate(reader, start=2):
            if None in raw:
                raise EvidenceError(f"row {row_number}: more values than header columns")
            values = {key: (value or "").strip() for key, value in raw.items() if key}
            if not any(values.values()):
                continue
            for field in REQUIRED:
                if field not in values or not values[field] and field not in (
                    "speech_end_to_first_audible_ms",
                    "failure_code",
                    "redacted_notes",
                ):
                    raise EvidenceError(f"row {row_number}: {field} is required")
            for field in YES_NO_FIELDS:
                if values[field].lower() not in ("yes", "no"):
                    raise EvidenceError(f"row {row_number}: {field} must be yes or no")
            if values["participation_consent"].lower() != "yes":
                raise EvidenceError(f"row {row_number}: participation consent must be yes")
            if values["capture_mode"] != "physical_microphone":
                raise EvidenceError(
                    f"row {row_number}: capture_mode must be physical_microphone"
                )

            latency = values["speech_end_to_first_audible_ms"]
            if latency:
                try:
                    latency_value = float(latency)
                except ValueError as exc:
                    raise EvidenceError(f"row {row_number}: latency must be numeric") from exc
                if not math.isfinite(latency_value) or latency_value < 0:
                    raise EvidenceError(f"row {row_number}: latency must be finite and >= 0")
                if values["first_audio_audible"].lower() != "yes":
                    raise EvidenceError(
                        f"row {row_number}: latency requires first_audio_audible=yes"
                    )
            elif values["first_audio_audible"].lower() == "yes":
                raise EvidenceError(
                    f"row {row_number}: heard audio needs a measured latency"
                )

            for field in SCORES:
                try:
                    score = int(values[field])
                except ValueError as exc:
                    raise EvidenceError(
                        f"row {row_number}: {field} must be an integer from 1 to 5"
                    ) from exc
                if score < 1 or score > 5:
                    raise EvidenceError(f"row {row_number}: {field} must be from 1 to 5")
                values[field] = str(score)

            turns.append(Turn(row_number=row_number, values=values))
        return turns


def nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def summarize(turns: list[Turn], minimum_turns: int) -> dict[str, object]:
    latencies = [
        float(turn.values["speech_end_to_first_audible_ms"])
        for turn in turns
        if turn.values["speech_end_to_first_audible_ms"]
    ]
    failures = [
        turn
        for turn in turns
        if turn.values["failure_code"]
        or turn.values["transcript_received"].lower() != "yes"
        or turn.values["meaning_preserved"].lower() != "yes"
        or turn.values["first_audio_audible"].lower() != "yes"
        or turn.values["audio_cutoff_or_overlap"].lower() == "yes"
    ]
    blocking_count = sum(
        turn.values["blocking_issue"].lower() == "yes" for turn in turns
    )
    score_means = {
        field: round(statistics.mean(int(turn.values[field]) for turn in turns), 3)
        if turns
        else None
        for field in SCORES
    }
    p50 = statistics.median(latencies) if latencies else None
    p95 = nearest_rank(latencies, 0.95)
    enough_measurements = len(latencies) >= minimum_turns
    gates = {
        "minimum_physical_latency_samples": {
            "required": minimum_turns,
            "observed": len(latencies),
            "passed": enough_measurements,
        },
        "p95_below_2000_ms": {
            "observed_ms": round(p95, 1) if p95 is not None else None,
            "passed": p95 is not None and p95 < 2000,
        },
        "grounding_mean_at_least_4": {
            "observed": score_means["grounding_score"],
            "passed": score_means["grounding_score"] is not None
            and score_means["grounding_score"] >= 4,
        },
        "action_safety_mean_at_least_4": {
            "observed": score_means["action_safety_score"],
            "passed": score_means["action_safety_score"] is not None
            and score_means["action_safety_score"] >= 4,
        },
        "zero_blocking_issues": {"observed": blocking_count, "passed": blocking_count == 0},
    }
    return {
        "attempted_turns": len(turns),
        "measured_physical_latency_turns": len(latencies),
        "failed_turns": len(failures),
        "failure_rate": round(len(failures) / len(turns), 4) if turns else None,
        "latency_ms": {
            "p50": round(p50, 1) if p50 is not None else None,
            "p95_nearest_rank": round(p95, 1) if p95 is not None else None,
        },
        "score_means": score_means,
        "gates": gates,
        "acceptance_gates_passed": bool(turns)
        and all(gate["passed"] for gate in gates.values()),
        "interpretation": (
            "This minimum sample gate is not strong statistical confidence or production proof."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="completed acceptance CSV")
    parser.add_argument(
        "--minimum-turns",
        type=int,
        default=20,
        help="minimum measured physical turns for percentile eligibility (default: 20)",
    )
    args = parser.parse_args()
    if args.minimum_turns < 1:
        parser.error("--minimum-turns must be at least 1")
    try:
        turns = read_turns(args.csv_path)
    except EvidenceError as exc:
        print(f"Invalid evidence CSV: {exc}", file=sys.stderr)
        return 2
    if not turns:
        print("Invalid evidence CSV: no turn rows found", file=sys.stderr)
        return 2
    print(json.dumps(summarize(turns, args.minimum_turns), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
