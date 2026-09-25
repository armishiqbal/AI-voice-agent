"""Create a local Google OAuth token for Calendar and Gmail integrations."""

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    backend_dir = root / "backend"
    sys.path.insert(0, str(backend_dir))
    from app.core.config import settings
    from app.integrations.google_auth import authorize_google_token

    client_secret_path = settings.google_client_secret_path
    token_path = settings.google_token_path
    if not client_secret_path or not token_path:
        raise SystemExit("Set GOOGLE_CLIENT_SECRET_PATH and GOOGLE_TOKEN_PATH in .env first")
    authorize_google_token(
        client_secret_path,
        token_path,
        [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.send",
        ],
    )
    print(f"Saved OAuth token to {os.path.abspath(token_path)}")
