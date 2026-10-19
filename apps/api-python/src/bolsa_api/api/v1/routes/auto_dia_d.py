"""API: DÍA-D AUTO (sandbox) — espejo read-only del artefacto por ``(cuenta, día)``.

Expone el artefacto que produce ``apps/api-python/scripts/v2_89_dia_d_auto_replay.py``: la
comparación, paso a paso de la cadena AUTO, entre lo que el motor **DECLARÓ** en la fecha
pasada ``D`` (replay hermético con reloj/precio inyectados) y lo que la ventana PAPER
**EJECUTÓ** de verdad (hechos durables de ``D``), más el OOS real del ciclo abierto en ``D``.

Esquema de lectura (compartido con el worker, `bolsa_application.dia_d_artifacts`)::

    <DIA_D_AUTO_DIR>/<segmento-cuenta>/dia-d-auto-<D>.json

**Legacy declarado:** si la ruta nueva no existe, se acepta la ruta plana histórica
(``<DIA_D_AUTO_DIR>/dia-d-auto-<D>.json``) **solo** cuando su ``meta.account`` coincide con la
cuenta activa. Se devuelve la nota ``legacy_artifact`` para que la UI no confunda procedencia.

Read-only: este router NO ejecuta el motor (eso vive en el CLI) y NO escribe nada. Sin cuenta
visible del principal devuelve vacío con ``no_account_scope`` (fail-closed). Un día sin
artefacto se declara ``available = false``; nunca se rellena con ceros.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.api.dependencies import (
    get_account_id_header,
    resolve_account_scope_or_default,
)
from bolsa_application.dia_d_artifacts import account_segment

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


def _artifact_path(day: str, scope: str) -> Path:
    """Artefacto canónico de ``(cuenta, día)`` (aislado por cuenta)."""
    return _artifacts_dir() / account_segment(scope) / f"dia-d-auto-{day}.json"


def _legacy_artifact_path(day: str) -> Path:
    """Ruta plana histórica (sin cuenta). Solo lectura, con ``meta.account`` verificado."""
    return _artifacts_dir() / f"dia-d-auto-{day}.json"


def _parse_artifact(path: Path) -> dict[str, Any] | None:
    """JSON legible de ``path``; ``None`` si no es fichero, no se puede leer o no es objeto."""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_artifact(
    day: str, scope: str
) -> tuple[Path | None, dict[str, Any] | None, bool]:
    """Artefacto visible para ``scope``: ``(ruta, payload, es_legacy)``.

    Orden: (1) ruta canónica por cuenta; (2) ruta plana histórica **solo** si su
    ``meta.account`` coincide exactamente con la cuenta del principal. Nunca se sirve a otra
    cuenta un artefacto plano (sería una fuga de contexto entre cuentas).
    """
    canonical = _artifact_path(day, scope)
    payload = _parse_artifact(canonical)
    if payload is not None:
        return canonical, payload, False

    legacy = _legacy_artifact_path(day)
    legacy_payload = _parse_artifact(legacy)
    if legacy_payload is not None and _artifact_matches_scope(legacy_payload, scope):
        return legacy, legacy_payload, True
    return None, None, False


def _read_artifact(day: str, scope: str) -> dict[str, Any] | None:
    """Lee el artefacto JSON de ``(cuenta, día)`` (read-only); ``None`` si no hay."""
    return _resolve_artifact(day, scope)[1]


def _artifact_modified_at(day: str, scope: str) -> str | None:
    """Marca temporal del artefacto **leído** (distingue «artefacto anterior» de uno fresco)."""
    path = _resolve_artifact(day, scope)[0]
    if path is None:
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat()


def _list_days(scope: str) -> list[str]:
    """Días con artefacto disponible **para ``scope``**, descendente.

    Se recorren el directorio de la cuenta (esquema vigente) y, para compatibilidad, la ruta
    plana histórica; un artefacto plano de otra cuenta no se lista.
    """
    directory = _artifacts_dir()
    days: set[str] = set()

    account_dir = directory / account_segment(scope)
    if account_dir.is_dir():
        for entry in account_dir.iterdir():
            match = _ARTIFACT_RE.match(entry.name)
            if match and entry.is_file():
                days.add(match.group(1))

    if directory.is_dir():
        for entry in directory.iterdir():
            match = _ARTIFACT_RE.match(entry.name)
            if not (match and entry.is_file()):
                continue
            payload = _parse_artifact(entry)
            if payload is not None and _artifact_matches_scope(payload, scope):
                days.add(match.group(1))

    return sorted(days, reverse=True)


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
    #: mtime del artefacto: la UI etiqueta «artefacto anterior» si el último job falló.
    artifactModifiedAt: str | None = None
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
    days = _list_days(scope)
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

    _path, artifact, is_legacy = _resolve_artifact(day, scope)
    # D34-06: una cuenta distinta es INDISTINGUIBLE de inexistente: no se revela que existe.
    if artifact is None:
        return DiaDAutoReplayDto(available=False, day=day, notes=["artifact_not_found"])

    meta = artifact.get("meta") or {}
    return DiaDAutoReplayDto(
        available=True,
        readOnly=bool(artifact.get("readOnly", True)),
        day=str(artifact.get("day") or day),
        artifactModifiedAt=_artifact_modified_at(day, scope),
        schemaVersion=artifact.get("schemaVersion"),
        summary=DiaDAutoSummaryDto(**artifact["summary"]) if artifact.get("summary") else None,
        steps=[DiaDAutoStepDto(**row) for row in artifact.get("comparison", [])],
        oos=DiaDAutoOosDto(**artifact["oos"]) if artifact.get("oos") else None,
        meta=dict(meta),
        limits=list(artifact.get("limits", [])),
        executedDetail=dict(artifact.get("executedDetail") or {}),
        # Procedencia declarada: un artefacto leído de la ruta plana histórica se etiqueta.
        notes=["legacy_artifact"] if is_legacy else [],
    )
