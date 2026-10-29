"""``NodeBackupRunner`` sin volcar una BD: se sustituye ``subprocess.run``.

Lo que se comprueba es el contrato con el script del repo y la honestidad del resultado:
``--dir`` apunta al directorio que lee el inventario, argv es una lista (sin shell), un
código de salida distinto de cero se publica como fallo con su ``stderr`` y el fichero
creado se detecta por diferencia de listado, no adivinando su nombre.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_infrastructure.database.backup_runner import (
    JsonlMaintenanceAudit,
    NodeBackupRunner,
    PostgresMaintenanceLock,
    backup_script_path,
)

_SHA = "b" * 64


def _write(path: Path, content: str = "x") -> None:
    path.write_text(content, encoding="utf-8")


def _fake_run_factory(
    directory: Path,
    *,
    returncode: int = 0,
    stderr: str = "",
    file_name: str = "bolsa_v1-20261029-150000-000.sql.gz",
    create: bool = True,
    captured: dict[str, Any] | None = None,
):
    def _run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        if captured is not None:
            captured["command"] = command
            captured["kwargs"] = kwargs
        if create:
            target = directory / file_name
            _write(target)
            _write(directory / f"{file_name}.sha256", f"{_SHA}  {file_name}\n")
            manifest = directory / "backups-manifest.json"
            manifest.write_text(
                f'[{{"file": "{file_name}", "schema": "060_provider_check_policy"}}]',
                encoding="utf-8",
            )
        return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)

    return _run


def test_reports_created_file_checksum_and_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        subprocess, "run", _fake_run_factory(tmp_path, captured=captured)
    )
    runner = NodeBackupRunner(node_executable="node", script=backup_script_path())

    result = runner.create(tmp_path)

    assert result.ok is True
    assert result.file is not None
    assert Path(result.file).name == "bolsa_v1-20261029-150000-000.sql.gz"
    assert result.bytes is not None and result.bytes > 0
    assert result.sha256 == _SHA
    assert result.schema == "060_provider_check_policy"
    # argv constante y `--dir` con el directorio que lee la API: nada de depender del cwd.
    assert captured["command"][1] == str(backup_script_path())
    assert captured["command"][2] == "--dir"
    assert captured["command"][3] == str(tmp_path)
    assert captured["kwargs"]["shell"] is False
    assert isinstance(captured["command"], list)


def test_pruned_counts_retention_removals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = tmp_path / "bolsa_v1-20261001-000000-000.sql.gz"
    _write(old)

    def _run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        # El script poda el más viejo y escribe el nuevo, como db-dump.mjs.
        old.unlink()
        _write(tmp_path / "bolsa_v1-20261029-150000-000.sql.gz")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    result = NodeBackupRunner(node_executable="node", script=backup_script_path()).create(
        tmp_path
    )

    assert result.ok is True
    assert result.pruned == 1


def test_missing_node_is_declared_not_simulated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "bolsa_infrastructure.database.backup_runner.shutil.which", lambda _name: None
    )
    result = NodeBackupRunner(script=backup_script_path()).create(tmp_path)

    assert result.ok is False
    assert result.error_code == "NODE_MISSING"


def test_missing_script_is_reported(tmp_path: Path) -> None:
    runner = NodeBackupRunner(node_executable="node", script=tmp_path / "no-existe.mjs")
    result = runner.create(tmp_path)
    assert result.ok is False
    assert result.error_code == "SCRIPT_MISSING"


def test_non_zero_exit_is_failure_with_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run_factory(tmp_path, returncode=1, stderr="pg_dump: error: conexión rechazada"),
    )
    result = NodeBackupRunner(node_executable="node", script=backup_script_path()).create(
        tmp_path
    )

    assert result.ok is False
    assert result.error_code == "DUMP_FAILED"
    assert "conexión rechazada" in (result.error or "")


def test_zero_exit_without_file_is_not_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess, "run", _fake_run_factory(tmp_path, create=False, stderr="nada")
    )
    result = NodeBackupRunner(node_executable="node", script=backup_script_path()).create(
        tmp_path
    )

    assert result.ok is False
    assert result.error_code == "OUTPUT_MISSING"


def test_timeout_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(command: list[str], **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(subprocess, "run", _raise)
    result = NodeBackupRunner(node_executable="node", script=backup_script_path()).create(
        tmp_path
    )

    assert result.ok is False
    assert result.error_code == "TIMEOUT"


def test_audit_appends_jsonl(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from bolsa_application.database_backup import MaintenanceAuditEntry

    audit = JsonlMaintenanceAudit(tmp_path)
    audit.record(
        MaintenanceAuditEntry(
            action="database.backup",
            actor="tester",
            ok=True,
            at=datetime(2026, 10, 29, 14, 0, tzinfo=UTC),
            file=str(tmp_path / "bolsa_v1-x.sql.gz"),
            bytes=1234,
            duration_ms=42,
        )
    )

    entries = list(audit.read_all())
    assert len(entries) == 1
    assert entries[0]["action"] == "database.backup"
    assert entries[0]["actor"] == "tester"
    assert entries[0]["bytes"] == 1234
    assert entries[0]["ok"] is True


class _FakeConnection:
    def __init__(self, available: bool) -> None:
        self._available = available
        self.closed = False
        self.unlocked = False

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(scalar=lambda: self._available)

    async def close(self) -> None:
        self.closed = True


class _FakeEngine:
    def __init__(self, available: bool) -> None:
        self.connection = _FakeConnection(available)

    def connect(self) -> Any:
        # ``AsyncEngine.connect()`` se espera con ``await`` en el adaptador.
        async def _get() -> Any:
            return self.connection

        return _get()


@pytest.mark.asyncio
async def test_lock_reports_busy_without_holding_connection() -> None:
    engine = _FakeEngine(available=False)
    lock = PostgresMaintenanceLock(engine)  # type: ignore[arg-type]

    assert await lock.try_acquire() is False
    assert engine.connection.closed is True
    await lock.release()  # sin lock: no-op, no debe lanzar
