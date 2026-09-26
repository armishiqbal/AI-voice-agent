"""Run isolated multi-turn fixture evaluation; optional --output saves JSON."""
import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.evaluation.conversations import (
        load_conversation_cases,
        run_conversation_evaluation,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_conversation_evaluation(load_conversation_cases(root / "evals" / "multiturn_conversations.json"))
    content = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n")
    print(content)
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
