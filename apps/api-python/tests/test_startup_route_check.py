"""Startup route check must not build OpenAPI."""

from __future__ import annotations

from fastapi import FastAPI

from bolsa_api.api.v1.router import api_v1_router
from bolsa_api.main import _route_path_exists


def test_route_path_exists_finds_alerts_without_openapi(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api")

    def _boom() -> dict:
        raise AssertionError("openapi() must not run during route check")

    monkeypatch.setattr(app, "openapi", _boom)
    assert _route_path_exists(app, "/api/alerts") is True
    assert _route_path_exists(app, "/api/does-not-exist") is False
