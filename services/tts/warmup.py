"""Run one authenticated smoke synthesis against the selected local TTS worker."""

from __future__ import annotations

import json
import os
import sys

import httpx


def main() -> int:
    engine = os.getenv("TTS_ENGINE", "parler").casefold()
    default_port = "8021" if engine == "parler" else "8022"
    base_url = os.getenv("TTS_SERVICE_URL", f"http://127.0.0.1:{default_port}").rstrip("/")
    token = os.getenv("TTS_SERVICE_TOKEN")
    if not token:
        print("TTS_SERVICE_TOKEN is required to warm up the TTS worker", file=sys.stderr)
        return 1
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = httpx.post(f"{base_url}/v1/warmup", headers=headers, timeout=900.0)
    except httpx.HTTPError as error:
        print(f"TTS worker is unreachable: {error}", file=sys.stderr)
        return 1
    if response.status_code != 200:
        print(f"TTS warmup failed (HTTP {response.status_code})", file=sys.stderr)
        return 1
    result = response.json()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
