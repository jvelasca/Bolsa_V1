"""API: TOP3 de oportunidades (activos) cross-asset — read-only.

Expone ``GET /api/v1/top3-opportunities/latest`` y ``GET /api/v1/top3-opportunities/{run_id}``:
la foto durable de «qué 3 activos decidió AUTO y por qué» (migración 052). Read-only: no
escribe ni deriva; la UI pinta el DTO tal cual (``assetId``, ``score``, ``components``,
``regime`` y ``reasons``).
"""

from __future__ import annotations

from typing import Annotated, Any

from bolsa_infrastructure.database.repositories.top3_opportunity_repository import (
    SqlAlchemyTop3OpportunityRepository,
    Top3OpportunityRowRecord,
)
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.schemas.mappers import to_iso

router = APIRouter()


class Top3OpportunityDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    runId: str
    rank: int
    assetId: str
    score: float
    components: dict[str, Any] = Field(default_factory=dict)
    regime: str | None = None
    reasons: list[str] = Field(default_factory=list)
    createdAt: str


class Top3OpportunitiesResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    runId: str
    items: list[Top3OpportunityDto] = Field(default_factory=list)


def _to_dto(row: Top3OpportunityRowRecord) -> Top3OpportunityDto:
    return Top3OpportunityDto(
        runId=row.run_id,
        rank=row.rank,
        assetId=row.asset_id,
        score=row.combined,
        components=dict(row.components),
        regime=row.regime,
        reasons=list(row.reasons),
        createdAt=to_iso(row.created_at),
    )


@router.get(
    "/top3-opportunities/latest",
    response_model=Top3OpportunitiesResponseDto,
)
async def get_latest_top3_opportunities(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Top3OpportunitiesResponseDto:
    """Run más reciente del TOP3 (por ``created_at``) y sus slots ordenados por rank.

    Sin TOP3 persistido devuelve ``runId=""`` e ``items=[]`` (fail-closed: la UI declara
    «sin TOP3 todavía», nunca una foto inventada).
    """
    repo = SqlAlchemyTop3OpportunityRepository(session)
    run_id, rows = await repo.latest()
    return Top3OpportunitiesResponseDto(runId=run_id, items=[_to_dto(r) for r in rows])


@router.get(
    "/top3-opportunities/{run_id}",
    response_model=Top3OpportunitiesResponseDto,
)
async def get_top3_opportunities_for_run(
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Top3OpportunitiesResponseDto:
    """Slots del TOP3 de un ``run_id`` concreto, ordenados por rank."""
    repo = SqlAlchemyTop3OpportunityRepository(session)
    rows = await repo.list_for_run(run_id)
    return Top3OpportunitiesResponseDto(runId=run_id, items=[_to_dto(r) for r in rows])
