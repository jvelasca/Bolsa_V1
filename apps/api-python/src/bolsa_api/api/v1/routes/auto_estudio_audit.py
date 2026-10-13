"""API: AUTO · ESTUDIO — auditoría por VALOR (estrategia + porqué + señal + resultado).

`P2` (sello 2). Read-only: compone la auditoría por valor a partir de piezas **ya
calculadas** — el artefacto de feedback DÍA-D (R por valor + ciclos) y, si existe, el
artefacto financiero OOS por `(estrategia × instrumento)` (dinero) que emite el CLI OOS con
`--finance-report`. NO recalcula el motor (mismo modo de servicio que el feedback:
``PRECOMPUTED_ARTIFACT``).

Fail-closed por cuenta: sin cuenta visible del principal ⇒ ``available = false`` con
``no_account_scope``. Una ventana sin artefacto se declara ``available = false``; nunca se
rellena con ceros.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.api.dependencies import (
    get_account_id_header,
    resolve_account_scope_or_default,
)
from bolsa_api.api.v1.routes import auto_dia_d_feedback as feedback_routes
from bolsa_application.estudio_audit import build_estudio_audit_report

router = APIRouter()

#: Modo de servicio REAL (``P4-3``): artefacto precalculado por jobs offline; esta ruta no lo
#: recalcula en vivo (piezas: feedback DÍA-D + reporte financiero OOS opt-in).
SERVING_PRECOMPUTED_ARTIFACT = feedback_routes.SERVING_PRECOMPUTED_ARTIFACT


def _finance_artifact_path(window: str) -> Path:
    """Ruta del reporte financiero OOS de la ventana (``finance-<window>.json``), opt-in.

    Lo emite el CLI OOS con ``--finance-report``. Si NO existe, la mitad de **dinero** queda
    como hueco declarado («Sin dato todavía») — nunca se fabrica un grupo.
    """
    return feedback_routes._artifacts_dir() / f"finance-{window}.json"


def _read_finance_groups(window: str) -> list[dict[str, Any]]:
    path = _finance_artifact_path(window)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    groups = payload.get("groups")
    return [dict(row) for row in groups] if isinstance(groups, list) else []


class EstudioAuditStrategyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    presetKey: str | None = None
    version: str | None = None


class EstudioAuditWhyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    indicatorSpecs: list[Any] | None = None
    recommendations: list[Any] | None = None


class EstudioAuditSignalDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cycles: int = 0
    measuredCycles: int = 0
    daysCovered: int = 0


class EstudioAuditCycleDto(BaseModel):
    """Ciclo del valor con la clave canónica (``cycleId``) para enlazar con la operación."""

    model_config = ConfigDict(populate_by_name=True)

    cycleId: str
    entryDay: str | None = None
    exitDay: str | None = None
    strategyPresetKey: str | None = None
    strategyVersion: str | None = None
    realizedR: float | None = None


class EstudioAuditResultRDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    verdict: str = "NOT_MEASURED"
    verdictReason: str | None = None
    evidenceQuality: str = "NOT_MEASURED"
    expectancyR: float | None = None
    hitRate: float | None = None
    realizedRTotal: float | None = None
    measuredCycles: int = 0
    daysCovered: int = 0
    measured: bool = False
    sampleFloor: int = 0


class EstudioAuditMoneyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trades: int = 0
    netReturnPct: float | None = None
    netReturnPctAtStress: float | None = None
    maxDrawdownPct: float | None = None
    hitRate: float | None = None
    committedCapital: float | None = None
    measured: bool = False
    sampleFloor: int = 0


class EstudioAuditValueDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    strategy: EstudioAuditStrategyDto
    why: EstudioAuditWhyDto
    signal: EstudioAuditSignalDto
    cycles: list[EstudioAuditCycleDto] = Field(default_factory=list)
    resultR: EstudioAuditResultRDto
    money: EstudioAuditMoneyDto
    measured: bool = False
    unmeasured: list[str]


class EstudioAuditSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    values: int = 0
    measured: int = 0
    unmeasured: int = 0
    withPresetKey: int = 0
    withoutPresetKey: int = 0


class EstudioAuditReportDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kind: str
    readOnly: bool = True
    pointCitable: bool = False
    pointCitableReason: str
    summary: EstudioAuditSummaryDto
    values: list[EstudioAuditValueDto]
    notes: list[str]


class EstudioAuditDto(BaseModel):
    """Auditoría por valor de ESTUDIO. ``available = false`` cuando no hay artefacto."""

    model_config = ConfigDict(populate_by_name=True)

    available: bool
    readOnly: bool = True
    serving: str = SERVING_PRECOMPUTED_ARTIFACT
    window: str | None = None
    audit: EstudioAuditReportDto | None = None
    notes: list[str] = Field(default_factory=list)


def _compose(window: str, artifact: dict[str, Any]) -> EstudioAuditReportDto:
    report = build_estudio_audit_report(
        values=list(artifact.get("values") or []),
        cycles=list(artifact.get("cycles") or []),
        finance_groups=_read_finance_groups(window),
    )
    return EstudioAuditReportDto.model_validate(report.to_dict())


@router.get("/auto/estudio-audit", response_model=EstudioAuditDto)
async def get_auto_estudio_audit(
    request: Request,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> EstudioAuditDto:
    """Auditoría por valor de la ventana más reciente con artefacto (fail-closed por cuenta)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return EstudioAuditDto(available=False, notes=["no_account_scope"])
    for window in feedback_routes._list_windows():
        artifact = feedback_routes._read_artifact(window)
        if artifact is None or not feedback_routes._artifact_matches_scope(artifact, scope):
            continue
        return EstudioAuditDto(
            available=True,
            window=window,
            audit=_compose(window, artifact),
            notes=[],
        )
    return EstudioAuditDto(available=False, notes=["no_artifacts"])


@router.get("/auto/estudio-audit/{window}", response_model=EstudioAuditDto)
async def get_auto_estudio_audit_window(
    request: Request,
    window: str,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> EstudioAuditDto:
    """Auditoría por valor de una ventana concreta (``D0_D1``), read-only y fail-closed."""
    if not feedback_routes._WINDOW_RE.match(window):
        return EstudioAuditDto(available=False, notes=["invalid_window"])
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return EstudioAuditDto(available=False, notes=["no_account_scope"])
    artifact = feedback_routes._read_artifact(window)
    if artifact is None or not feedback_routes._artifact_matches_scope(artifact, scope):
        return EstudioAuditDto(available=False, notes=["artifact_not_found"])
    return EstudioAuditDto(
        available=True, window=window, audit=_compose(window, artifact), notes=[]
    )
