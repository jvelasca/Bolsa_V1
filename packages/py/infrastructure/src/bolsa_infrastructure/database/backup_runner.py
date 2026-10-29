"""Adaptadores de la copia de BD bajo demanda: ejecutor, cerrojo y auditoría.

Tres piezas de infraestructura que implementan los puertos de
``bolsa_application.database_backup``:

* ``NodeBackupRunner`` — ejecuta el script canónico del repo
  (``scripts/db-dump.mjs``) en lugar de reimplementar ``pg_dump`` en Python. Así la copia
  que se lanza desde la UI es **la misma** que la de ``pnpm db:dump``: mismo sello, mismo
  ``O_EXCL``, mismo sidecar ``.sha256``, mismo manifest y misma retención. Duplicar esa
  lógica sería crear una segunda verdad sobre los backups.
* ``PostgresMaintenanceLock`` — ``pg_try_advisory_lock`` sobre una conexión dedicada. La
  exclusión es global (API workers + cualquier proceso que use la misma clave), no solo
  dentro del proceso; si la conexión cae, PostgreSQL libera el cerrojo solo.
* ``JsonlMaintenanceAudit`` — append-only en ``logs/agent/db-maintenance.jsonl``. Es el
  registro de quién lanzó una copia y cómo terminó; no sustituye al manifest de backups.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from bolsa_application.database_backup import (
    BackupRunResult,
    MaintenanceAuditEntry,
)
from bolsa_infrastructure.database.backup_inventory import resolve_repo_root

__all__ = [
    "DEFAULT_MAINTENANCE_LOCK_KEY",
    "JsonlMaintenanceAudit",
    "NodeBackupRunner",
    "PostgresMaintenanceLock",
    "backup_script_path",
    "agent_log_directory",
]

#: Clave del advisory lock de mantenimiento. Distinta de ``BOOTSTRAP_ADVISORY_LOCK_KEY``
#: (774_104_253): migrar y copiar son trabajos independientes que pueden coincidir.
DEFAULT_MAINTENANCE_LOCK_KEY = 774_104_254

_SCRIPT_RELATIVE = Path("scripts") / "db-dump.mjs"
_DUMP_TIMEOUT_SECONDS = 600
_MAX_DETAIL = 1200


def backup_script_path() -> Path:
    """Ruta absoluta del script de volcado del repo."""
    return resolve_repo_root() / _SCRIPT_RELATIVE


def agent_log_directory() -> Path:
    return resolve_repo_root() / "logs" / "agent"


def _is_backup_file(name: str) -> bool:
    return name.startswith("bolsa_v1-") and (name.endswith(".sql") or name.endswith(".sql.gz"))


def _list_backup_names(directory: Path) -> set[str]:
    try:
        return {entry.name for entry in directory.iterdir() if entry.is_file() and _is_backup_file(entry.name)}
    except OSError:
        return set()


def _tail(raw: str | None, limit: int = _MAX_DETAIL) -> str:
    """Últimas líneas del stderr: el error útil de ``pg_dump`` suele estar al final."""
    if not raw:
        return ""
    cleaned = raw.strip()
    return cleaned[-limit:] if len(cleaned) > limit else cleaned


class NodeBackupRunner:
    """Ejecuta ``node scripts/db-dump.mjs --dir <dir>`` con argv constante (sin shell)."""

    def __init__(
        self,
        *,
        node_executable: str | None = None,
        script: Path | None = None,
        timeout_seconds: int = _DUMP_TIMEOUT_SECONDS,
        repo_root: Path | None = None,
    ) -> None:
        self._node = node_executable
        self._script = script
        self._timeout = timeout_seconds
        self._repo_root = repo_root

    def create(self, directory: Path) -> BackupRunResult:
        started = time.monotonic()
        node = self._node or shutil.which("node")
        if not node:
            return self._failure(
                "NODE_MISSING",
                "No hay ejecutable de Node en el PATH; la copia necesita node para el script del repo",
                started,
            )
        script = self._script or backup_script_path()
        if not script.is_file():
            return self._failure(
                "SCRIPT_MISSING",
                f"No se encontró el script de copias: {script}",
                started,
            )

        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return self._failure(
                "DIR_ERROR",
                f"No se pudo preparar el directorio de copias ({exc.__class__.__name__})",
                started,
            )

        before = _list_backup_names(directory)
        cwd = self._repo_root or resolve_repo_root()
        command = [node, str(script), "--dir", str(directory)]
        try:
            completed = subprocess.run(  # noqa: S603 — argv constante, sin shell
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return self._failure(
                "TIMEOUT",
                f"El volcado superó {self._timeout} s y se abortó; revisa el tamaño de la BD",
                started,
            )
        except OSError as exc:
            return self._failure(
                "DUMP_FAILED",
                f"No se pudo lanzar el volcado ({exc.__class__.__name__})",
                started,
            )

        after = _list_backup_names(directory)
        created = after - before
        if completed.returncode != 0:
            detail = _tail(completed.stderr) or _tail(completed.stdout) or "sin detalle"
            return self._failure("DUMP_FAILED", detail, started, pruned=self._pruned(before, after))
        if not created:
            detail = _tail(completed.stderr) or "el script terminó sin escribir ningún fichero"
            return self._failure("OUTPUT_MISSING", detail, started, pruned=self._pruned(before, after))

        # Normalmente nace un único fichero; si hubiera más de uno, se informa el más
        # reciente y se deja constancia del resto en el mensaje.
        newest = max(created, key=lambda name: (directory / name).stat().st_mtime)
        path = directory / newest
        try:
            size = path.stat().st_size
        except OSError:
            return self._failure("OUTPUT_MISSING", "El fichero creado desapareció antes de medirlo", started)

        return BackupRunResult(
            ok=True,
            file=str(path),
            bytes=size,
            sha256=self._read_sha256(path),
            schema=self._read_schema(directory, newest),
            pruned=self._pruned(before, after),
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    # ------------------------------------------------------------------ internos

    @staticmethod
    def _pruned(before: set[str], after: set[str]) -> int:
        """Cuántos ficheros viejos podó la retención (1 nuevo por ejecución)."""
        return max(0, len(before) + 1 - len(after))

    @staticmethod
    def _read_sha256(path: Path) -> str | None:
        try:
            raw = (path.parent / f"{path.name}.sha256").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        first = raw.split()[0] if raw else ""
        return first.lower() if len(first) == 64 else None

    @staticmethod
    def _read_schema(directory: Path, name: str) -> str | None:
        try:
            parsed = json.loads((directory / "backups-manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(parsed, list):
            return None
        for item in parsed:
            if isinstance(item, dict) and item.get("file") == name:
                schema = item.get("schema")
                return schema if isinstance(schema, str) else None
        return None

    @staticmethod
    def _failure(
        code: str,
        detail: str,
        started: float,
        *,
        pruned: int = 0,
    ) -> BackupRunResult:
        return BackupRunResult(
            ok=False,
            pruned=pruned,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_code=code,
            error=detail[:_MAX_DETAIL] if detail else code,
        )


class PostgresMaintenanceLock:
    """Cerrojo de sesión PostgreSQL: serializa las copias entre procesos.

    Se toma una conexión dedicada del engine y se retiene hasta ``release``. No se usa la
    sesión de la petición: al devolverla al pool con el lock tomado, el cerrojo quedaría
    "suelto" en una conexión que otro request podría reutilizar.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        key: int = DEFAULT_MAINTENANCE_LOCK_KEY,
    ) -> None:
        self._engine = engine
        self._key = key
        self._connection: AsyncConnection | None = None

    async def try_acquire(self) -> bool:
        if self._connection is not None:
            # Ya lo tenemos: reintentar sería un no-op engañoso.
            return True
        connection = await self._engine.connect()
        try:
            row = (
                await connection.execute(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": self._key},
                )
            ).scalar()
        except Exception:
            await connection.close()
            raise
        if bool(row):
            self._connection = connection
            return True
        await connection.close()
        return False

    async def release(self) -> None:
        connection, self._connection = self._connection, None
        if connection is None:
            return
        try:
            await connection.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": self._key},
            )
        finally:
            await connection.close()


class JsonlMaintenanceAudit:
    """Auditoría append-only de mantenimiento en ``logs/agent/db-maintenance.jsonl``."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or agent_log_directory()

    @property
    def path(self) -> Path:
        return self._directory / "db-maintenance.jsonl"

    def record(self, entry: MaintenanceAuditEntry) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        line = json.dumps(_as_payload(entry), ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def read_all(self) -> Iterable[dict[str, object]]:
        """Lee las entradas registradas (diagnóstico y tests; nunca en el path caliente)."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return ()
        entries: list[dict[str, object]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                entries.append(parsed)
        return tuple(entries)


def _as_payload(entry: MaintenanceAuditEntry) -> dict[str, object]:
    payload: dict[str, object] = {
        "at": (entry.at or datetime.now(UTC)).astimezone(UTC).isoformat(),
        "action": entry.action,
        "actor": entry.actor,
        "ok": entry.ok,
        "durationMs": entry.duration_ms,
    }
    if entry.file:
        payload["file"] = entry.file
    if entry.bytes is not None:
        payload["bytes"] = entry.bytes
    if entry.error_code:
        payload["errorCode"] = entry.error_code
    if entry.detail:
        payload["detail"] = entry.detail[:_MAX_DETAIL]
    return payload
