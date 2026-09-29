"""Reproducible multi-turn reasoning evaluation against isolated local fixtures.

No STT/TTS, model provider, Calendar, email or production inventory is exercised.
"""
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, Field

from app.agents.graph import EstateAgent
from app.domain.fixtures import demo_properties
from app.services.appointments import PropertyRepository


class ConversationTurnCase(BaseModel):
    text: str
    expected_kind: str
    expected_reason: str | None = None
    state_equals: dict[str, object] = Field(default_factory=dict)
    require_available_properties: bool = False
    forbidden_text: list[str] = Field(default_factory=list)


class ConversationCase(BaseModel):
    id: str
    category: str
    turns: list[ConversationTurnCase] = Field(min_length=2)


def load_conversation_cases(path: Path) -> list[ConversationCase]:
    cases = [ConversationCase.model_validate(item) for item in json.loads(path.read_text())]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Conversation IDs must be unique")
    return cases


def run_conversation_evaluation(cases: list[ConversationCase]) -> dict[str, object]:
    results = []
    categories: dict[str, dict[str, int]] = {}
    durations: list[float] = []
    for case in cases:
        repository = PropertyRepository(demo_properties())
        agent = EstateAgent(repository)
        turns = []
        for number, turn in enumerate(case.turns, 1):
            started = perf_counter()
            decision = agent.respond(case.id, turn.text)
            durations.append((perf_counter() - started) * 1000)
            state = agent.states[case.id]
            checks = {"decision_kind": decision.kind == turn.expected_kind}
            if turn.expected_reason is not None:
                checks["decision_reason"] = decision.reason == turn.expected_reason
            for key, value in turn.state_equals.items():
                actual = getattr(state, key)
                checks[f"memory:{key}"] = actual == value
            if turn.require_available_properties:
                checks["available_properties"] = bool(decision.property_ids) and all(
                    repository.get_available(property_id) is not None
                    for property_id in decision.property_ids
                )
            for forbidden in turn.forbidden_text:
                checks[f"forbidden:{forbidden}"] = forbidden.casefold() not in decision.spoken_text.casefold()
            turns.append({"turn": number, "actual_kind": decision.kind, "checks": checks, "passed": all(checks.values())})
        passed = all(turn["passed"] for turn in turns)
        results.append({"id": case.id, "category": case.category, "passed": passed, "turns": turns})
        category = categories.setdefault(case.category, {"total": 0, "passed": 0})
        category["total"] += 1
        category["passed"] += int(passed)
    passed = sum(int(result["passed"]) for result in results)
    return {
        "mode": "local-fixture-multiturn-reasoning",
        "live_voice_evidence": False,
        "live_provider_evidence": False,
        "scope": "Deterministic agent routing, preference memory, availability and explicit guardrail expectations; no human naturalness or semantic hallucination score.",
        "total": len(results), "passed": passed,
        "turn_count": sum(len(case.turns) for case in cases),
        "conversation_success_rate": passed / len(results) if results else 0.0,
        "local_reasoning_average_ms": sum(durations) / len(durations) if durations else 0.0,
        "categories": categories, "results": results,
    }
