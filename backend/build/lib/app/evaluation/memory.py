from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from app.domain.models import AgentDecision


def load_memory_cases(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("Memory evaluation file must contain a JSON list")
    return payload


def run_memory_evaluation(
    agent_factory: Callable[[], object], cases: list[dict[str, object]]
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for case in cases:
        agent = agent_factory()
        conversation_id = f"memory-eval-{case['id']}"
        turns = case["turns"]
        assert isinstance(turns, list)
        actual_kinds: list[str] = []
        for turn in turns:
            assert isinstance(turn, dict)
            decision: AgentDecision = agent.respond(conversation_id, str(turn["input"]))
            actual_kinds.append(decision.kind)
        state = agent.states[conversation_id]
        expected_kinds = [str(turn["expected_kind"]) for turn in turns]
        expected_state = case.get("expected_state", {})
        state_matches = all(
            getattr(state, key, None) == value for key, value in dict(expected_state).items()
        )
        passed = actual_kinds == expected_kinds and state_matches
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "actual_kinds": actual_kinds,
                "expected_kinds": expected_kinds,
                "state_matches": state_matches,
            }
        )
    passed = sum(1 for result in results if result["passed"])
    return {
        "mode": "local-memory-fixtures",
        "total": len(results),
        "passed": passed,
        "accuracy": round(passed / len(results), 4) if results else 0.0,
        "results": results,
    }
