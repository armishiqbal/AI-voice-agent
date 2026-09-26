from __future__ import annotations

from pathlib import Path
from typing import Any


class GoogleIntegrationError(RuntimeError):
    """Expected configuration or authorization failure for a Google adapter."""


def load_google_service(api: str, version: str, token_path: str, scopes: list[str]) -> Any:
    """Load pre-authorized OAuth credentials without starting an API web flow."""

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as error:
        raise GoogleIntegrationError(
            "Install the google optional extra to enable Workspace adapters"
        ) from error
    token_file = Path(token_path)
    if not token_file.exists():
        raise GoogleIntegrationError(f"OAuth token file does not exist: {token_path}")
    credentials = Credentials.from_authorized_user_file(str(token_file), scopes)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials.valid:
        raise GoogleIntegrationError("Google OAuth credentials are missing or invalid")
    return build(api, version, credentials=credentials, cache_discovery=False)


def authorize_google_token(client_secret_path: str, token_path: str, scopes: list[str]) -> None:
    """Run the one-time local OAuth consent flow; never call this from the API process."""

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as error:
        raise GoogleIntegrationError(
            "Install the google optional extra to authorize OAuth"
        ) from error
    secret_file = Path(client_secret_path)
    if not secret_file.exists():
        raise GoogleIntegrationError(
            f"Google client secret file does not exist: {client_secret_path}"
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), scopes)
    credentials = flow.run_local_server(port=0)
    output = Path(token_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(credentials.to_json(), encoding="utf-8")
    output.chmod(0o600)
