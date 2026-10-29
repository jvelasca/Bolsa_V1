"""Contrato HTTP de ``GET /api/database/maintenance`` — sin PostgreSQL real.

Se sustituye el caso de uso: lo que se prueba es el DTO (alias camelCase, estados) y que
la ruta responde 200 incluso cuando la BD está caída. Las consultas reales se cubren en
``test_database_maintenance_pg.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.api.v1.routes import database as database_route
from bolsa_application.database_maintenance import (
    BackupReport,
    CapacityReport,
    CapacityTable,
    CheckResult,
    ConnectionsReport,
    DatabaseMaintenanceReport,
    IntegrityReport,
    MaintenanceReport,
    SchemaReport,
)

pytestmark = pytest.mark.asyncio


def _report(*, connected: bool = True) -> DatabaseMaintenanceReport:
    if connected:
        status = "ok"
        schema = SchemaReport(
            status="ok",
            current_revision="060_provider_check_policy",
            expected_head="060_provider_check_policy",
            database_tables=89,
            expected_tables=87,
            allowlisted=("table custody_obligation: histórica",),
            detail="Esquema en head",
        )
        capacity = CapacityReport(
            status="ok",
            database_bytes=51_380_224,
            database_pretty="49.0 MB",
            tables=(
                CapacityTable(
                    table="ohlcv_bars",
                    label="Velas OHLCV",
                    rows=43_000,
                    size_bytes=20_000_000,
                    size_pretty="19.1 MB",
                ),
            ),
            detail="49.0 MB",
        )
    else:
        status = "error"
        schema = SchemaReport(
            status="unknown",
            current_revision=None,
            expected_head="060_provider_check_policy",
            database_tables=0,
            expected_tables=0,
            detail="PostgreSQL no responde",
        )
        capacity = CapacityReport(
            status="unknown",
            database_bytes=0,
            database_pretty="—",
            detail="PostgreSQL no responde",
        )

    return DatabaseMaintenanceReport(
        status=status,  # type: ignore[arg-type]
        generated_at=datetime(2026, 10, 29, 12, 0, tzinfo=UTC),
        connected=connected,
        message="PostgreSQL conectado" if connected else "PostgreSQL inaccesible",
        schema=schema,
        capacity=capacity,
        maintenance=MaintenanceReport(
            status="ok" if connected else "unknown",
            autovacuum_enabled=True if connected else None,
            naptime_seconds=60 if connected else None,
            dead_tuples_total=12,
            detail="autovacuum activo" if connected else "PostgreSQL no responde",
        ),
        connections=ConnectionsReport(
            status="ok" if connected else "unknown",
            total=4,
            active=1,
            idle=3,
            idle_in_transaction=0,
            max_connections=100,
            longest_transaction_seconds=None,
            detail="4 conexiones",
        ),
        backups=BackupReport(
            status="ok" if connected else "unknown",
            accessible=connected,
            directory="db-backups",
            count=3,
            retention=14,
            latest_name="bolsa_v1-20261029.sql.gz",
            latest_bytes=52_000_000,
            latest_created_at=datetime(2026, 10, 29, 3, 0, tzinfo=UTC),
            latest_schema="060_provider_check_policy",
            age_hours=9.0,
            stale=False,
            checksum_present=True,
            mirror_configured=False,
            detail="3 copias",
        ),
        integrity=IntegrityReport(
            status="ok" if connected else "unknown",
            checks=(
                CheckResult(
                    id="integrity.sync_settings_singleton",
                    label="Fila única de sync_settings",
                    status="ok" if connected else "unknown",
                    detail="Existe exactamente una fila",
                    value="default",
                ),
            ),
            detail="sin hallazgos",
        ),
        checks=(),
    )


class _UseCase:
    def __init__(self, report: DatabaseMaintenanceReport) -> None:
        self._report = report

    async def execute(self, **_kwargs: Any) -> DatabaseMaintenanceReport:
        return self._report


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    application = FastAPI()
    application.include_router(database_route.router, prefix="/api")

    async def _session() -> Any:
        yield None

    application.dependency_overrides[get_db_session] = _session
    monkeypatch.setattr(
        database_route,
        "get_database_maintenance_use_case",
        lambda _session: _UseCase(_report()),
    )
    return application


async def _get(app: FastAPI) -> dict[str, Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/database/maintenance")
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_returns_camel_case_payload(app: FastAPI) -> None:
    data = await _get(app)
    assert data["status"] == "ok"
    assert data["generatedAt"].startswith("2026-10-29T12:00:00")
    assert data["schema"]["currentRevision"] == "060_provider_check_policy"
    assert data["schema"]["missingTables"] == []
    assert data["capacity"]["databasePretty"] == "49.0 MB"
    assert data["capacity"]["tables"][0]["sizeBytes"] == 20_000_000
    assert data["maintenance"]["autovacuumEnabled"] is True
    assert data["connections"]["maxConnections"] == 100
    assert data["backups"]["latestName"] == "bolsa_v1-20261029.sql.gz"
    assert data["integrity"]["checks"][0]["status"] == "ok"


async def test_database_down_still_returns_200_with_unknown(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        database_route,
        "get_database_maintenance_use_case",
        lambda _session: _UseCase(_report(connected=False)),
    )
    data = await _get(app)
    assert data["connected"] is False
    assert data["status"] == "error"
    assert data["schema"]["status"] == "unknown"
    assert data["capacity"]["databasePretty"] == "—"
    assert data["maintenance"]["autovacuumEnabled"] is None
