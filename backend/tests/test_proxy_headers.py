import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def test_forwarded_client_ip_is_trusted_only_from_configured_proxy_cidr() -> None:
    observed_clients: list[tuple[str, int] | None] = []

    async def capture_scope(scope, receive, send) -> None:
        observed_clients.append(scope.get("client"))

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        return None

    middleware = ProxyHeadersMiddleware(capture_scope, trusted_hosts="10.10.0.0/16")
    forwarded_headers = [(b"x-forwarded-for", b"203.0.113.8")]

    async def invoke(proxy_ip: str) -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/v1/voice/session",
            "raw_path": b"/v1/voice/session",
            "query_string": b"",
            "root_path": "",
            "headers": forwarded_headers,
            "client": (proxy_ip, 443),
            "server": ("127.0.0.1", 8000),
        }
        await middleware(scope, receive, send)

    asyncio.run(invoke("10.10.2.15"))
    asyncio.run(invoke("10.11.2.15"))

    assert observed_clients[0] == ("203.0.113.8", 0)
    assert observed_clients[1] == ("10.11.2.15", 443)


@pytest.mark.parametrize(
    ("proxy_address", "expected_client"),
    [
        ("10.10.2.15", "203.0.113.8"),
        ("10.11.2.15", "10.11.2.15"),
    ],
)
def test_voice_session_endpoint_uses_forwarded_ip_only_from_trusted_proxy(
    monkeypatch: pytest.MonkeyPatch, proxy_address: str, expected_client: str
) -> None:
    import app.api.app as api

    observed_clients: list[tuple[str, str]] = []

    class RecordingVoiceSessions:
        def issue(self, client_address: str, origin: str):
            observed_clients.append((client_address, origin))
            return "test-ticket", datetime.now(UTC) + timedelta(minutes=2)

    monkeypatch.setattr(api, "voice_sessions", RecordingVoiceSessions())

    async def configured_voice_options() -> dict[str, bool]:
        return {
            "standard_voice_ready": True,
            "openai_voice_ready": False,
            "multilingual_tts": True,
            "live_voice_pipeline_ready": True,
        }

    monkeypatch.setattr(api, "voice_option_readiness", configured_voice_options)
    proxied_app = ProxyHeadersMiddleware(api.app, trusted_hosts="10.10.0.0/16")

    with TestClient(proxied_app, client=(proxy_address, 443)) as client:
        response = client.post(
            "/v1/voice/session",
            headers={
                "origin": "http://localhost:5173",
                "x-forwarded-for": "203.0.113.8",
            },
        )

    assert response.status_code == 200
    assert observed_clients == [(expected_client, "http://localhost:5173")]
