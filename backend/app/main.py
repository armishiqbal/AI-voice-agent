"""Compatibility ASGI entrypoint; the application lives in app.api.app."""

from app.api.app import app

__all__ = ["app"]
