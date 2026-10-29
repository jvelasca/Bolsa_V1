"""Contrato HTTP de ``POST /api/database/backup`` — sin PostgreSQL, Node ni disco real.

Lo que se prueba es la frontera: qué códigos devuelve (422 sin la palabra, 409 si ya hay
una copia, 403 en producción, 503 si falta el entorno, 500 si el volcado falló) y que el
payload use alias camelCase. La copia real la cubre ``test_backup_runner.py`` y la
verificación manual con el stack arriba.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bolsa_api.api.dependencies import get_create_database_backup_use_case
from bolsa_api.api.v1.routes import database as database_route
from bolsa_application.database_backup import BackupRunReport, BackupRunResult
from bolsa_application.database_maintenance import BackupReport

pytestmark = pytest.mark.asyncio


def _backups() -> BackupReport:
    return BackupReport(
        status="ok",
        accessible=True,
        directory="db-backups",
        count=6,
        retention=14,
        latest_name="bolsa_v1-20261029-150000-000.sql.gz",
        latest_bytes=52_000_000,
        latest_created_at=datetime(2026, 10, 29, 15, 0, tzinfo=UTC),
        latest_schema="060_provider_check_policy",
        age_hours=0.1,
        stale=False,
        checksum_present=True,
        mirror_configured=False,
        detail="6 copia(s)",
    )


def _success() -> BackupRunReport:
    return BackupRunReport(
        run=BackupRunResult(
            ok=True,
            file="/repo/db-backups/bolsa_v1-20261029-150000-000.sql.gz",
            bytes=52_000_000,
            sha256="c" * 64,
            schema="060_provider_check_policy",
            pruned=1,
            duration_ms=1234,
        ),
        backups=_backups(),
    )


def _busy() -> BackupRunReport:
    return BackupRunReport(
        run=BackupRunResult(ok=False, error_code="BUSY", error="Ya hay una copia en curso"),
        backups=None,
        busy=True,
        reason="BUSY",
    )


def _refused() -> BackupRunReport:
    return BackupRunReport(
        run=BackupRunResult(
            ok=False,
            error_code="PRODUCTION_FORBIDDEN",
            error="La copia local bajo demanda está deshabilitada en producción",
        ),
        backups=None,
        refused=True,
        reason="PRODUCTION_FORBIDDEN",
    )


def _failed(code: str) -> BackupRunReport:
    return BackupRunReport(
        run=BackupRunResult(ok=False, error_code=code, error=f"fallo {code}"),
        backups=None,
    )


class _UseCase:
    def __init__(self, report: BackupRunReport) -> None:
        self._report = report
        self.actor: str | None = None

    async def execute(self, *, actor: str = "system") -> BackupRunReport:
        self.actor = actor
        return self._report


def _app(
    monkeypatch: pytest.MonkeyPatch,
    report: BackupRunReport,
    *,
    app_password: str = "",
) -> tuple[FastAPI, _UseCase]:
    application = FastAPI()
    application.include_router(database_route.router, prefix="/api")
    use_case = _UseCase(report)
    application.dependency_overrides[get_create_database_backup_use_case] = lambda: use_case

    class _Settings:
        pass

    _Settings.app_password = app_password  # type: ignore[attr-defined]

    monkeypatch.setattr(database_route, "get_settings", lambda: _Settings(), raising=False)
    monkeypatch.setattr(
        "bolsa_api.auth.roles.get_settings", lambda: _Settings(), raising=True
    )
    return application, use_case


async def _post(app: FastAPI, body: dict[str, Any]) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/database/backup", json=body)


async def test_creates_backup_with_camel_case_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, use_case = _app(monkeypatch, _success())
    response = await _post(app, {"confirm": "COPIAR"})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["run"]["ok"] is True
    assert data["run"]["durationMs"] == 1234
    assert data["run"]["schemaRevision"] == "060_provider_check_policy"
    assert data["run"]["errorCode"] is None
    assert data["backups"]["latestName"] == "bolsa_v1-20261029-150000-000.sql.gz"
    assert data["backups"]["checksumPresent"] is True
    # El actor sale del principal del request (en tests, el owner de settings).
    assert use_case.actor


async def test_confirmation_is_case_insensitive_but_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _app(monkeypatch, _success())
    subtle = await _post(app, {"confirm": " copiar "})
    assert subtle.status_code == 200

    rejected = await _post(app, {"confirm": "sí"})
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "confirmation_required"


async def test_busy_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _app(monkeypatch, _busy())
    response = await _post(app, {"confirm": "COPIAR"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "backup_in_progress"


async def test_production_returns_403(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _app(monkeypatch, _refused())
    response = await _post(app, {"confirm": "COPIAR"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PRODUCTION_FORBIDDEN"


@pytest.mark.parametrize("code", ["NODE_MISSING", "SCRIPT_MISSING", "DIR_ERROR"])
async def test_missing_environment_returns_503(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    app, _ = _app(monkeypatch, _failed(code))
    response = await _post(app, {"confirm": "COPIAR"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize("code", ["DUMP_FAILED", "TIMEOUT", "OUTPUT_MISSING"])
async def test_dump_failure_returns_500(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    app, _ = _app(monkeypatch, _failed(code))
    response = await _post(app, {"confirm": "COPIAR"})

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == code


async def test_auth_enabled_requires_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _app(monkeypatch, _success(), app_password="secreto")
    response = await _post(app, {"confirm": "COPIAR"})

    assert response.status_code == 403


async def test_admin_helper_is_open_without_auth_and_strict_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException

    from bolsa_api.auth.roles import require_admin_when_auth_enabled

    request = SimpleNamespace(state=SimpleNamespace(auth_role=None))

    class _NoAuth:
        app_password = ""

    monkeypatch.setattr("bolsa_api.auth.roles.get_settings", lambda: _NoAuth())
    require_admin_when_auth_enabled(request)  # local sin auth: no bloquea

    class _Auth:
        app_password = "secreto"

    monkeypatch.setattr("bolsa_api.auth.roles.get_settings", lambda: _Auth())
    with pytest.raises(HTTPException) as raised:
        require_admin_when_auth_enabled(request)
    assert raised.value.status_code == 403

    request.state.auth_role = "admin"
    require_admin_when_auth_enabled(request)  # admin: pasa
