"""API: TOP-3 estrategias AT por instrumento (embudo coach)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from bolsa_application.instrument_strategy_tops import (
    DeleteInstrumentStrategyTop,
    GetInstrumentStrategyTop,
    UpsertInstrumentStrategyTop,
)
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    InstrumentStrategyTopRecord,
    SqlAlchemyInstrumentStrategyTopRepository,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.schemas.instrument_strategy_tops import (
    InstrumentStrategyTopDto,
    InstrumentStrategyTopResponseDto,
    InstrumentStrategyTopsListResponseDto,
    InstrumentStrategyTopSlotDto,
    QueryInstrumentStrategyTopsDto,
    UpsertInstrumentStrategyTopDto,
)

router = APIRouter()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _slot_to_dto(raw: dict[str, Any]) -> InstrumentStrategyTopSlotDto:
    return InstrumentStrategyTopSlotDto.model_validate(raw)


def _to_dto(row: InstrumentStrategyTopRecord) -> InstrumentStrategyTopDto:
    return InstrumentStrategyTopDto(
        id=row.id,
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        timeframe=row.timeframe,
        period_label=row.period_label,
        status=row.status,  # type: ignore[arg-type]
        version=row.version,
        evidence_level=row.evidence_level,  # type: ignore[arg-type]
        slots=[_slot_to_dto(s) for s in row.slots],
        coach_headline=row.coach_headline,
        coach_facts=row.coach_facts,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _slot_to_dict(slot: InstrumentStrategyTopSlotDto) -> dict[str, Any]:
    return slot.model_dump(by_alias=True, exclude_none=False)


@router.get(
    "/instruments/{instrument_id}/strategy-top",
    response_model=InstrumentStrategyTopResponseDto,
)
async def get_instrument_strategy_top(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    timeframe: str = Query(default="1d"),
) -> InstrumentStrategyTopResponseDto:
    repo = SqlAlchemyInstrumentStrategyTopRepository(session)
    row = await GetInstrumentStrategyTop(repo).execute(instrument_id, timeframe)
    return InstrumentStrategyTopResponseDto(data=_to_dto(row) if row else None)


@router.post(
    "/instrument-strategy-tops/query",
    response_model=InstrumentStrategyTopsListResponseDto,
)
async def query_instrument_strategy_tops(
    body: QueryInstrumentStrategyTopsDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentStrategyTopsListResponseDto:
    """Batch: TOPs de varios instrumentos (resumen Lista en Backtesting)."""
    repo = SqlAlchemyInstrumentStrategyTopRepository(session)
    # Dedup preservando orden
    seen: set[str] = set()
    ids: list[str] = []
    for raw in body.instrument_ids:
        iid = (raw or "").strip()
        if not iid or iid in seen:
            continue
        seen.add(iid)
        ids.append(iid)
        if len(ids) >= 200:
            break
    rows = await repo.list_for_instruments(ids, body.timeframe or "1d")
    return InstrumentStrategyTopsListResponseDto(data=[_to_dto(r) for r in rows])


@router.put(
    "/instruments/{instrument_id}/strategy-top",
    response_model=InstrumentStrategyTopResponseDto,
)
async def upsert_instrument_strategy_top(
    instrument_id: str,
    body: UpsertInstrumentStrategyTopDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentStrategyTopResponseDto:
    if body.instrument_id != instrument_id:
        raise HTTPException(status_code=400, detail="instrumentId del body no coincide con la ruta")
    if not (1 <= len(body.slots) <= 3):
        raise HTTPException(status_code=400, detail="slots debe tener entre 1 y 3 entradas")
    ranks = sorted(s.rank for s in body.slots)
    if ranks != list(range(1, len(body.slots) + 1)):
        raise HTTPException(status_code=400, detail="ranks deben ser 1..N consecutivos")
    repo = SqlAlchemyInstrumentStrategyTopRepository(session)
    try:
        row = await UpsertInstrumentStrategyTop(repo).execute(
            instrument_id=instrument_id,
            timeframe=body.timeframe,
            slots=[_slot_to_dict(s) for s in body.slots],
            symbol=body.symbol,
            period_label=body.period_label,
            status=body.status,
            evidence_level=body.evidence_level,
            coach_headline=body.coach_headline,
            coach_facts=body.coach_facts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InstrumentStrategyTopResponseDto(data=_to_dto(row))


@router.delete(
    "/instruments/{instrument_id}/strategy-top",
    response_model=dict,
)
async def delete_instrument_strategy_top(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    timeframe: str = Query(default="1d"),
) -> dict[str, bool]:
    repo = SqlAlchemyInstrumentStrategyTopRepository(session)
    ok = await DeleteInstrumentStrategyTop(repo).execute(instrument_id, timeframe)
    if not ok:
        raise HTTPException(status_code=404, detail="TOP no encontrado")
    return {"ok": True}
