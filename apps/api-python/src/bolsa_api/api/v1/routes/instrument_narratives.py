"""API: narrativa corta de evolución por instrumento."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.schemas.instrument_narratives import (
    InstrumentNarrativeDto,
    InstrumentNarrativeResponseDto,
    UpsertInstrumentNarrativeDto,
)
from bolsa_application.instrument_narratives import (
    DeleteInstrumentNarrative,
    GetInstrumentNarrative,
    UpsertInstrumentNarrative,
)
from bolsa_infrastructure.database.repositories.instrument_narrative_repository import (
    InstrumentNarrativeRecord,
    SqlAlchemyInstrumentNarrativeRepository,
)

router = APIRouter()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _to_dto(row: InstrumentNarrativeRecord) -> InstrumentNarrativeDto:
    return InstrumentNarrativeDto(
        id=row.id,
        instrument_id=row.instrument_id,
        scope=row.scope,
        body=row.body,
        source=row.source,
        version=row.version,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


@router.get(
    "/instruments/{instrument_id}/narrative",
    response_model=InstrumentNarrativeResponseDto,
)
async def get_instrument_narrative(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    scope: Literal["estudio", "global", "trading"] = Query(default="estudio"),
) -> InstrumentNarrativeResponseDto:
    repo = SqlAlchemyInstrumentNarrativeRepository(session)
    row = await GetInstrumentNarrative(repo).execute(instrument_id, scope)
    return InstrumentNarrativeResponseDto(data=_to_dto(row) if row else None)


@router.put(
    "/instruments/{instrument_id}/narrative",
    response_model=InstrumentNarrativeResponseDto,
)
async def upsert_instrument_narrative(
    instrument_id: str,
    body: UpsertInstrumentNarrativeDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentNarrativeResponseDto:
    repo = SqlAlchemyInstrumentNarrativeRepository(session)
    try:
        row = await UpsertInstrumentNarrative(repo).execute(
            instrument_id=instrument_id,
            scope=body.scope,
            body=body.body,
            source=body.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InstrumentNarrativeResponseDto(data=_to_dto(row))


@router.delete(
    "/instruments/{instrument_id}/narrative",
    response_model=InstrumentNarrativeResponseDto,
)
async def delete_instrument_narrative(
    instrument_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    scope: Literal["estudio", "global", "trading"] = Query(default="estudio"),
) -> InstrumentNarrativeResponseDto:
    repo = SqlAlchemyInstrumentNarrativeRepository(session)
    ok = await DeleteInstrumentNarrative(repo).execute(instrument_id, scope)
    if not ok:
        return InstrumentNarrativeResponseDto(data=None)
    return InstrumentNarrativeResponseDto(data=None)
