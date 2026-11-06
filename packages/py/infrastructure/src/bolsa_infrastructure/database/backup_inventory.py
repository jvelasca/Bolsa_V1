"""Inventario de copias de seguridad de ``bolsa_v1`` (solo lectura).

El mecanismo de copias ya existe (``pnpm db:dump`` / ``db:restore`` / ``db:backup:list``),
pero vivía **fuera** de la aplicación: nadie podía ver desde Configuración si la última
copia era de hace una hora o de hace dos días. Este adaptador lee el manifest y el
sistema de ficheros y publica hechos:

* qué copias hay y cuál es la más reciente,
* su edad y si supera el umbral de frescura,
* si existe el sidecar ``.sha256`` (integridad declarada),
* en qué revisión Alembic se tomó,
* si hay espejo off-site configurado.

No crea, no borra y no restaura nada; tampoco re-hashea el volcado en cada GET (un dump de
87 MB por consulta sería un coste absurdo): informa de la presencia del checksum, que es lo
que el restore verifica de verdad.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from bolsa_application.database_maintenance import BackupSnapshot

__all__ = [
    "BackupInventoryAdapter",
    "backup_directory",
    "backup_stale_hours",
    "resolve_repo_root",
]

_REPO_ROOT = Path(__file__).resolve().parents[6]
_DEFAULT_BACKUP_DIR = "db-backups"
_DEFAULT_KEEP = 14
_DEFAULT_STALE_HOURS = 24.0


def resolve_repo_root() -> Path:
    return _REPO_ROOT


def backup_directory() -> Path:
    """``DB_BACKUP_DIR`` (absoluta o relativa al repo) o ``db-backups`` por defecto."""
    raw = (os.environ.get("DB_BACKUP_DIR") or "").strip()
    if not raw:
        return _REPO_ROOT / _DEFAULT_BACKUP_DIR
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else _REPO_ROOT / raw


def backup_stale_hours() -> float:
    """Umbral de frescura de la copia más reciente (``DB_BACKUP_STALE_HOURS``)."""
    raw = (os.environ.get("DB_BACKUP_STALE_HOURS") or "").strip()
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_STALE_HOURS
    return value if value > 0 else _DEFAULT_STALE_HOURS


def _retention() -> int:
    raw = (os.environ.get("DB_BACKUP_KEEP") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_KEEP
    return value if value > 0 else _DEFAULT_KEEP


def _mirror_configured() -> bool:
    return bool((os.environ.get("DB_BACKUP_MIRROR_DIR") or "").strip())


@dataclass(frozen=True, slots=True)
class _ManifestEntry:
    file: str
    bytes: int | None
    created_at: datetime | None
    schema: str | None
    mirror: bool


def _parse_datetime(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _read_manifest(directory: Path) -> dict[str, _ManifestEntry]:
    path = directory / "backups-manifest.json"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(parsed, list):
        return {}
    entries: dict[str, _ManifestEntry] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("file")
        if not isinstance(name, str) or not name:
            continue
        raw_bytes = item.get("bytes")
        entries[name] = _ManifestEntry(
            file=name,
            bytes=int(raw_bytes) if isinstance(raw_bytes, int) else None,
            created_at=_parse_datetime(item.get("created_at")),
            schema=item.get("schema") if isinstance(item.get("schema"), str) else None,
            mirror=bool(item.get("mirror")),
        )
    return entries


def _is_backup_file(name: str) -> bool:
    return name.startswith("bolsa_v1-") and (name.endswith(".sql") or name.endswith(".sql.gz"))


class BackupInventoryAdapter:
    """Adaptador de ``BackupInventory`` sobre ``db-backups/`` y su manifest."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or backup_directory()

    def snapshot(self) -> BackupSnapshot:
        directory = self._directory
        retention = _retention()
        if not directory.exists():
            return BackupSnapshot(
                accessible=False,
                directory=str(directory),
                retention=retention,
                mirror_configured=_mirror_configured(),
                detail=(
                    "El directorio de copias no existe o no es visible desde el proceso "
                    "de la API"
                ),
            )

        try:
            files = [entry for entry in directory.iterdir() if entry.is_file()]
        except OSError as exc:
            return BackupSnapshot(
                accessible=False,
                directory=str(directory),
                retention=retention,
                mirror_configured=_mirror_configured(),
                detail=f"No se pudo listar el directorio de copias: {exc.__class__.__name__}",
            )

        manifest = _read_manifest(directory)
        backups = [entry for entry in files if _is_backup_file(entry.name)]
        if not backups:
            return BackupSnapshot(
                accessible=True,
                directory=str(directory),
                retention=retention,
                mirror_configured=_mirror_configured(),
                detail="No hay ninguna copia en el directorio",
            )

        # La copia más reciente se decide por fecha del manifest y, si falta, por mtime.
        def _sort_key(entry: Path) -> tuple[datetime, str]:
            known = manifest.get(entry.name)
            created = known.created_at if known is not None else None
            if created is None:
                created = datetime.fromtimestamp(entry.stat().st_mtime, tz=UTC)
            return created, entry.name

        latest = max(backups, key=_sort_key)
        known = manifest.get(latest.name)
        created_at = known.created_at if known is not None else None
        if created_at is None:
            created_at = datetime.fromtimestamp(latest.stat().st_mtime, tz=UTC)

        size = latest.stat().st_size
        return BackupSnapshot(
            accessible=True,
            directory=str(directory),
            count=len(backups),
            latest_name=latest.name,
            latest_bytes=size,
            latest_created_at=created_at,
            latest_schema=known.schema if known is not None else None,
            checksum_present=(directory / f"{latest.name}.sha256").is_file(),
            mirror_configured=_mirror_configured() or bool(known and known.mirror),
            retention=retention,
            detail=f"{len(backups)} copia(s) en {directory}",
        )
