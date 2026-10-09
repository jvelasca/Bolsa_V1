"""API: evidencia durable PAPER (PAPER-2) — read-only, account-scoped.

Expone ``GET /api/auto/paper-evidence``: los **siete criterios** del contrato PAPER evaluados
sobre el material durable **conciliado** (operaciones, ejecuciones, cierres, costes y
resultados), con la procedencia de cada cifra y los huecos declarados.

Read-only (``readOnly = true``): no escribe, no toca el motor de decisión y **nunca** emite la
confirmación: ``verdict`` es el literal ``"NO_CONFIRMED"``. Un dato ausente viaja ``null`` con su
medición ``UNKNOWN``; jamás un ``0`` de relleno. Sin cuenta operativa visible la respuesta es el
DTO vacío con ``no_account_scope`` (fail-closed, nunca global).

@see docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md
@see packages/py/application/src/bolsa_application/paper_evidence_reader.py
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
from bolsa_application.paper_evidence_protocol import (
    PAPER_EVIDENCE_SNAPSHOT_EVENT,
    build_paper_evidence_snapshot_entry,
    paper_evidence_series,
)
from bolsa_application.paper_evidence_reader import (
    empty_paper_evidence,
    read_paper_evidence,
)

router = APIRouter()


class PaperEvidenceCriterionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    #: ``met`` | ``unmet`` | ``unknown`` (sin dato todavía). ``unknown`` NO es ``0``.
    status: str
    measurement: str
    #: Origen durable que demuestra el criterio (tabla/evento), en lenguaje de usuario.
    source: str
    #: Contadores nullable: ``None`` = no medido (nunca un ``0`` de relleno).
    counts: dict[str, int | None] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class PaperEvidenceCycleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cycleId: str
    strategyVersion: str | None = None
    fills: int
    buyQty: str | None = None
    sellQty: str | None = None
    bothSides: bool
    balanced: bool
    closed: bool
    fifoPnl: str | None = None
    settlementPresent: bool
    settlementPnl: str | None = None
    settlementPnlMeasurement: str
    settlementClosedQty: str | None = None
    reconciled: bool
    costMeasurement: str
    costComplete: bool
    notes: list[str] = Field(default_factory=list)


class PaperEvidenceReconciliationDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fillsLoaded: bool
    settlementsLoaded: bool
    fillsTotal: int
    fillsWithCycle: int
    duplicateExecutions: int
    orphanExecutions: int
    closedCycles: int
    anonymousClosedCycles: int
    windowDays: int | None = None
    windowEpisodes: int | None = None
    settlementsTotal: int
    settlementsReconciled: int
    settlementsDivergent: int
    settlementsUnmatched: int
    cycles: list[PaperEvidenceCycleDto] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PaperEvidencePerVersionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    strategyVersion: str
    closedOperations: int
    reconciledClosures: int
    measuredResults: int
    completeCosts: int
    meetsMinimum: bool


class AutoPaperEvidenceDto(BaseModel):
    """DTO canónico de la evidencia PAPER: siete criterios + conciliación + desglose."""

    model_config = ConfigDict(populate_by_name=True)

    schemaVersion: str
    readOnly: bool
    accountId: str | None = None
    asOf: str | None = None
    #: Tipo LITERAL por contrato: no existe rama que emita la confirmación.
    verdict: str
    criteria: list[PaperEvidenceCriterionDto]
    metCriterionIds: list[str] = Field(default_factory=list)
    unmetCriterionIds: list[str] = Field(default_factory=list)
    unknownCriterionIds: list[str] = Field(default_factory=list)
    unmetOrUnmeasuredCriterionIds: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    perVersion: list[PaperEvidencePerVersionDto] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    fillsWindowFull: bool
    fillsTotalForAccount: int | None = None
    reconciliation: PaperEvidenceReconciliationDto


@router.get("/auto/paper-evidence", response_model=AutoPaperEvidenceDto)
async def get_auto_paper_evidence(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    strategy_version: Annotated[
        list[str] | None, Query(alias="strategyVersion", max_length=128)
    ] = None,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> AutoPaperEvidenceDto:
    """Evidencia PAPER durable de la cuenta visible del principal (read-only).

    ``strategyVersion`` acota el desglose por estrategia (repetible); sin él se usan las versiones
    que declara el propio material. Sin cuenta visible devuelve el DTO vacío con ``no_account_scope``.
    """
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return AutoPaperEvidenceDto(
            **empty_paper_evidence("", strategy_version, note="no_account_scope")
        )
    payload: dict[str, Any] = await read_paper_evidence(
        session, scope, versions=strategy_version
    )
    return AutoPaperEvidenceDto(**payload)


class PaperEvidenceSnapshotDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    snapshotId: str | None = None
    asOf: str | None = None
    #: Literal reservado: el protocolo NUNCA promueve.
    verdict: str = "NO_CONFIRMED"
    metCount: int = 0
    unmetCount: int = 0
    unknownCount: int = 0
    metCriterionIds: list[str] = Field(default_factory=list)
    unmetCriterionIds: list[str] = Field(default_factory=list)
    unknownCriterionIds: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    fillsWindowFull: bool = False
    fillsTotalForAccount: int | None = None


class PaperEvidenceHistoryDto(BaseModel):
    """Serie longitudinal PAPER (read-only): snapshots durables, más antiguo → más nuevo."""

    model_config = ConfigDict(populate_by_name=True)

    readOnly: bool
    accountId: str | None = None
    #: Literal reservado por contrato: ninguna rama de este protocolo emite la confirmación.
    verdict: str = "NO_CONFIRMED"
    snapshots: list[PaperEvidenceSnapshotDto] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PaperEvidenceSnapshotRecordedDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recorded: bool
    accountId: str | None = None
    asOf: str | None = None
    verdict: str = "NO_CONFIRMED"
    note: str | None = None


async def _journal_entries_for_snapshots(
    session: AsyncSession, account_id: str, limit: int
) -> tuple[list[Any], int]:
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    return await SqlAlchemyJournalRepository(session).list_entries(
        account_id=account_id,
        event_type=PAPER_EVIDENCE_SNAPSHOT_EVENT,
        limit=limit,
    )


@router.get("/auto/paper-evidence/history", response_model=PaperEvidenceHistoryDto)
async def get_auto_paper_evidence_history(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> PaperEvidenceHistoryDto:
    """Serie longitudinal PAPER durable (read-only, acotada por cuenta).

    Solo lee los snapshots ``auto_paper_evidence_snapshot`` del spine (``decision_journal_entries``)
    y los ordena. Una cuenta sin snapshots devuelve serie vacía con ``NO_CONFIRMED`` (fail-closed,
    sin inventar hitos).
    """
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return PaperEvidenceHistoryDto(readOnly=True, accountId=None, notes=["no_account_scope"])
    entries, _total = await _journal_entries_for_snapshots(session, scope, limit)
    series = paper_evidence_series(entries)
    return PaperEvidenceHistoryDto(
        readOnly=True,
        accountId=scope,
        snapshots=[PaperEvidenceSnapshotDto(**row) for row in series],
    )


@router.post("/auto/paper-evidence/snapshot", response_model=PaperEvidenceSnapshotRecordedDto)
async def post_auto_paper_evidence_snapshot(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> PaperEvidenceSnapshotRecordedDto:
    """Registra UNA foto durable de la evidencia PAPER del día (driver de la serie longitudinal).

    NO es el GET read-only: esta ruta **escribe** la traza del protocolo. La separación es
    deliberada — ``GET /auto/paper-evidence`` declara ``readOnly = true`` y no puede escribir. La
    identidad ``(cuenta, día)`` es idempotente: repetir la foto del mismo día no duplica ni pisa la
    primera. El ``verdict`` es el literal reservado ``NO_CONFIRMED``; la promoción es humana.
    """
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return PaperEvidenceSnapshotRecordedDto(
            recorded=False, accountId=None, note="no_account_scope"
        )
    payload: dict[str, Any] = await read_paper_evidence(session, scope)
    entry = build_paper_evidence_snapshot_entry(account_id=scope, evidence=payload)
    if entry is None:
        return PaperEvidenceSnapshotRecordedDto(
            recorded=False, accountId=scope, note="no_snapshot_identity"
        )
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)
    try:
        await repository.append(entry)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return PaperEvidenceSnapshotRecordedDto(
        recorded=True,
        accountId=scope,
        asOf=str((entry.payload or {}).get("asOf") or "") or None,
    )
