"""Copia de seguridad de ``bolsa_v1`` bajo demanda desde Configuración → BD.

El diagnóstico de ``database_maintenance`` responde «¿cuándo fue la última copia?». Esta
entrega añade la única acción de mantenimiento que la UI puede disparar: **crear una
copia ahora**. Sigue siendo una operación que no escribe en PostgreSQL —``pg_dump`` solo
lee— pero sí crea un fichero y poda por retención, así que no es «read-only» y se blinda:

* **Un trabajo a la vez**: un cerrojo (advisory lock PostgreSQL) serializa la petición
  entre procesos. Si está ocupado, no se encola nada: se devuelve ``busy`` y la ruta
  contesta 409. Un doble clic no puede producir dos volcados.
* **Sin simulación**: si el runner falla, el resultado lleva ``ok=False`` y su
  ``error_code``. Nunca se inventa un fichero ni un checksum.
* **Auditoría siempre**: éxito y fallo dejan una entrada con actor, fichero, bytes y
  duración. La ausencia de entrada es un fallo del propio registro, no un éxito.
* **Producción fuera**: el llamante declara si el entorno es productivo; en ese caso la
  operación se rechaza con motivo. La copia de ``bolsa_v1`` es una herramienta local.

Puertos (sin imports de infraestructura): ``BackupRunner`` ejecuta el volcado,
``MaintenanceLock`` serializa y ``MaintenanceAudit`` registra.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from bolsa_application.database_maintenance import (
    BackupInventory,
    BackupReport,
    BackupSnapshot,
    summarize_backup_snapshot,
)

__all__ = [
    "BackupRunReport",
    "BackupRunResult",
    "BackupRunner",
    "CreateDatabaseBackup",
    "MaintenanceAudit",
    "MaintenanceAuditEntry",
    "MaintenanceLock",
    "PRODUCTION_FORBIDDEN",
    "RUNNER_ERROR",
    "BUSY",
]

#: Códigos estables: la UI y los tests se apoyan en ellos, no en el texto libre.
PRODUCTION_FORBIDDEN = "PRODUCTION_FORBIDDEN"
RUNNER_ERROR = "RUNNER_ERROR"
BUSY = "BUSY"

#: Tope defensivo del actor que viaja a la auditoría (un JWT cabría, un log no debe crecer).
_MAX_ACTOR = 120


@dataclass(frozen=True, slots=True)
class BackupRunResult:
    """Resultado de un volcado. ``ok=False`` siempre trae ``error_code``."""

    ok: bool
    file: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    schema: str | None = None
    pruned: int = 0
    mirror_path: str | None = None
    duration_ms: int = 0
    error_code: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MaintenanceAuditEntry:
    """Una línea del registro de mantenimiento (``logs/agent/db-maintenance.jsonl``)."""

    action: str
    actor: str
    ok: bool
    at: datetime
    file: str | None = None
    bytes: int | None = None
    duration_ms: int = 0
    error_code: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class BackupRunReport:
    """Respuesta del caso de uso: el intento y el estado real del inventario después.

    ``backups`` se recalcula **después** del volcado, para que la tarjeta muestre la copia
    recién creada sin una segunda llamada ni un dato viejo.
    """

    run: BackupRunResult
    backups: BackupReport | None
    busy: bool = False
    refused: bool = False
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.run.ok


class BackupRunner(Protocol):
    """Ejecuta el volcado en el directorio indicado (síncrono: se llama en un thread)."""

    def create(self, directory: Path) -> BackupRunResult: ...


class MaintenanceLock(Protocol):
    """Cerrojo de mantenimiento (exclusión global, no solo dentro del proceso)."""

    async def try_acquire(self) -> bool: ...

    async def release(self) -> None: ...


class MaintenanceAudit(Protocol):
    """Registro append-only de acciones de mantenimiento."""

    def record(self, entry: MaintenanceAuditEntry) -> None: ...


class CreateDatabaseBackup:
    """Crea una copia local de la BD y devuelve el intento junto al inventario nuevo."""

    def __init__(
        self,
        *,
        runner: BackupRunner,
        lock: MaintenanceLock,
        audit: MaintenanceAudit,
        backup_inventory: BackupInventory,
        backup_directory: Path,
        expected_head: str | None = None,
        backup_stale_hours: float = 24.0,
        production: bool = False,
    ) -> None:
        self._runner = runner
        self._lock = lock
        self._audit = audit
        self._backup_inventory = backup_inventory
        self._backup_directory = backup_directory
        self._expected_head = expected_head
        self._backup_stale_hours = backup_stale_hours
        self._production = production

    async def execute(self, *, actor: str = "system") -> BackupRunReport:
        who = (actor or "system").strip()[:_MAX_ACTOR] or "system"

        if self._production:
            # Fail-closed antes de tocar el cerrojo o el disco: en producción esta copia
            # local no es la herramienta (allí manda la política de backups del hosting).
            return BackupRunReport(
                run=BackupRunResult(
                    ok=False,
                    error_code=PRODUCTION_FORBIDDEN,
                    error="La copia local bajo demanda está deshabilitada en producción",
                ),
                backups=None,
                refused=True,
                reason=PRODUCTION_FORBIDDEN,
            )

        if not await self._lock.try_acquire():
            return BackupRunReport(
                run=BackupRunResult(
                    ok=False,
                    error_code=BUSY,
                    error="Ya hay una copia en curso; espera a que termine",
                ),
                backups=None,
                busy=True,
                reason=BUSY,
            )

        started = datetime.now(UTC)
        result: BackupRunResult
        try:
            result = await asyncio.to_thread(self._runner.create, self._backup_directory)
        except Exception as exc:  # noqa: BLE001 — el puerto no debe tumbar la petición
            result = BackupRunResult(
                ok=False,
                error_code=RUNNER_ERROR,
                error=f"El ejecutor de copias falló: {exc.__class__.__name__}: {exc}",
            )
        finally:
            await self._lock.release()

        # Una sola entrada por intento: éxito y fallo se registran igual.
        self._record(who, started, result)
        return BackupRunReport(
            run=result,
            backups=self._snapshot(),
            busy=False,
            refused=False,
        )

    # ------------------------------------------------------------------ internos

    def _record(
        self,
        actor: str,
        started: datetime,
        result: BackupRunResult,
    ) -> None:
        """Registra el intento (éxito o fallo) sin poder tumbar la petición."""
        entry = MaintenanceAuditEntry(
            action="database.backup",
            actor=actor,
            ok=result.ok,
            at=started,
            file=result.file,
            bytes=result.bytes,
            duration_ms=result.duration_ms or _elapsed_ms(started),
            error_code=result.error_code,
            detail=result.error,
        )
        try:
            self._audit.record(entry)
        except Exception:  # noqa: BLE001 — la auditoría best-effort no tumba la copia
            pass

    def _snapshot(self) -> BackupReport | None:
        try:
            snapshot: BackupSnapshot = self._backup_inventory.snapshot()
        except Exception:  # noqa: BLE001 — sin inventario no se inventa estado
            return None
        return summarize_backup_snapshot(
            snapshot,
            expected_head=self._expected_head,
            stale_hours=self._backup_stale_hours,
            now=datetime.now(UTC),
        )


def _elapsed_ms(started: datetime) -> int:
    return max(0, int((datetime.now(UTC) - started).total_seconds() * 1000))
