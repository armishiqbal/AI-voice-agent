"""Evaluate deterministic booking, reschedule, and cancellation invariants."""

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from app.evaluation.appointments import run_appointment_evaluation

    print(json.dumps(run_appointment_evaluation(), indent=2))
