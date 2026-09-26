from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.conversations import (
    ConversationCase,
    load_conversation_cases,
    run_conversation_evaluation,
)

ROOT = Path(__file__).resolve().parents[2]


def test_multiturn_evaluation_covers_all_capstone_categories():
    cases = load_conversation_cases(ROOT / "evals" / "multiturn_conversations.json")
    report = run_conversation_evaluation(cases)
    assert len(cases) >= 40
    assert all(len(case.turns) >= 2 for case in cases)
    assert set(report["categories"]) == {
        "buyer", "seller", "investor", "rental", "appointment", "cancellation",
        "rescheduling", "off_topic", "prompt_injection", "angry_customer", "silent_caller",
    }
    assert report["passed"] == report["total"]
    assert report["live_voice_evidence"] is False
    assert report["live_provider_evidence"] is False


def test_multiturn_evaluation_reports_failed_expectation():
    case = ConversationCase.model_validate({"id": "bad-expectation", "category": "buyer", "turns": [
        {"text": "Hello", "expected_kind": "book"},
        {"text": "Hello", "expected_kind": "ask_clarification", "state_equals": {"budget": 1}},
    ]})
    report = run_conversation_evaluation([case])
    assert report["passed"] == 0
    assert report["results"][0]["turns"][1]["checks"]["memory:budget"] is False


def test_single_turn_is_not_counted_as_a_conversation():
    with pytest.raises(ValidationError):
        ConversationCase.model_validate({"id": "single", "category": "buyer", "turns": [{"text": "Hi", "expected_kind": "ask_clarification"}]})
