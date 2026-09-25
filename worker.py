"""Run the appointment outbox worker with ``python worker.py``."""

import os
import sys
from pathlib import Path


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent / "backend"
    os.chdir(backend_dir)
    sys.path.insert(0, str(backend_dir))
    from app.workers.runner import main

    main()
