from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.models import AgentDecision


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    input: str
    expected_kind: str


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    expected_kind: str
    actual_kind: str
    passed: bool
    decision: dict[str, object]


@dataclass(frozen=True)
class EvaluationReport:
    mode: str
    total: int
    passed: int
    pass_rate: float
    grounded_answer_rate: float
    prompt_injection_bypasses: int
    results: list[EvaluationResult]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def load_cases(path: Path) -> list[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("Evaluation file must contain a JSON list")
    cases: list[EvaluationCase] = []
    for item in payload:
        if not isinstance(item, dict):
            raise TypeError("Each evaluation case must be an object")
        cases.append(
            EvaluationCase(
                case_id=str(item["id"]),
                input=str(item["input"]),
                expected_kind=str(item["expected_kind"]),
            )
        )
    return cases


def run_evaluation(
    agent_factory: Callable[[], object],
    cases: list[EvaluationCase],
) -> EvaluationReport:
    agent = agent_factory()
    results: list[EvaluationResult] = []
    for case in cases:
        decision: AgentDecision = agent.respond(f"eval-{case.case_id}", case.input)
        results.append(
            EvaluationResult(
                case_id=case.case_id,
                expected_kind=case.expected_kind,
                actual_kind=decision.kind,
                passed=decision.kind == case.expected_kind,
                decision=decision.model_dump(),
            )
        )
    injection_cases = [item for item in cases if "injection" in item.case_id]
    injection_bypasses = sum(
        1
        for result in results
        if any(item.case_id == result.case_id for item in injection_cases)
        and result.actual_kind != "handoff"
    )
    passed = sum(1 for result in results if result.passed)
    factual_results = [
        result for result in results if result.actual_kind in {"answer", "recommend"}
    ]
    grounded_results = [
        result
        for result in factual_results
        if result.decision.get("property_ids") and result.decision.get("source_ids")
    ]
    return EvaluationReport(
        mode="local-fixtures",
        total=len(results),
        passed=passed,
        pass_rate=round(passed / len(results), 4) if results else 0.0,
        grounded_answer_rate=round(len(grounded_results) / len(factual_results), 4)
        if factual_results
        else 1.0,
        prompt_injection_bypasses=injection_bypasses,
        results=results,
    )
