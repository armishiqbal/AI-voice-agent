"""Evaluate multi-turn conversation memory against local fixtures."""

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.agents.graph import EstateAgent
    from app.domain.fixtures import demo_properties
    from app.evaluation.memory import load_memory_cases, run_memory_evaluation
    from app.services.appointments import PropertyRepository

    print(json.dumps(run_memory_evaluation(lambda: EstateAgent(PropertyRepository(demo_properties())), load_memory_cases(root / "evals" / "memory.json")), indent=2))
