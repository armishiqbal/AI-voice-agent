"""Run the deterministic fixture evaluation with ``python scripts/evaluation/evaluate.py``."""

import json
from pathlib import Path

if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parents[2]
    backend_dir = root / "backend"
    sys.path.insert(0, str(backend_dir))
    from app.agents.graph import EstateAgent
    from app.domain.fixtures import demo_properties
    from app.evaluation.runner import load_cases, run_evaluation
    from app.services.appointments import PropertyRepository

    report = run_evaluation(
        lambda: EstateAgent(PropertyRepository(demo_properties())),
        load_cases(root / "evals" / "conversations.json"),
    )
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
