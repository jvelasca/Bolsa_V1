"""Purges de mantenimiento: mismo criterio de rol que la copia bajo demanda.

La protección ``require_admin_when_auth_enabled`` se había aplicado solo a
``POST /database/backup``, aunque ``/database/orphans/purge`` y
``/database/closed-accounts/purge`` son MÁS destructivos (borran filas). Con la auth
activa, un token no-admin no puede ejecutarlos; sin auth el comportamiento no cambia (no
hay rol que exigir, y eso queda declarado en el helper).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.api.v1.routes import database as database_route

pytestmark = pytest.mark.asyncio


class _Session:
    async def commit(self) -> None:
        return None


class _PurgeOrphans:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, *, limit: int) -> dict[str, Any]:
        self.calls += 1
        return {"purgedIds": [], "skipped": [], "scanned": 0}


class _PurgeAccounts:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, *, limit: int) -> dict[str, Any]:
        self.calls += 1
        return {"purgedIds": [], "skipped": [], "scanned": 0}


def _app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    app_password: str,
) -> tuple[FastAPI, _PurgeOrphans, _PurgeAccounts]:
    application = FastAPI()
    application.include_router(database_route.router, prefix="/api")
    application.dependency_overrides[get_db_session] = lambda: _Session()

    orphans = _PurgeOrphans()
    accounts = _PurgeAccounts()
    monkeypatch.setattr(
        database_route, "get_purge_orphan_instruments_use_case", lambda _session: orphans
    )
    monkeypatch.setattr(
        database_route,
        "get_purge_closed_simulated_accounts_use_case",
        lambda _session: accounts,
    )

    class _Settings:
        pass

    _Settings.app_password = app_password  # type: ignore[attr-defined]
    monkeypatch.setattr(database_route, "get_settings", lambda: _Settings(), raising=False)
    monkeypatch.setattr("bolsa_api.auth.roles.get_settings", lambda: _Settings(), raising=True)
    return application, orphans, accounts


async def _post(app: FastAPI, path: str) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json={"limit": 10})


@pytest.mark.parametrize(
    ("path", "attribute"),
    [
        ("/api/database/orphans/purge", "orphans"),
        ("/api/database/closed-accounts/purge", "accounts"),
    ],
)
async def test_with_auth_enabled_a_non_admin_cannot_purge(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    attribute: str,
) -> None:
    app, orphans, accounts = _app(monkeypatch, app_password="secreto")

    response = await _post(app, path)

    assert response.status_code == 403
    use_case = orphans if attribute == "orphans" else accounts
    assert use_case.calls == 0, "el 403 ocurre ANTES de tocar la BD"


@pytest.mark.parametrize(
    "path",
    ["/api/database/orphans/purge", "/api/database/closed-accounts/purge"],
)
async def test_without_auth_the_route_behaves_as_before(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    app, _, _ = _app(monkeypatch, app_password="")

    response = await _post(app, path)

    assert response.status_code == 200, response.text
