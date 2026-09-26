from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.domain.models import PropertyQuery


@dataclass(frozen=True)
class RAGCase:
    case_id: str
    query: str
    city: str | None
    purpose: str | None
    max_budget_pkr: int | None
    expected_property_ids: list[str]


def load_rag_cases(path: Path) -> list[RAGCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        RAGCase(
            str(item["id"]),
            str(item["query"]),
            item.get("city"),
            item.get("purpose"),
            item.get("max_budget_pkr"),
            list(item["expected_property_ids"]),
        )
        for item in payload
    ]


def run_sql_baseline(repository: object, cases: list[RAGCase]) -> dict[str, object]:
    results = []
    for case in cases:
        matches = [
            item
            for item in repository.list(
                PropertyQuery(
                    city=case.city, purpose=case.purpose, max_budget_pkr=case.max_budget_pkr
                )
            )
            if item.available
        ]
        actual = [item.id for item in matches[:3]]
        expected = case.expected_property_ids
        results.append(
            {
                "id": case.case_id,
                "expected": expected,
                "actual": actual,
                "passed": actual == expected[:3],
            }
        )
    passed = sum(1 for item in results if item["passed"])
    hallucinations = sum(
        1
        for item in results
        if any(property_id not in item["expected"] for property_id in item["actual"])
    )
    return {
        "mode": "sql-grounded-fixtures",
        "pinecone_evidence": False,
        "total": len(results),
        "passed": passed,
        "accuracy": round(passed / len(results), 4) if results else 0.0,
        "hallucination_rate": round(hallucinations / len(results), 4) if results else 0.0,
        "results": results,
    }
