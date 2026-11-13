"""Persistencia de propuestas/veredictos de adaptación — **ficheros, no base de datos**.

El bucle APL (ADR-049) no puede escribir en el motor ni en la estrategia activa; su memoria
tampoco necesita PostgreSQL. Cada propuesta vive en su propio JSON bajo
``operability_runs/ai-adaptation/<propuesta>.json``:

* **Aislada por id**: proponer dos veces la misma evidencia reescribe el mismo fichero (el id
  es estable), y dos propuestas distintas nunca comparten fichero.
* **Legible y determinista**: escritura atómica con JSON ordenado; la lectura ignora ficheros
  corruptos en vez de tumbar el listado.
* **Puro en rutas**: este módulo no lee configuración global; el caller inyecta la raíz.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from collections.abc import Iterator, Mapping
from typing import Any

__all__ = [
    "ADAPTATION_ARTIFACTS_ENV",
    "ADAPTATION_ARTIFACT_DIR",
    "adaptation_artifact_relpath",
    "adaptation_path",
    "adaptation_path_in",
    "adaptation_root",
    "iter_adaptation_records",
    "load_adaptation_record",
    "merge_adaptation_record",
    "save_adaptation_record",
]

#: Carpeta raíz del bucle de adaptación, relativa a la raíz del repo.
ADAPTATION_ARTIFACT_DIR = pathlib.Path("operability_runs") / "ai-adaptation"

#: Variable que redirige la raíz (despliegues fuera del árbol de trabajo).
ADAPTATION_ARTIFACTS_ENV = "AI_ADAPTATION_DIR"

#: Alfabeto seguro para el id (nunca ``.``/``/``/``\\``: un id hostil no escapa del árbol).
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _segment(proposal_id: str) -> str:
    value = (proposal_id or "").strip()
    if _SAFE_ID.fullmatch(value):
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:40]
    return f"adp-{digest}"


def adaptation_artifact_relpath(proposal_id: str) -> pathlib.Path:
    """Ruta **relativa** del registro de una propuesta dentro de la raíz del repo."""
    return ADAPTATION_ARTIFACT_DIR / f"{_segment(proposal_id)}.json"


def adaptation_path_in(artifacts_dir: pathlib.Path, proposal_id: str) -> pathlib.Path:
    return pathlib.Path(artifacts_dir) / f"{_segment(proposal_id)}.json"


def adaptation_path(root: pathlib.Path, proposal_id: str) -> pathlib.Path:
    return pathlib.Path(root) / ADAPTATION_ARTIFACT_DIR / f"{_segment(proposal_id)}.json"


def adaptation_root(default_root: pathlib.Path, environ: Mapping[str, str]) -> pathlib.Path:
    raw = (environ.get(ADAPTATION_ARTIFACTS_ENV) or "").strip()
    return pathlib.Path(raw) if raw else pathlib.Path(default_root)


def save_adaptation_record(artifacts_dir: pathlib.Path, record: Mapping[str, Any]) -> pathlib.Path:
    """Escribe el registro de forma atómica y devuelve su ruta."""
    proposal_id = str(record.get("id") or "").strip()
    if not proposal_id:
        raise ValueError("registro sin id de propuesta")
    path = adaptation_path_in(artifacts_dir, proposal_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(record), sort_keys=True, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_adaptation_record(
    artifacts_dir: pathlib.Path, proposal_id: str
) -> dict[str, Any] | None:
    path = adaptation_path_in(artifacts_dir, proposal_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def merge_adaptation_record(
    artifacts_dir: pathlib.Path, proposal_id: str, patch: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Fusiona ``patch`` sobre el registro existente; ``None`` si no existe."""
    current = load_adaptation_record(artifacts_dir, proposal_id)
    if current is None:
        return None
    current.update(dict(patch))
    save_adaptation_record(artifacts_dir, current)
    return current


def iter_adaptation_records(artifacts_dir: pathlib.Path) -> Iterator[dict[str, Any]]:
    """Registros válidos, ordenados por ``createdAt`` desc y luego por id (estable)."""
    directory = pathlib.Path(artifacts_dir)
    if not directory.is_dir():
        return
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            records.append(payload)
    records.sort(key=lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or "")), reverse=True)
    yield from records
