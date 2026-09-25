"""Run one isolated local TTS engine process (Parler or Chatterbox)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    engine = os.getenv("TTS_ENGINE", "parler").casefold()
    host = os.getenv("TTS_SERVICE_HOST", "127.0.0.1")
    if not os.getenv("TTS_SERVICE_TOKEN"):
        raise SystemExit("TTS_SERVICE_TOKEN is required to start the TTS worker")
    if engine not in {"parler", "chatterbox"}:
        raise SystemExit("TTS_ENGINE must be parler or chatterbox")
    uvicorn.run(
        "services.tts.app:app",
        host=host,
        port=int(os.getenv("TTS_SERVICE_PORT", "8021")),
        workers=1,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
