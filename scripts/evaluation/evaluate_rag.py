"""Run the local SQL-grounded retrieval baseline; it is not live Pinecone evidence."""

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.domain.fixtures import demo_properties
    from app.evaluation.rag import load_rag_cases, run_sql_baseline
    from app.services.appointments import PropertyRepository

    print(json.dumps(run_sql_baseline(PropertyRepository(demo_properties()), load_rag_cases(root / "evals" / "rag_questions.json")), indent=2))
