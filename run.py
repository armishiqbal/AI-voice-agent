"""Local development launcher for the Awaaz Estate API."""

import os
import sys
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent / "backend"
    os.chdir(backend_dir)
    sys.path.insert(0, str(backend_dir))
    from app.core.config import settings

    uvicorn.run(
        "app.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=settings.app_env == "development",
        proxy_headers=True,
        forwarded_allow_ips=settings.trusted_proxy_ips,
        ws_max_size=settings.voice_max_ws_message_bytes,
        ws_max_queue=settings.voice_ws_protocol_queue,
    )
