"""Copia de BD bajo demanda: reglas de negocio sin PostgreSQL, Node ni disco real.

Lo que se protege: no hay dos copias a la vez, un fallo del runner **no** se convierte en
éxito, producción se rechaza antes de tocar nada y toda ejecución (buena o mala) deja una
entrada de auditoría. Los puertos se sustituyen por dobles; el script real se prueba en
``packages/py/infrastructure/tests/test_backup_runner.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from bolsa_application.database_backup import (
    BUSY,
    PRODUCTION_FORBIDDEN,
    RUNNER_ERROR,
    BackupRunResult,
    CreateDatabaseBackup,
    MaintenanceAuditEntry,
)
from bolsa_application.database_maintenance import BackupSnapshot

pytestmark = pytest.mark.asyncio

_BACKUP_DIR = Path("/tmp/db-backups")


class _Runner:
    def __init__(
        self,
        result: BackupRunResult | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._result = result or BackupRunResult(
            ok=True,
            file=str(_BACKUP_DIR / "bolsa_v1-20261029-150000-000.sql.gz"),
            bytes=12_345_678,
            sha256="a" * 64,
            schema="060_provider_check_policy",
            pruned=1,
            duration_ms=800,
        )
        self._raises = raises
        self.calls: list[Path] = []

    def create(self, directory: Path) -> BackupRunResult:
        self.calls.append(directory)
        if self._raises is not None:
            raise self._raises
        return self._result


class _Lock:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired = acquired
        self.acquire_calls = 0
        self.released = 0

    async def try_acquire(self) -> bool:
        self.acquire_calls += 1
        return self.acquired

    async def release(self) -> None:
        self.released += 1


class _Audit:
    def __init__(self, *, raises: bool = False) -> None:
        self.entries: list[MaintenanceAuditEntry] = []
        self._raises = raises

    def record(self, entry: MaintenanceAuditEntry) -> None:
        if self._raises:
            raise OSError("disco lleno")
        self.entries.append(entry)


class _Inventory:
    def __init__(self, snapshot: BackupSnapshot | None = None) -> None:
        self._snapshot = snapshot or BackupSnapshot(
            accessible=True,
            directory=str(_BACKUP_DIR),
            count=4,
            retention=14,
            latest_name="bolsa_v1-20261029-150000-000.sql.gz",
            latest_bytes=12_345_678,
            latest_created_at=datetime.now(UTC),
            latest_schema="060_provider_check_policy",
            checksum_present=True,
            mirror_configured=False,
            detail="4 copia(s)",
        )

    def snapshot(self) -> BackupSnapshot:
        return self._snapshot


def _use_case(
    *,
    runner: Any = None,
    lock: Any = None,
    audit: Any = None,
    inventory: Any = None,
    production: bool = False,
) -> CreateDatabaseBackup:
    return CreateDatabaseBackup(
        runner=runner or _Runner(),
        lock=lock or _Lock(),
        audit=audit or _Audit(),
        backup_inventory=inventory or _Inventory(),
        backup_directory=_BACKUP_DIR,
        expected_head="060_provider_check_policy",
        backup_stale_hours=24.0,
        production=production,
    )


async def test_creates_backup_and_reports_fresh_inventory() -> None:
    runner = _Runner()
    lock = _Lock()
    audit = _Audit()
    report = await _use_case(runner=runner, lock=lock, audit=audit).execute(actor="tester")

    assert report.ok is True
    assert report.busy is False
    assert report.refused is False
    assert runner.calls == [_BACKUP_DIR]
    assert lock.released == 1
    assert report.run.file is not None
    assert report.run.pruned == 1
    # Inventario recalculado (no el de antes de copiar) y sin duplicar la llamada.
    assert report.backups is not None
    assert report.backups.count == 4
    assert report.backups.latest_name == "bolsa_v1-20261029-150000-000.sql.gz"
    assert len(audit.entries) == 1
    assert audit.entries[0].ok is True
    assert audit.entries[0].actor == "tester"
    assert audit.entries[0].action == "database.backup"


async def test_busy_does_not_run_and_does_not_audit() -> None:
    runner = _Runner()
    lock = _Lock(acquired=False)
    audit = _Audit()
    report = await _use_case(runner=runner, lock=lock, audit=audit).execute(actor="tester")

    assert report.busy is True
    assert report.reason == BUSY
    assert report.run.error_code == BUSY
    assert report.run.ok is False
    assert runner.calls == []
    assert audit.entries == []
    assert lock.released == 0


async def test_production_is_refused_before_touching_lock_or_disk() -> None:
    runner = _Runner()
    lock = _Lock()
    audit = _Audit()
    report = await _use_case(
        runner=runner, lock=lock, audit=audit, production=True
    ).execute(actor="tester")

    assert report.refused is True
    assert report.reason == PRODUCTION_FORBIDDEN
    assert report.run.error_code == PRODUCTION_FORBIDDEN
    assert runner.calls == []
    assert lock.acquire_calls == 0
    assert audit.entries == []


async def test_failed_dump_is_not_success_and_is_audited() -> None:
    failure = BackupRunResult(ok=False, error_code="DUMP_FAILED", error="pg_dump falló")
    audit = _Audit()
    lock = _Lock()
    report = await _use_case(runner=_Runner(failure), lock=lock, audit=audit).execute()

    assert report.ok is False
    assert report.run.error_code == "DUMP_FAILED"
    assert report.run.file is None
    assert lock.released == 1
    assert len(audit.entries) == 1
    assert audit.entries[0].ok is False
    assert audit.entries[0].error_code == "DUMP_FAILED"


async def test_runner_exception_becomes_error_and_lock_is_released() -> None:
    audit = _Audit()
    lock = _Lock()
    report = await _use_case(
        runner=_Runner(raises=RuntimeError("boom")), lock=lock, audit=audit
    ).execute()

    assert report.run.ok is False
    assert report.run.error_code == RUNNER_ERROR
    assert "boom" in (report.run.error or "")
    assert lock.released == 1
    assert audit.entries[0].error_code == RUNNER_ERROR


async def test_audit_failure_does_not_hide_the_copy() -> None:
    report = await _use_case(audit=_Audit(raises=True)).execute()

    assert report.ok is True
    assert report.run.file is not None


async def test_actor_is_trimmed_and_bounded() -> None:
    audit = _Audit()
    await _use_case(audit=audit).execute(actor="  " + "x" * 500)
    assert audit.entries[0].actor.startswith("x")
    assert len(audit.entries[0].actor) == 120
