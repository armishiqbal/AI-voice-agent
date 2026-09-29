from pathlib import Path

from app.evaluation.rag import load_rag_cases, run_sql_baseline
from app.services.appointments import PropertyRepository


def test_rag_fixture_set_has_twenty_cases_and_is_explicitly_local() -> None:
    root = Path(__file__).resolve().parents[2]
    report = run_sql_baseline(
        PropertyRepository(), load_rag_cases(root / "evals" / "rag_questions.json")
    )
    assert report["total"] == 20
    assert report["pinecone_evidence"] is False
    assert report["retrieval_accuracy"] == report["accuracy"] == 1.0
    assert report["grounding_rate"] == 1.0
    assert report["hallucination_rate"] == 0.0
    assert report["denominators"] == {
        "queries": 20,
        "returned_property_references": 37,
        "grounded_property_references": 37,
        "queries_with_unexpected_property_ids": 0,
    }
    assert "not free-form claim entailment" in report["metrics_scope"]
