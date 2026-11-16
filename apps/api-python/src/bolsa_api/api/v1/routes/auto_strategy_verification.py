"""API: verificación periódica de estrategia y ledger contrafactual (ADR-050).

Dos superficies, ambas **read-only sobre la operativa**:

* ``GET /auto/strategy-verification`` — perfil pre-registrado, último veredicto y runs.
* ``POST /auto/strategy-verification`` — recalcula el veredicto sobre las épocas con artefacto
  as-run disponible y **sella** el índice durable (``strategy_verification_runs``).
* ``GET /auto/strategy-verification/history`` — serie de runs para el historial.
* ``GET /auto/strategy-verification/ledger`` — ledger por operación de un día as-run,
  filtrable por instrumento, desenlace y calidad de decisión.

Invariantes:
* ``activationAllowed`` es siempre ``False``: el veredicto es advisory.
* Sin universo declarado no se emite perfil: se declara el hueco, no se inventa.
* Una época con solape no entra en el veredicto (lo decide el módulo de cadencia).
* El ledger distingue resultado (``win``/``loss``) de calidad de la decisión.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)
from bolsa_api.api.v1.routes.auto_dia_d import (
    _artifact_matches_scope,
    _as_run_artifact_path,
    _list_as_run_days,
    _parse_artifact,
)
from bolsa_application.dia_d_as_run import OUTCOMES, QUALITY_UNMEASURED
from bolsa_application.strategy_verification import (
    EpochMeasurement,
    artifact_measurement_hash,
    epoch_measurement_from_artifact,
    evaluate_verification,
    measurement_hash,
)
from bolsa_application.strategy_verification_cadence import VerificationEpoch
from bolsa_application.strategy_verification_profile import (
    StrategyVerificationProfileV1,
    VerificationCadence,
    VerificationProfileError,
    VerificationSamples,
)
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models.tables import SimAutoPositionRow
from bolsa_infrastructure.database.repositories.strategy_verification_repository import (
    SealedVerificationRunConflictError,
    SqlAlchemyStrategyVerificationRepository,
)

router = APIRouter()

_KIND_EPOCH = "epoch"
_KIND_ROLLING = "rolling"


class StrategyVerificationRecomputeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    every_days: int | None = Field(default=None, alias="everyDays")
    anchor_day: str | None = Field(default=None, alias="anchorDay")
    health_state: str | None = Field(default=None, alias="healthState")
    limit_days: int = Field(default=48, alias="limitDays", ge=1, le=400)


# ── contrato de respuesta (OpenAPI → schema.d.ts) ───────────────────────────


class StrategyVerificationCadenceDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: str
    everyDays: int
    anchorDay: str | None = None
    rollingEnabled: bool
    rollingLookbackDays: int


class StrategyVerificationSamplesDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    minCohortSamples: int
    minClosedCycles: int
    minPerInstrumentCycles: int
    epochsInVerdict: int


class StrategyVerificationCandidatePolicyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    requirePointInTime: bool
    measureForward: bool
    maxCandidates: int


class StrategyVerificationThresholdsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    minExcessMeanR: float
    minShareEpochsNotWorse: float
    maxDrawdownPct: float
    minHitRate: float | None = None
    maxEvidenceAgeDays: float | None = None


class StrategyVerificationDecisionPolicyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str
    watchOnInconclusive: bool
    relabOnArmDominance: bool
    allowAutoActivation: bool = False


class StrategyVerificationProfileDto(BaseModel):
    """Perfil pre-registrado: se hashea ANTES de medir y no autoriza operar."""

    model_config = ConfigDict(populate_by_name=True)

    version: str
    profileId: str
    accountScope: str
    universeInstruments: list[str]
    cadence: StrategyVerificationCadenceDto
    samples: StrategyVerificationSamplesDto
    arms: list[str]
    candidate: StrategyVerificationCandidatePolicyDto
    thresholds: StrategyVerificationThresholdsDto
    decision: StrategyVerificationDecisionPolicyDto
    execution: dict[str, Any] = Field(default_factory=dict)


class StrategyVerificationProfileResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    activationAllowed: bool = False
    profile: StrategyVerificationProfileDto | None = None
    profileHash: str | None = None
    notes: list[str] = Field(default_factory=list)


class StrategyVerificationGateDto(BaseModel):
    """Un gate. ``not_evaluated`` NUNCA equivale a ``pass``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    gate: str
    status: str
    reason: str | None = None


class StrategyVerificationEpochDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    epochId: str
    day: str
    toDay: str
    artifactHash: str
    measured: bool
    certified: bool
    armsR: dict[str, float | None] = Field(default_factory=dict)
    armsReturnPct: dict[str, float | None] = Field(default_factory=dict)
    closedCycles: int = 0
    operations: int = 0
    consistentDecisions: int = 0
    inconsistentDecisions: int = 0
    unrealizedR: float | None = None
    strategyVersion: str | None = None
    mandateVersion: str | None = None
    candidateMeasured: bool = False
    candidateReturnPct: float | None = None
    candidateGap: str | None = None
    certificationChecks: dict[str, str] = Field(default_factory=dict)


class StrategyVerificationVerdictDto(BaseModel):
    """Veredicto advisory completo: gates, muestras y números."""

    model_config = ConfigDict(populate_by_name=True)

    verdict: str
    activationAllowed: bool = False
    profileId: str
    profileHash: str
    gates: list[StrategyVerificationGateDto] = Field(default_factory=list)
    samples: int
    requiredSamples: int
    asRunMeanR: float | None = None
    bestArm: str | None = None
    bestArmMeanR: float | None = None
    meanExcessR: float | None = None
    shareEpochsNotWorse: float | None = None
    bootstrapLow: float | None = None
    candidateMeanReturnPct: float | None = None
    asRunMeanReturnPct: float | None = None
    epochs: list[StrategyVerificationEpochDto] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    measurementHash: str | None = None
    profile: StrategyVerificationProfileDto | None = None


class StrategyVerificationRunDto(BaseModel):
    """Run sellado en el índice durable (``strategy_verification_runs``)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    accountId: str
    profileId: str
    profileHash: str
    kind: str
    day: str
    toDay: str
    measurementHash: str
    verdict: str
    strategyVersion: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class StrategyVerificationOverviewDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    activationAllowed: bool = False
    latest: StrategyVerificationRunDto | None = None
    runs: list[StrategyVerificationRunDto] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StrategyVerificationRecomputeResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    activationAllowed: bool = False
    run: StrategyVerificationRunDto
    verdict: StrategyVerificationVerdictDto


class StrategyVerificationHistoryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    activationAllowed: bool = False
    kind: str
    runs: list[StrategyVerificationRunDto] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StrategyVerificationLedgerRowDto(BaseModel):
    """Fila del ledger por operación (``outcome`` ≠ ``decisionQuality``)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    arm: str
    instrumentId: str
    direction: str = "long"
    quantity: float = 0.0
    entryDay: str | None = None
    entryPrice: float = 0.0
    structuralStop: float | None = None
    target1: float | None = None
    target2: float | None = None
    riskPerUnit: float | None = None
    riskSource: str | None = None
    exitDay: str | None = None
    exitPrice: float | None = None
    exitReason: str | None = None
    deferred: bool = False
    daysHeld: int | None = None
    grossR: float | None = None
    netR: float | None = None
    pnlCurrency: float | None = None
    feesCurrency: float | None = None
    maeR: float | None = None
    mfeR: float | None = None
    capture: float | None = None
    outcome: str
    decisionQuality: str
    cycleId: str | None = None
    reasonCodes: list[str] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    day: str


class StrategyVerificationLedgerDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    activationAllowed: bool = False
    day: str
    rows: list[StrategyVerificationLedgerRowDto] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StrategyVerificationMeasurementHashDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool
    day: str | None = None
    measurementHash: str | None = None
    artifactHash: str | None = None
    notes: list[str] = Field(default_factory=list)


async def _declared_universe(session: AsyncSession, *, account_id: str) -> tuple[str, ...]:
    """Universo declarado: los símbolos que la cuenta tiene vivos AHORA.

    Es la única fuente honesta disponible sin un snapshot histórico de watchlist. Sin
    posiciones se devuelve vacío y el perfil no se emite (``no_declared_universe``).
    """
    rows = (
        await session.execute(
            select(SimAutoPositionRow.symbol).where(
                SimAutoPositionRow.account_id == account_id,
                SimAutoPositionRow.quantity > 0,
            )
        )
    ).all()
    return tuple(sorted({str(row[0]) for row in rows if row[0]}))


def _profile_from_settings(
    *, account_id: str, universe: tuple[str, ...], every_days: int | None, anchor: str | None
) -> StrategyVerificationProfileV1:
    settings = get_settings()
    return StrategyVerificationProfileV1(
        profile_id="default",
        account_scope=account_id,
        universe_instruments=universe,
        cadence=VerificationCadence(
            every_days=int(
                every_days
                if every_days is not None
                else getattr(settings, "strategy_verification_every_days", 30)
            ),
            anchor_day=anchor,
            rolling_enabled=bool(
                getattr(settings, "strategy_verification_rolling_enabled", True)
            ),
            rolling_lookback_days=int(
                getattr(settings, "strategy_verification_rolling_lookback_days", 1)
            ),
        ),
        samples=VerificationSamples(),
    )


def _epoch_measurement_payload(epoch: EpochMeasurement) -> dict[str, Any]:
    """Medición de la época sin la huella del artefacto (que incluye ``meta.generatedAt``)."""
    body = epoch.to_dict()
    body.pop("artifactHash", None)
    return body


def _collect_epochs(*, scope: str, limit: int) -> list[EpochMeasurement]:
    """Épocas con artefacto as-run propio, sin solape, en orden temporal."""
    days = sorted(_list_as_run_days(scope)[: max(1, int(limit))])
    epochs: list[EpochMeasurement] = []
    previous_to: str | None = None
    for index, day in enumerate(days):
        artifact = _parse_artifact(_as_run_artifact_path(day, scope))
        if artifact is None or not _artifact_matches_scope(artifact, scope):
            continue
        to_day = str(artifact.get("toDay") or day)[:10]
        if to_day <= day:
            continue
        if previous_to is not None and day < previous_to:
            # Solape con la época anterior: se descarta, nunca se cuenta dos veces.
            continue
        epoch = VerificationEpoch(
            epoch_id=f"epoch:{day}",
            index=index,
            day=day,
            to_day=to_day,
            status="closed",
        )
        epochs.append(epoch_measurement_from_artifact(artifact, epoch=epoch))
        previous_to = to_day
    return epochs


@router.get(
    "/auto/strategy-verification/profile",
    response_model=StrategyVerificationProfileResponseDto,
)
async def get_strategy_verification_profile(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> StrategyVerificationProfileResponseDto:
    """Perfil activo (pre-registrado) o el hueco declarado si falta el universo."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return StrategyVerificationProfileResponseDto(
            available=False, notes=["no_account_scope"]
        )
    universe = await _declared_universe(session, account_id=scope)
    if not universe:
        return StrategyVerificationProfileResponseDto(
            available=False, notes=["no_declared_universe"]
        )
    profile = _profile_from_settings(
        account_id=scope, universe=universe, every_days=None, anchor=None
    )
    return StrategyVerificationProfileResponseDto(
        available=True,
        profile=StrategyVerificationProfileDto(**profile.to_dict()),
        profileHash=profile.hash(),
        notes=[],
    )


@router.get("/auto/strategy-verification", response_model=StrategyVerificationOverviewDto)
async def get_strategy_verification(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> StrategyVerificationOverviewDto:
    """Último veredicto sellado y runs recientes (historial de épocas)."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return StrategyVerificationOverviewDto(
            available=False, notes=["no_account_scope"]
        )
    repo = SqlAlchemyStrategyVerificationRepository(session)
    latest = await repo.latest(account_id=scope, profile_id="default")
    runs = await repo.list_runs(account_id=scope, profile_id="default", limit=120)
    return StrategyVerificationOverviewDto(
        available=latest is not None,
        latest=None if latest is None else StrategyVerificationRunDto(**latest.to_dict()),
        runs=[StrategyVerificationRunDto(**run.to_dict()) for run in runs],
        notes=[] if latest is not None else ["no_verification_runs"],
    )


@router.post(
    "/auto/strategy-verification",
    response_model=StrategyVerificationRecomputeResponseDto,
)
async def recompute_strategy_verification(
    body: StrategyVerificationRecomputeDto,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> StrategyVerificationRecomputeResponseDto:
    """Recalcula el veredicto sobre las épocas medidas y lo sella en el índice durable."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="no_account_scope: sin cuenta del principal")
    universe = await _declared_universe(session, account_id=scope)
    if not universe:
        raise HTTPException(
            status_code=409,
            detail="no_declared_universe: se declara el hueco, no se inventa el universo",
        )
    try:
        profile = _profile_from_settings(
            account_id=scope,
            universe=universe,
            every_days=body.every_days,
            anchor=body.anchor_day,
        )
    except VerificationProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    epochs = _collect_epochs(scope=scope, limit=body.limit_days)
    if not epochs:
        raise HTTPException(
            status_code=409,
            detail="no_measured_epochs: no hay artefactos as-run para construir la cohorte",
        )
    health_state = str(body.health_state or "").strip()
    health = {"state": health_state} if health_state else None
    verdict = evaluate_verification(
        epochs, profile=profile, today=datetime.now(UTC).date().isoformat(), health=health
    )
    day = epochs[0].day
    to_day = epochs[-1].to_day
    payload = verdict.to_dict()
    payload["profile"] = profile.to_dict()
    payload["measurementHash"] = measurement_hash(
        {
            "profileHash": profile.hash(),
            "epochs": [_epoch_measurement_payload(epoch) for epoch in epochs],
        }
    )
    repo = SqlAlchemyStrategyVerificationRepository(session)
    try:
        run = await repo.upsert_run(
            account_id=scope,
            profile_id=profile.profile_id,
            profile_hash=profile.hash(),
            kind=_KIND_EPOCH,
            day=day,
            to_day=to_day,
            measurement_hash=payload["measurementHash"],
            verdict=verdict.verdict,
            strategy_version=next(
                (epoch.strategy_version for epoch in epochs if epoch.strategy_version), None
            ),
            payload=payload,
        )
    except SealedVerificationRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return StrategyVerificationRecomputeResponseDto(
        available=True,
        run=StrategyVerificationRunDto(**run.to_dict()),
        verdict=StrategyVerificationVerdictDto(**payload),
    )


@router.get(
    "/auto/strategy-verification/history",
    response_model=StrategyVerificationHistoryDto,
)
async def list_strategy_verification_history(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
    kind: str = Query(default=_KIND_EPOCH),
    limit: int = Query(default=120, ge=1, le=400),
) -> StrategyVerificationHistoryDto:
    """Historial de runs (orden temporal ascendente) para dibujar la serie."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return StrategyVerificationHistoryDto(
            available=False, kind=kind, notes=["no_account_scope"]
        )
    if kind not in (_KIND_EPOCH, _KIND_ROLLING):
        raise HTTPException(status_code=400, detail=f"kind no soportado: {kind!r}")
    repo = SqlAlchemyStrategyVerificationRepository(session)
    runs = await repo.list_runs(account_id=scope, kind=kind, limit=limit)
    return StrategyVerificationHistoryDto(
        available=bool(runs),
        kind=kind,
        runs=[StrategyVerificationRunDto(**run.to_dict()) for run in runs],
        notes=[] if runs else ["no_verification_runs"],
    )


@router.get(
    "/auto/strategy-verification/ledger",
    response_model=StrategyVerificationLedgerDto,
)
async def get_strategy_verification_ledger(
    request: Request,
    day: str,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
    arm: str | None = Query(default=None),
    instrument: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    quality: str | None = Query(default=None),
) -> StrategyVerificationLedgerDto:
    """Ledger por operación del día as-run, filtrable (resultado ≠ calidad de decisión)."""
    if outcome is not None and outcome not in OUTCOMES:
        raise HTTPException(status_code=400, detail=f"outcome no soportado: {outcome!r}")
    if quality is not None and quality not in (
        "consistent",
        "inconsistent",
        QUALITY_UNMEASURED,
    ):
        raise HTTPException(status_code=400, detail=f"quality no soportada: {quality!r}")
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return StrategyVerificationLedgerDto(
            available=False, day=day, notes=["no_account_scope"]
        )
    artifact = _parse_artifact(_as_run_artifact_path(day, scope))
    if artifact is None or not _artifact_matches_scope(artifact, scope):
        return StrategyVerificationLedgerDto(
            available=False, day=day, notes=["artifact_not_found"]
        )

    rows: list[StrategyVerificationLedgerRowDto] = []
    for raw_arm in artifact.get("arms") or ():
        if not isinstance(raw_arm, dict):
            continue
        arm_name = str(raw_arm.get("arm") or "")
        if not arm_name or (arm is not None and arm_name != arm):
            continue
        for row in raw_arm.get("ledger") or ():
            if not isinstance(row, dict):
                continue
            if instrument is not None and row.get("instrumentId") != instrument:
                continue
            if outcome is not None and row.get("outcome") != outcome:
                continue
            if quality is not None and row.get("decisionQuality") != quality:
                continue
            rows.append(StrategyVerificationLedgerRowDto(**{**row, "day": day}))
    return StrategyVerificationLedgerDto(
        available=True,
        day=day,
        rows=rows,
        notes=[] if rows else ["no_ledger_rows"],
    )


@router.get(
    "/auto/strategy-verification/measurement-hash",
    response_model=StrategyVerificationMeasurementHashDto,
)
async def get_strategy_verification_measurement_hash(
    day: str,
    request: Request,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> StrategyVerificationMeasurementHashDto:
    """Huella de MEDICIÓN del artefacto (sin ``meta.generatedAt``): reproducible entre rejuegos."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return StrategyVerificationMeasurementHashDto(
            available=False, notes=["no_account_scope"]
        )
    artifact = _parse_artifact(_as_run_artifact_path(day, scope))
    if artifact is None or not _artifact_matches_scope(artifact, scope):
        return StrategyVerificationMeasurementHashDto(
            available=False, notes=["artifact_not_found"]
        )
    return StrategyVerificationMeasurementHashDto(
        available=True,
        day=day,
        measurementHash=artifact_measurement_hash(artifact),
        artifactHash=artifact.get("hash"),
    )
