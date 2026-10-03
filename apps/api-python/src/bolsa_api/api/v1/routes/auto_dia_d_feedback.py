"""API: DÍA-D AUTO · FEEDBACK (por valor) — espejo read-only del artefacto de la ventana.

Expone el artefacto que produce ``apps/api-python/scripts/v2_90_dia_d_feedback.py``: el veredicto
por instrumento (``CONFIRMED``/``MIXED``/``REFUTED``/``NOT_MEASURED``), la matriz valor × día, el
catálogo de errores (``SOFTWARE``/``OPERATIONAL``/``DATA``) y el gate de ventana.

Read-only: este router NO ejecuta el motor (eso vive en el CLI) y NO escribe nada. Sin cuenta
visible del principal devuelve vacío con ``no_account_scope`` (fail-closed). Una ventana sin
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

#: Nombre canónico del artefacto por ventana: ``feedback-<D0>_<D1>.json``.
_ARTIFACT_RE = re.compile(r"^feedback-(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$")
_WINDOW_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}$")


def _artifacts_dir() -> Path:
    override = os.environ.get("DIA_D_AUTO_DIR")
    return Path(override) if override else _DEFAULT_DIR


def _artifact_path(window: str) -> Path:
    return _artifacts_dir() / f"feedback-{window}.json"


def _read_artifact(window: str) -> dict[str, Any] | None:
    """Lee el artefacto JSON de ``window`` (read-only); ``None`` si no existe o no es legible."""
    path = _artifact_path(window)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _list_windows() -> list[str]:
    """Ventanas con artefacto disponible, DESCENDENTE (la más reciente primero)."""
    directory = _artifacts_dir()
    if not directory.is_dir():
        return []
    windows: list[str] = []
    for entry in directory.iterdir():
        match = _ARTIFACT_RE.match(entry.name)
        if match and entry.is_file():
            windows.append(f"{match.group(1)}_{match.group(2)}")
    return sorted(set(windows), reverse=True)


class DiaDFeedbackWindowDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(default="", alias="from")
    to: str = ""
    days: list[str] = Field(default_factory=list)


class DiaDFeedbackErrorCountsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    SOFTWARE: int = 0
    OPERATIONAL: int = 0
    DATA: int = 0
    total: int = 0


class DiaDFeedbackSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    values: int = 0
    confirmed: int = 0
    mixed: int = 0
    refuted: int = 0
    notMeasured: int = 0
    measuredValues: int = 0
    errors: DiaDFeedbackErrorCountsDto = Field(default_factory=DiaDFeedbackErrorCountsDto)


class DiaDFeedbackValueLimitsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    minCycles: int = 0
    minHitRate: float = 0.0


class DiaDFeedbackByDayDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    realizedR: float | None = None
    cycles: int = 0
    errors: int = 0


class DiaDFeedbackValueDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    verdict: str
    verdictReason: str | None = None
    expectancyR: float | None = None
    hitRate: float | None = None
    measuredCycles: int = 0
    daysCovered: int = 0
    windowDays: int = 0
    realizedRTotal: float | None = None
    errors: DiaDFeedbackErrorCountsDto = Field(default_factory=DiaDFeedbackErrorCountsDto)
    errorTotal: int = 0
    byDay: dict[str, DiaDFeedbackByDayDto] = Field(default_factory=dict)
    limits: DiaDFeedbackValueLimitsDto = Field(default_factory=DiaDFeedbackValueLimitsDto)


class DiaDFeedbackCellDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    day: str
    realizedR: float | None = None
    cycles: int = 0
    errors: int = 0
    outcome: str


class DiaDFeedbackMatrixRowDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    cells: list[DiaDFeedbackCellDto] = Field(default_factory=list)


class DiaDFeedbackErrorDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    day: str = ""
    symbol: str = ""
    kind: str
    code: str
    detail: str | None = None


class DiaDFeedbackDto(BaseModel):
    """Artefacto de una ventana. ``available = false`` cuando no existe (fail-closed)."""

    model_config = ConfigDict(populate_by_name=True)

    available: bool
    readOnly: bool = True
    schemaVersion: str | None = None
    kind: str | None = None
    window: DiaDFeedbackWindowDto = Field(default_factory=DiaDFeedbackWindowDto)
    summary: DiaDFeedbackSummaryDto | None = None
    values: list[DiaDFeedbackValueDto] = Field(default_factory=list)
    matrix: list[DiaDFeedbackMatrixRowDto] = Field(default_factory=list)
    errors: list[DiaDFeedbackErrorDto] = Field(default_factory=list)
    gate: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    limits: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DiaDFeedbackListDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    readOnly: bool = True
    windows: list[str] = Field(default_factory=list)
    latest: str | None = None
    artifact: DiaDFeedbackDto | None = None
    notes: list[str] = Field(default_factory=list)


def _project(artifact: dict[str, Any], scope: str) -> DiaDFeedbackDto:
    """Proyecta el artefacto crudo al DTO del contrato (declarando la cuenta si no cuadra)."""
    notes: list[str] = []
    meta = artifact.get("meta") or {}
    artifact_account = meta.get("account")
    if artifact_account and artifact_account != scope:
        notes.append("account_scope_mismatch")
    return DiaDFeedbackDto(
        available=True,
        readOnly=bool(artifact.get("readOnly", True)),
        schemaVersion=artifact.get("schemaVersion"),
        kind=artifact.get("kind"),
        window=DiaDFeedbackWindowDto(**dict(artifact.get("window") or {})),
        summary=(
            DiaDFeedbackSummaryDto(**artifact["summary"]) if artifact.get("summary") else None
        ),
        values=[DiaDFeedbackValueDto(**row) for row in artifact.get("values", [])],
        matrix=[DiaDFeedbackMatrixRowDto(**row) for row in artifact.get("matrix", [])],
        errors=[DiaDFeedbackErrorDto(**row) for row in artifact.get("errors", [])],
        gate=dict(artifact.get("gate") or {}),
        meta=dict(meta),
        limits=list(artifact.get("limits", [])),
        notes=notes,
    )


@router.get("/auto/dia-d-feedback", response_model=DiaDFeedbackListDto)
async def list_auto_dia_d_feedback(
    request: Request,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDFeedbackListDto:
    """Ventanas con feedback disponibles + el artefacto MÁS RECIENTE (read-only, fail-closed)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDFeedbackListDto(windows=[], notes=["no_account_scope"])
    windows = _list_windows()
    if not windows:
        return DiaDFeedbackListDto(windows=[], notes=["no_artifacts"])
    latest = windows[0]
    artifact = _read_artifact(latest)
    return DiaDFeedbackListDto(
        windows=windows,
        latest=latest,
        artifact=None if artifact is None else _project(artifact, scope),
        notes=[],
    )


@router.get("/auto/dia-d-feedback/{window}", response_model=DiaDFeedbackDto)
async def get_auto_dia_d_feedback(
    request: Request,
    window: str,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDFeedbackDto:
    """Artefacto de feedback de ``window`` (``D0_D1``), read-only y fail-closed."""
    if not _WINDOW_RE.match(window):
        return DiaDFeedbackDto(available=False, notes=["invalid_window"])
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDFeedbackDto(available=False, notes=["no_account_scope"])
    artifact = _read_artifact(window)
    if artifact is None:
        return DiaDFeedbackDto(available=False, notes=["artifact_not_found"])
    return _project(artifact, scope)
