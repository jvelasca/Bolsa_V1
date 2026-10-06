"""API: AUTO Operational Monitor (M1) — espejo read-only de la cadena AUTO.

Expone ``GET /api/auto/operational-monitor``: la proyección canónica de la cadena
``SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL → PROTECTION → SETTLEMENT →
CYCLE CLOSED`` sobre el estado DURABLE (``portfolio_reservations``, ``auto_exit_orders``,
``sim_fill_finance_context``, ``sim_auto_positions``, ``auto_engine_runs/ticks`` y el spine
``decision_journal_entries``), más el panel de ownership de reservas y el de concurrencia.

Read-only: ``readOnly = true`` y no escribe nada. La UI pinta el DTO tal cual: no interpreta
ni re-deriva. Un paso sin traza durable viaja ``unknown``/``absent`` con su ``measurement``;
un valor no medido viaja ``null``, NUNCA un ``0`` de relleno.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)
from bolsa_application.auto_operational_monitor import (
    build_operational_monitor,
    read_operational_monitor,
)

router = APIRouter()


class AutoMonitorFactDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    value: Any = None
    measurement: str


class AutoMonitorStepDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    state: str
    at: str | None = None
    measurement: str
    facts: list[AutoMonitorFactDto] = Field(default_factory=list)
    note: str | None = None


class AutoMonitorCycleResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pnl: Any = None
    closedAt: str | None = None


class AutoMonitorCycleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cycleId: str
    instrumentId: str | None = None
    strategyVersion: str | None = None
    direction: str = "long"
    # ``closed`` es nullable: con la ventana de fills truncada no se puede AFIRMAR el cierre.
    # ``None`` + ``closedMeasurement`` (PARTIAL/UNKNOWN) declara el hueco; la UI lo rotula.
    closed: bool | None = None
    closedMeasurement: str = "UNKNOWN"
    steps: list[AutoMonitorStepDto] = Field(default_factory=list)
    result: AutoMonitorCycleResultDto | None = None
    notes: list[str] = Field(default_factory=list)


class AutoMonitorFillProgressDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    filled: Any = None
    requested: Any = None
    measurement: str


class AutoMonitorReconciliationDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    at: str | None = None
    caller: str | None = None
    decision: str | None = None
    reason: str | None = None
    aged: Any = None
    graceWindowSeconds: Any = None
    # Medición DECLARADA de cada campo (COMPLETE/PARTIAL/UNKNOWN): sin ella la UI no puede
    # distinguir un valor NO MEDIDO de un valor vacío. Nunca se asume COMPLETE por defecto.
    reasonMeasurement: str = "UNKNOWN"
    callerMeasurement: str = "UNKNOWN"
    agedMeasurement: str = "UNKNOWN"
    graceWindowMeasurement: str = "UNKNOWN"
    reconciliationMeasurement: str = "UNKNOWN"


class AutoMonitorReservationDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reservationId: str
    instrumentId: str | None = None
    side: str | None = None
    quantity: Any = None
    remainingQty: Any = None
    ownerSession: str | None = None
    ownerMeasurement: str
    created: str | None = None
    expires: str | None = None
    expiresMeasurement: str
    state: str
    releaseReason: str | None = None
    releaseReasonMeasurement: str
    fillProgress: AutoMonitorFillProgressDto
    reconciliations: list[AutoMonitorReconciliationDto] = Field(default_factory=list)


class AutoMonitorConcurrencyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    activeSessions: int | None = None
    activeSessionsMeasurement: str
    heartbeatsPersisted: int = 0
    claimAttempts: int | None = None
    claimAttemptsMeasurement: str
    successfulClaims: int | None = None
    successfulClaimsMeasurement: str
    lostClaims: int | None = None
    lostClaimsMeasurement: str
    raceConflicts: int | None = None
    raceConflictsMeasurement: str
    reconciliations: int | None = None
    reconciliationsMeasurement: str
    graceWindowKeeps: int | None = None
    graceWindowKeepsMeasurement: str
    forcedReleases: int = 0
    forcedReleasesMeasurement: str
    lastConflict: Any = None
    lastConflictMeasurement: str


class AutoMonitorHeaderDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    engineId: str | None = None
    state: str = "UNKNOWN"
    venue: str = "paper"
    granularity: dict[str, Any] = Field(default_factory=dict)
    decisionClock: str = "CLOSED BAR"
    executionDeclared: str | None = None
    executionEnabled: bool | None = None
    protectionModel: str | None = None
    heartbeatSeconds: float | None = None
    graceSeconds: float | None = None
    lastHeartbeatAt: str | None = None
    lastHeartbeatMeasurement: str = "UNKNOWN"
    lastDecisionAt: str | None = None
    lastDecisionMeasurement: str = "UNKNOWN"
    nextDecisionAt: str | None = None
    currentActivity: str | None = None
    currentActivityMeasurement: str = "UNKNOWN"
    currentActivityAt: str | None = None
    currentActivityAtMeasurement: str = "UNKNOWN"
    realPriceEnabled: bool = False
    heartbeatsPersisted: int = 0
    asOf: str


class AutoOperationalMonitorDto(BaseModel):
    """DTO canónico del monitor: header + ciclos + reservas + concurrencia + huecos."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    readOnly: bool
    accountId: str | None = None
    asOf: str
    header: AutoMonitorHeaderDto
    cycles: list[AutoMonitorCycleDto] = Field(default_factory=list)
    reservations: list[AutoMonitorReservationDto] = Field(default_factory=list)
    concurrency: AutoMonitorConcurrencyDto
    notes: list[str] = Field(default_factory=list)


def _timing_context() -> tuple[float, float]:
    """``(interval_seconds, grace_seconds)`` derivados de la MISMA política del worker.

    Se importa perezosamente para no arrastrar el worker completo (y su coste) al importar la
    ruta. Sin worker disponible, los defaults declarados (60 s / 61 s) mantienen la forma.
    """
    try:
        from bolsa_api.background.auto_simulation_worker import (
            _sim_interval_seconds,
            reservation_grace_window,
        )

        interval = float(_sim_interval_seconds())
        return interval, reservation_grace_window(interval).total_seconds()
    except Exception:  # noqa: BLE001 — sin política resoluble se declaran los defaults.
        return 60.0, 61.0


@router.get("/auto/operational-monitor", response_model=AutoOperationalMonitorDto)
async def get_auto_operational_monitor(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    cycle_id: Annotated[str | None, Query(alias="cycleId", max_length=128)] = None,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoOperationalMonitorDto:
    """Proyección read-only de la cadena AUTO de una cuenta visible del principal.

    Sin cuenta operativa visible la respuesta es un DTO vacío con ``no_account_scope``
    (fail-closed, nunca global). ``cycleId`` acota a un solo ciclo para el drill-down.
    """
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        payload = build_operational_monitor(account_id="", cycle_id=cycle_id)
        payload["notes"] = ["no_account_scope", *payload["notes"]]
        return AutoOperationalMonitorDto(**payload)
    interval_seconds, grace_seconds = _timing_context()
    payload = await read_operational_monitor(
        session,
        scope,
        limit=limit,
        cycle_id=cycle_id,
        interval_seconds=interval_seconds,
        grace_seconds=grace_seconds,
    )
    return AutoOperationalMonitorDto(**payload)
