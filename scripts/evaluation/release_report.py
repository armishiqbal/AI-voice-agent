"""Print an evidence-scoped local release report."""

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.core.config import settings
    from app.evaluation.release import build_release_report, read_runtime_readiness

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        help="Optionally query the running app's /readyz endpoint for runtime-specific configuration.",
    )
    args = parser.parse_args()
    runtime_readiness = read_runtime_readiness(args.api_url) if args.api_url else None

    print(json.dumps(build_release_report(root, settings, runtime_readiness), indent=2))
