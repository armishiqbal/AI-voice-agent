"""Print an evidence-scoped local release report."""

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.core.config import settings
    from app.evaluation.release import build_release_report

    print(json.dumps(build_release_report(root, settings), indent=2))
