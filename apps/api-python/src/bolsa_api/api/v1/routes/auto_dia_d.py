"""API: DÍA-D AUTO (sandbox) — espejo read-only del artefacto `dia-d-auto-<D>.json`.

Expone el artefacto que produce ``apps/api-python/scripts/v2_89_dia_d_auto_replay.py``: la
comparación, paso a paso de la cadena AUTO, entre lo que el motor **DECLARÓ** en la fecha
pasada ``D`` (replay hermético con reloj/precio inyectados) y lo que la ventana PAPER
**EJECUTÓ** de verdad (hechos durables de ``D``), más el OOS real del ciclo abierto en ``D``.

Read-only: este router NO ejecuta el motor (eso vive en el CLI) y NO escribe nada. Sin cuenta
visible del principal devuelve vacío con ``no_account_scope`` (fail-closed). Un día sin
artefacto se declara ``available = false``; nunca se rellena con ceros.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.api.dependencies import (
    get_account_id_header,
    resolve_account_scope_or_default,
)

router = APIRouter()

#: Directorio por defecto de artefactos (relativo a la raíz del repo). `DIA_D_AUTO_DIR` lo
#: sobreescribe para despliegues donde la API corre fuera del árbol de trabajo.
#: ``routes`` → ``v1`` → ``api`` → ``bolsa_api`` → ``src`` → ``api-python`` → ``apps`` → raíz.
_DEFAULT_DIR = Path(__file__).resolve().parents[7] / "operability_runs" / "dia-d-auto"

#: Nombre canónico del artefacto por día. El guion bajo/guiones se aceptan en la fecha.
_ARTIFACT_RE = re.compile(r"^dia-d-auto-(\d{4}-\d{2}-\d{2})\.json$")
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _artifacts_dir() -> Path:
    override = os.environ.get("DIA_D_AUTO_DIR")
    return Path(override) if override else _DEFAULT_DIR


def _artifact_path(day: str) -> Path:
    return _artifacts_dir() / f"dia-d-auto-{day}.json"


def _read_artifact(day: str) -> dict[str, Any] | None:
    """Lee el artefacto JSON de ``day`` (read-only); ``None`` si no existe o no es legible."""
    path = _artifact_path(day)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _list_days() -> list[str]:
    """Días con artefacto disponible, descendente (el más reciente primero)."""
    directory = _artifacts_dir()
    if not directory.is_dir():
        return []
    days: list[str] = []
    for entry in directory.iterdir():
        match = _ARTIFACT_RE.match(entry.name)
        if match and entry.is_file():
            days.append(match.group(1))
    return sorted(set(days), reverse=True)


class DiaDAutoStepDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    step: str
    declared: Any = None
    executed: Any = None
    verdict: str
    measurement: str


class DiaDAutoSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    verdict: str
    match: int
    divergent: int
    notMeasured: int
    steps: int


class DiaDAutoOosDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    closedCount: int = 0
    openCount: int = 0
    realizedRTotal: float = 0.0
    unmeasuredCount: int = 0
    realized: list[dict[str, Any]] = Field(default_factory=list)
    open: list[dict[str, Any]] = Field(default_factory=list)


class DiaDAutoReplayDto(BaseModel):
    """Artefacto de un día. ``available = false`` cuando no existe (fail-closed)."""

    model_config = ConfigDict(populate_by_name=True)

    available: bool
    readOnly: bool = True
    day: str
    schemaVersion: str | None = None
    summary: DiaDAutoSummaryDto | None = None
    steps: list[DiaDAutoStepDto] = Field(default_factory=list)
    oos: DiaDAutoOosDto | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    limits: list[str] = Field(default_factory=list)
    executedDetail: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class DiaDAutoReplayListDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    readOnly: bool = True
    days: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _artifact_account(artifact: dict[str, Any]) -> str | None:
    """Cuenta sellada en el artefacto; ``None`` si no declara ninguna (fail-closed)."""
    meta = artifact.get("meta") or {}
    account = meta.get("account")
    return str(account) if account else None


def _artifact_matches_scope(artifact: dict[str, Any], scope: str) -> bool:
    """``True`` solo si el artefacto declara EXACTAMENTE la cuenta del principal (D34-06)."""
    return _artifact_account(artifact) == scope


@router.get("/auto/dia-d-replay", response_model=DiaDAutoReplayListDto)
async def list_auto_dia_d_replay(
    request: Request,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDAutoReplayListDto:
    """Días con artefacto DÍA-D AUTO DISPONIBLES PARA LA CUENTA (selector de fecha, fail-closed)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDAutoReplayListDto(days=[], notes=["no_account_scope"])
    days: list[str] = []
    for candidate in _list_days():
        artifact = _read_artifact(candidate)
        if artifact is not None and _artifact_matches_scope(artifact, scope):
            days.append(candidate)
    notes = [] if days else ["no_artifacts"]
    return DiaDAutoReplayListDto(days=days, notes=notes)


@router.get("/auto/dia-d-replay/{day}", response_model=DiaDAutoReplayDto)
async def get_auto_dia_d_replay(
    request: Request,
    day: str,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDAutoReplayDto:
    """Artefacto DÍA-D AUTO de ``day`` (``YYYY-MM-DD``), read-only y fail-closed por cuenta."""
    if not _DAY_RE.match(day):
        return DiaDAutoReplayDto(available=False, day=day, notes=["invalid_day"])
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDAutoReplayDto(available=False, day=day, notes=["no_account_scope"])

    artifact = _read_artifact(day)
    # D34-06: una cuenta distinta es INDISTINGUIBLE de inexistente: no se revela que existe.
    if artifact is None or not _artifact_matches_scope(artifact, scope):
        return DiaDAutoReplayDto(available=False, day=day, notes=["artifact_not_found"])

    meta = artifact.get("meta") or {}
    return DiaDAutoReplayDto(
        available=True,
        readOnly=bool(artifact.get("readOnly", True)),
        day=str(artifact.get("day") or day),
        schemaVersion=artifact.get("schemaVersion"),
        summary=DiaDAutoSummaryDto(**artifact["summary"]) if artifact.get("summary") else None,
        steps=[DiaDAutoStepDto(**row) for row in artifact.get("comparison", [])],
        oos=DiaDAutoOosDto(**artifact["oos"]) if artifact.get("oos") else None,
        meta=dict(meta),
        limits=list(artifact.get("limits", [])),
        executedDetail=dict(artifact.get("executedDetail") or {}),
        notes=[],
    )
