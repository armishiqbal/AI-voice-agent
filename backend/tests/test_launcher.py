from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import uvicorn

from app.core.config import settings


def test_run_launcher_applies_configured_trusted_proxy_allowlist(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def capture_run(application: str, **options: object) -> None:
        captured["application"] = application
        captured.update(options)

    monkeypatch.setattr(uvicorn, "run", capture_run)
    monkeypatch.setattr(os, "chdir", lambda _path: None)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(settings, "trusted_proxy_ips", "10.20.0.0/16,192.0.2.17")

    project_root = Path(__file__).resolve().parents[2]
    runpy.run_path(str(project_root / "run.py"), run_name="__main__")

    assert captured["application"] == "app.main:app"
    assert captured["proxy_headers"] is True
    assert captured["forwarded_allow_ips"] == "10.20.0.0/16,192.0.2.17"
