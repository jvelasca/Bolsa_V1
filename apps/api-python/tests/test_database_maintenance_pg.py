"""Diagnóstico de BD contra PostgreSQL real (solo lectura).

Verifica que las consultas del informe funcionan sobre el catálogo real y que el
resultado es honesto: head alineado, tamaños > 0, autovacuum declarado, integridad
medida. No escribe nada y no necesita transacción propia.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from bolsa_application.database_maintenance import GetDatabaseMaintenance
from bolsa_infrastructure.database.backup_inventory import BackupInventoryAdapter
from bolsa_infrastructure.database.schema_contract import SchemaContractAdapter
from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED_ENV = "DATABASE_MAINTENANCE_PG_REQUIRED"
_EXPECTED_HEAD = "061_profile_delete_restrict"


class _DeadSession:
    """Sesión que falla al ejecutar: simula PostgreSQL caído sin abrir conexión."""

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        raise ConnectionError("connection refused")


@pytest.mark.asyncio
async def test_report_reads_the_real_catalog() -> None:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="diagnóstico de BD")
        return

    try:
        async with factory() as session:
            report = await GetDatabaseMaintenance(
                session,
                schema_contract=SchemaContractAdapter(),
                backup_inventory=BackupInventoryAdapter(),
                expected_head=_EXPECTED_HEAD,
            ).execute()
    finally:
        await engine.dispose()

    assert report.connected is True
    assert report.schema.current_revision == _EXPECTED_HEAD
    assert report.schema.status == "ok", report.schema.detail
    assert report.schema.missing_tables == ()
    assert report.schema.missing_columns == ()
    assert report.schema.missing_constraints == ()
    # ``alembic_version`` y ``custody_obligation`` son divergencias declaradas.
    assert report.schema.unexpected_tables == ()
    assert report.schema.allowlisted

    assert report.capacity.database_bytes > 0
    assert report.capacity.tables
    assert report.capacity.tables[0].size_bytes > 0

    assert report.maintenance.autovacuum_enabled is True
    assert report.maintenance.dead_tuples_total >= 0

    assert report.connections.total >= 1
    assert report.connections.max_connections is not None

    assert report.integrity.status in {"ok", "warning"}
    assert any(
        check.id == "integrity.sync_settings_singleton"
        for check in report.integrity.checks
    )
    assert report.checks


@pytest.mark.asyncio
async def test_disconnected_database_reports_unknown_not_zero() -> None:
    """Sin BD no se afirma salud: ``connected=False`` y todo en ``unknown``/``error``."""
    report = await GetDatabaseMaintenance(
        _DeadSession(),  # type: ignore[arg-type]
        schema_contract=SchemaContractAdapter(),
        backup_inventory=BackupInventoryAdapter(),
        expected_head=_EXPECTED_HEAD,
    ).execute()

    assert report.connected is False
    assert report.status == "error"
    assert report.schema.status == "unknown"
    assert report.capacity.status == "unknown"
    assert report.capacity.database_pretty == "—"
    assert report.maintenance.status == "unknown"
    assert report.connections.status == "unknown"
    assert report.backups.status == "unknown"
    assert report.integrity.status == "unknown"
    assert report.schema.current_revision is None
