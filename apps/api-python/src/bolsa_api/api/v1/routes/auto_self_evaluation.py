"""API: autoevaluación AUTO-7 (lectura pura, read-only).

Expone el informe que agrega la cadena ``señal → decisión → ejecución → resultado`` por
versión de estrategia a partir de los fills SIM durables (``sim_fill_finance_context``,
con ``strategy_version_id`` y ``cycle_id``). NO es un permiso ni un ajuste de pesos: la
respuesta lleva ``readOnly = true`` y declara —campo a campo— qué bloques quedaron
``UNKNOWN``/``PARTIAL`` porque hoy no hay productor que los mida (R realizado, MAE/MFE,
slippage, embudo de oportunidades del día). Un hueco declarado NO es un cero.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)
from bolsa_application.auto_self_evaluation_feed import build_auto_self_evaluation
from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

router = APIRouter()


class AutoStrategySelfEvaluationDto(BaseModel):
    """Lectura de UNA versión de estrategia (lo medido + lo declarado como no medido)."""

    strategyVersion: str
    trades: int
    wins: int
    losses: int
    realizedPnl: str
    expectancyCurrency: str | None = None
    expectancyR: float | None = None
    netExpectancyR: float | None = None
    winRate: float | None = None
    profitFactor: float | None = None
    avgWinCurrency: str | None = None
    avgLossCurrency: str | None = None
    mfeR: float | None = None
    maeR: float | None = None
    slippageCurrency: str | None = None
    rejectionCostReturn: float | None = None
    drawdownCurrency: str
    drawdownShare: float | None = None
    funnel: dict[str, int] = Field(default_factory=dict)
    sampleQuality: str
    resultsMeasurement: str
    riskMeasurement: str
    netRMeasurement: str
    cyclesWithoutCost: int
    excursionsMeasurement: str
    slippageMeasurement: str
    rejectionCostMeasurement: str
    drawdownMeasurement: str
    decisive: bool
    notes: list[str] = Field(default_factory=list)


class AutoStrategyRegimeEvaluationDto(BaseModel):
    """AUTO-9 — celda ``strategyVersion × régime``: el R condicionado al mercado.

    ``regime == "UNKNOWN"`` es un cubo PROPIO (los ciclos que no declaran régimen), no un
    comodín. El embudo no viaja aquí: no tiene dimensión de régimen en el dato durable.
    """

    strategyVersion: str
    regime: str
    cycles: int
    wins: int
    losses: int
    realizedPnl: str
    expectancyR: float | None = None
    netExpectancyR: float | None = None
    winRate: float | None = None
    cyclesWithoutRisk: int
    cyclesWithoutCost: int
    rMeasurement: str
    netRMeasurement: str
    sampleQuality: str
    decisive: bool
    notes: list[str] = Field(default_factory=list)


class AutoSelfEvaluationDto(BaseModel):
    """Informe completo: roll-up + filas por versión + embudo + huecos declarados."""

    key: str
    readOnly: bool
    version: str | None = None
    cycles: int
    trades: int
    realizedPnl: str
    expectancyCurrency: str | None = None
    expectancyR: float | None = None
    winRate: float | None = None
    profitFactor: float | None = None
    slippageCurrency: str | None = None
    opportunityCostReturn: float | None = None
    opportunityCostMeasurement: str
    drawdownCurrency: str
    unattributedCycles: int
    unattributedPnl: str
    cyclesWithoutIdentity: int
    cyclesWithoutRegime: int
    duplicateCycles: int
    funnel: dict[str, Any] = Field(default_factory=dict)
    rejectionReasons: dict[str, int] = Field(default_factory=dict)
    byStrategy: list[AutoStrategySelfEvaluationDto] = Field(default_factory=list)
    byRegime: list[AutoStrategyRegimeEvaluationDto] = Field(default_factory=list)
    resultsMeasurement: str
    measurement: str
    decisive: bool
    errors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _to_dto(payload: dict[str, Any], *, version: str | None) -> AutoSelfEvaluationDto:
    return AutoSelfEvaluationDto(
        key=str(payload["key"]),
        readOnly=bool(payload["readOnly"]),
        version=version,
        cycles=int(payload["cycles"]),
        trades=int(payload["trades"]),
        realizedPnl=str(payload["realizedPnl"]),
        expectancyCurrency=payload["expectancyCurrency"],
        expectancyR=payload["expectancyR"],
        winRate=payload["winRate"],
        profitFactor=payload["profitFactor"],
        slippageCurrency=payload["slippageCurrency"],
        opportunityCostReturn=payload["opportunityCostReturn"],
        opportunityCostMeasurement=str(payload["opportunityCostMeasurement"]),
        drawdownCurrency=str(payload["drawdownCurrency"]),
        unattributedCycles=int(payload["unattributedCycles"]),
        unattributedPnl=str(payload["unattributedPnl"]),
        cyclesWithoutIdentity=int(payload["cyclesWithoutIdentity"]),
        cyclesWithoutRegime=int(payload["cyclesWithoutRegime"]),
        duplicateCycles=int(payload["duplicateCycles"]),
        funnel=payload["funnel"],
        rejectionReasons=payload["rejectionReasons"],
        byStrategy=[AutoStrategySelfEvaluationDto(**row) for row in payload["byStrategy"]],
        byRegime=[AutoStrategyRegimeEvaluationDto(**row) for row in payload["byRegime"]],
        resultsMeasurement=str(payload["resultsMeasurement"]),
        measurement=str(payload["measurement"]),
        decisive=bool(payload["decisive"]),
        errors=list(payload["errors"]),
        notes=list(payload["notes"]),
    )


@router.get("/auto/self-evaluation", response_model=AutoSelfEvaluationDto)
async def get_auto_self_evaluation(
    request: Request,
    version: Annotated[str, Query(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoSelfEvaluationDto:
    """Informe AUTO-7 de UNA versión de estrategia, desde los fills durables.

    La versión es OBLIGATORIA: el informe se agrega POR ``strategyVersion`` y devolver un
    roll-up de "todas" sin saber cuáles son sería una lectura incompleta disfrazada. El
    ``account_id`` (de la cabecera) acota la lectura a una cuenta visible del principal:
    sin cuenta operativa la respuesta es vacía (fail-closed), nunca global.
    """
    vid = str(version).strip()
    if not vid:
        return _to_dto(build_auto_self_evaluation().as_dict(), version=None)
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        # Sin cuenta visible del principal NO se lee global: se declara el hueco.
        payload = build_auto_self_evaluation().as_dict()
        payload["errors"] = ["no_account_scope"]
        return _to_dto(payload, version=vid)
    store = PostgresSimFillFinanceContextStore(session)
    fills = await store.list_for_strategy_version(vid, account_id=scope)
    payload = build_auto_self_evaluation(fills=fills).as_dict()
    return _to_dto(payload, version=vid)
