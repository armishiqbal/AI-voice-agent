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
    grounded_reference_count = 0
    property_reference_count = 0
    hallucination_case_count = 0
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
        returned_matches = matches[:3]
        actual = [item.id for item in returned_matches]
        grounded_ids = [item.id for item in returned_matches if item.available]
        expected = case.expected_property_ids
        property_reference_count += len(actual)
        grounded_reference_count += len(grounded_ids)
        hallucination = any(property_id not in expected for property_id in actual)
        hallucination_case_count += int(hallucination)
        results.append(
            {
                "id": case.case_id,
                "expected": expected,
                "actual": actual,
                "grounded_property_ids": grounded_ids,
                "ungrounded_property_ids": [
                    property_id for property_id in actual if property_id not in grounded_ids
                ],
                "passed": actual == expected[:3],
                "property_id_hallucination": hallucination,
            }
        )
    passed = sum(1 for item in results if item["passed"])
    query_count = len(results)
    retrieval_accuracy = round(passed / query_count, 4) if query_count else 0.0
    return {
        "mode": "sql-grounded-fixtures",
        "pinecone_evidence": False,
        "metrics_scope": "SQL fixture property references; not free-form claim entailment",
        "total": query_count,
        "passed": passed,
        "accuracy": retrieval_accuracy,
        "retrieval_accuracy": retrieval_accuracy,
        "grounding_rate": (
            round(grounded_reference_count / property_reference_count, 4)
            if property_reference_count
            else 0.0
        ),
        "hallucination_rate": (
            round(hallucination_case_count / query_count, 4) if query_count else 0.0
        ),
        "denominators": {
            "queries": query_count,
            "returned_property_references": property_reference_count,
            "grounded_property_references": grounded_reference_count,
            "queries_with_unexpected_property_ids": hallucination_case_count,
        },
        "results": results,
    }
