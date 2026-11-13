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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)
from bolsa_application.auto_ops_jobs import EnqueueAutoOpsJob
from bolsa_application.dia_d_artifacts import (
    account_segment,
    artifacts_root,
    as_run_artifact_path_in,
    as_run_artifacts_root,
    value_artifact_path_in,
)
from bolsa_application.dia_d_certification import certify_artifact
from bolsa_domain.entities.auto_ops_job import JOB_KIND_DIA_D_AS_RUN
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)

router = APIRouter()

#: Directorio por defecto de artefactos (relativo a la raíz del repo). `DIA_D_AUTO_DIR` lo
#: sobreescribe para despliegues donde la API corre fuera del árbol de trabajo.
#: ``routes`` → ``v1`` → ``api`` → ``bolsa_api`` → ``src`` → ``api-python`` → ``apps`` → raíz.
_DEFAULT_DIR = Path(__file__).resolve().parents[7] / "operability_runs" / "dia-d-auto"

#: Raíz propia del método **as-run** (ADR-049). No comparte directorio con ``dia-d-auto``.
_DEFAULT_AS_RUN_DIR = Path(__file__).resolve().parents[7] / "operability_runs" / "dia-d-as-run"

#: Nombre canónico del artefacto por día. El guion bajo/guiones se aceptan en la fecha.
_ARTIFACT_RE = re.compile(r"^dia-d-auto-(\d{4}-\d{2}-\d{2})\.json$")
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#: Símbolo admitido en la ruta (mismo alfabeto que el catálogo; se normaliza a mayúsculas).
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


def _artifacts_dir() -> Path:
    """Raíz de artefactos, resuelta por el MISMO helper que usa el worker que escribe."""
    return artifacts_root(_DEFAULT_DIR, os.environ)


def _as_run_artifacts_dir() -> Path:
    """Raíz de artefactos as-run, resuelta por el MISMO helper que usa el worker."""
    return as_run_artifacts_root(_DEFAULT_AS_RUN_DIR, os.environ)


def _artifact_path(day: str, scope: str) -> Path:
    """Artefacto canónico de ``(cuenta, día)`` (aislado por cuenta)."""
    return _artifacts_dir() / account_segment(scope) / f"dia-d-auto-{day}.json"


def _value_artifact_path(day: str, scope: str, symbol: str) -> Path:
    """Artefacto DÍA-D de **un valor** (``…/<cuenta>/values/<SÍMBOLO>/…``) — otro fichero."""
    return value_artifact_path_in(_artifacts_dir(), day, scope, symbol)


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
    #: Símbolo cuando el artefacto es la verificación DÍA-D de UN valor (árbol ``values/``).
    symbol: str | None = None
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


@router.get(
    "/auto/dia-d-replay/{day}/value/{symbol}", response_model=DiaDAutoReplayDto
)
async def get_auto_dia_d_replay_value(
    request: Request,
    day: str,
    symbol: str,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDAutoReplayDto:
    """Verificación DÍA-D de **un valor** (``values/<SÍMBOLO>``), read-only y fail-closed.

    Es un artefacto DISTINTO del día completo: se sirve solo si declara la cuenta activa y
    un watch que cubre **exactamente** ese símbolo. No se rellena desde el artefacto del día
    (diría «verificado» con la evidencia del watch entero, que es justo la confusión a evitar).
    """
    wanted = (symbol or "").strip().upper()
    if not _DAY_RE.match(day) or not _SYMBOL_RE.match(wanted):
        return DiaDAutoReplayDto(
            available=False, day=day, symbol=wanted or None, notes=["invalid_request"]
        )
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDAutoReplayDto(
            available=False, day=day, symbol=wanted, notes=["no_account_scope"]
        )

    path = _value_artifact_path(day, scope, wanted)
    artifact = _parse_artifact(path)
    if artifact is None or not _artifact_matches_scope(artifact, scope):
        # Una cuenta distinta es INDISTINGUIBLE de inexistente.
        return DiaDAutoReplayDto(
            available=False, day=day, symbol=wanted, notes=["artifact_not_found"]
        )
    meta = artifact.get("meta") or {}
    raw_watch = meta.get("watch")
    watch = (
        [str(item).strip().upper() for item in raw_watch if str(item).strip()]
        if isinstance(raw_watch, list)
        else []
    )
    if watch != [wanted]:
        # El fichero existe pero no demuestra ESTE valor: se declara, no se sirve.
        return DiaDAutoReplayDto(
            available=False,
            day=day,
            symbol=wanted,
            notes=["value_mismatch"],
            meta=dict(meta),
        )

    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    except OSError:  # pragma: no cover — el fichero se acaba de leer
        modified = None
    return DiaDAutoReplayDto(
        available=True,
        readOnly=bool(artifact.get("readOnly", True)),
        day=str(artifact.get("day") or day),
        symbol=wanted,
        artifactModifiedAt=modified,
        schemaVersion=artifact.get("schemaVersion"),
        summary=DiaDAutoSummaryDto(**artifact["summary"]) if artifact.get("summary") else None,
        steps=[DiaDAutoStepDto(**row) for row in artifact.get("comparison", [])],
        oos=DiaDAutoOosDto(**artifact["oos"]) if artifact.get("oos") else None,
        meta=dict(meta),
        limits=list(artifact.get("limits", [])),
        executedDetail=dict(artifact.get("executedDetail") or {}),
        notes=[],
    )


# ── método DÍA-D as-run (ADR-049) ───────────────────────────────────────────


class DiaDAsRunArmDto(BaseModel):
    """Brazo medido o hueco declarado. ``measured=false`` ⇒ ``realizedR=null`` con motivo."""

    model_config = ConfigDict(populate_by_name=True)

    arm: str
    measured: bool
    reason: str | None = None
    realizedR: float | None = None
    pnlCurrency: float | None = None
    maeR: float | None = None
    mfeR: float | None = None
    capture: float | None = None
    #: Retorno porcentual: el benchmark ``market_bh`` solo publica esto (no tiene R).
    returnPct: float | None = None
    exits: int = 0
    stops: int = 0
    targets: int = 0
    legs: int = 0
    reasonCodes: list[str] = Field(default_factory=list)
    #: Decisiones declaradas del brazo (auditoría de la reproducción secuencial).
    decisions: list[dict[str, Any]] = Field(default_factory=list)


class DiaDAsRunDto(BaseModel):
    """Artefacto as-run de un día. ``available=false`` cuando no existe (fail-closed)."""

    model_config = ConfigDict(populate_by_name=True)

    available: bool
    readOnly: bool = True
    day: str
    #: ``measured`` | ``not_measured`` — un artefacto sin brazos medibles lo declara.
    status: str | None = None
    schemaVersion: str | None = None
    costBps: float | None = None
    startingState: dict[str, Any] = Field(default_factory=dict)
    arms: list[DiaDAsRunArmDto] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    hash: str | None = None
    artifactModifiedAt: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    #: Sobre de auditoría (congelación temporal, datos, versiones, decisiones).
    audit: dict[str, Any] | None = None
    #: Certificación del MÉTODO. Ausente en v1 ⇒ la ruta la calcula y sale ``not_certified``.
    certification: dict[str, Any] | None = None


class DiaDAsRunListDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    readOnly: bool = True
    days: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DiaDAsRunCreateDto(BaseModel):
    """Petición de replay as-run. ``day`` por defecto es hoy UTC (scheduler lo rellena)."""

    model_config = ConfigDict(populate_by_name=True)

    day: str | None = None
    to: str | None = None
    costBps: float | None = None
    engineStopMultiplier: float | None = None
    engineTargetMultiplier: float | None = None


class DiaDAsRunJobDto(BaseModel):
    """Foto mínima del job encolado: la UI observa estado y hueco, no inventa progreso."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: str
    status: str
    day: str
    created: bool = False


def _as_run_artifact_path(day: str, scope: str) -> Path:
    """Artefacto as-run de ``(cuenta, día)`` bajo la raíz ``…/dia-d-as-run``."""
    return as_run_artifact_path_in(_as_run_artifacts_dir(), day, scope)


def _list_as_run_days(scope: str) -> list[str]:
    """Días con artefacto as-run **para ``scope``**, descendente (aislado por cuenta)."""
    days: set[str] = set()
    account_dir = _as_run_artifacts_dir() / account_segment(scope)
    if not account_dir.is_dir():
        return []
    for entry in account_dir.iterdir():
        match = re.match(r"^as-run-(\d{4}-\d{2}-\d{2})\.json$", entry.name)
        if match and entry.is_file():
            days.add(match.group(1))
    return sorted(days, reverse=True)


@router.post("/auto/dia-d-as-run", response_model=DiaDAsRunJobDto)
async def create_auto_dia_d_as_run(
    body: DiaDAsRunCreateDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDAsRunJobDto:
    """Encola (o devuelve el activo) del replay as-run para la cuenta activa."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        raise HTTPException(
            status_code=404, detail="no_account_scope: no hay cuenta activa del principal"
        )
    payload: dict[str, Any] = {}
    if body.to:
        payload["to"] = body.to
    if body.costBps is not None:
        payload["costBps"] = float(body.costBps)
    if body.engineStopMultiplier is not None:
        payload["engineStopMultiplier"] = float(body.engineStopMultiplier)
    if body.engineTargetMultiplier is not None:
        payload["engineTargetMultiplier"] = float(body.engineTargetMultiplier)
    try:
        outcome = await EnqueueAutoOpsJob(
            SqlAlchemyAutoOpsJobRepository(session)
        ).execute_with_outcome(
            kind=JOB_KIND_DIA_D_AS_RUN,
            account_id=scope,
            day=body.day,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = outcome.job
    await session.commit()
    return DiaDAsRunJobDto(
        id=job.id,
        kind=job.kind,
        status=job.status,
        day=job.day,
        created=outcome.created,
    )


@router.get("/auto/dia-d-as-run", response_model=DiaDAsRunListDto)
async def list_auto_dia_d_as_run(
    request: Request,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDAsRunListDto:
    """Días con artefacto as-run DISPONIBLES PARA LA CUENTA (selector de fecha)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDAsRunListDto(days=[], notes=["no_account_scope"])
    days = _list_as_run_days(scope)
    notes = [] if days else ["no_artifacts"]
    return DiaDAsRunListDto(days=days, notes=notes)


@router.get("/auto/dia-d-as-run/{day}", response_model=DiaDAsRunDto)
async def get_auto_dia_d_as_run(
    request: Request,
    day: str,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDAsRunDto:
    """Artefacto as-run de ``day``, read-only y fail-closed por cuenta."""
    if not _DAY_RE.match(day):
        return DiaDAsRunDto(available=False, day=day, notes=["invalid_day"])
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDAsRunDto(available=False, day=day, notes=["no_account_scope"])

    path = _as_run_artifact_path(day, scope)
    artifact = _parse_artifact(path)
    # Una cuenta distinta es INDISTINGUIBLE de inexistente: no se revela que existe.
    if artifact is None or not _artifact_matches_scope(artifact, scope):
        return DiaDAsRunDto(available=False, day=day, notes=["artifact_not_found"])

    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    except OSError:  # pragma: no cover — el fichero se acaba de leer
        modified = None
    raw_arms = artifact.get("arms") or []
    arms = [
        DiaDAsRunArmDto(**row)
        for row in raw_arms
        if isinstance(row, dict) and row.get("arm")
    ]
    certification = artifact.get("certification")
    if not isinstance(certification, dict):
        # Un artefacto v1 no trae certificación: se calcula ahora y se declara lo que falte.
        # Certificar el método no certifica el resultado ni autoriza nada.
        certification = certify_artifact(artifact).to_dict()
    return DiaDAsRunDto(
        available=True,
        readOnly=True,
        day=str(artifact.get("day") or day),
        status=artifact.get("status"),
        schemaVersion=artifact.get("schemaVersion"),
        costBps=artifact.get("costBps"),
        startingState=dict(artifact.get("startingState") or {}),
        arms=arms,
        gaps=[row for row in (artifact.get("gaps") or []) if isinstance(row, dict)],
        hash=artifact.get("hash"),
        artifactModifiedAt=modified,
        meta=dict(artifact.get("meta") or {}),
        notes=[],
        audit=artifact.get("audit") if isinstance(artifact.get("audit"), dict) else None,
        certification=certification,
    )
