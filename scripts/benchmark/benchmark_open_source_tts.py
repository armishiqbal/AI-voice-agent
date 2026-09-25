"""CLI entry point for the local multilingual TTS evaluation runner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.evaluation.oss_tts_benchmark import main as run_benchmark

    run_benchmark()


if __name__ == "__main__":
    main()
