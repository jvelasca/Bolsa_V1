"""API: mandato operativo multi-dispositivo (ADR-020 M1b)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.schemas.mandates import (
    MandateBundleDto,
    MandateBundleResponseDto,
    MandateTenureDto,
    MandateTradeLinkDto,
    SyncMandateBundleDto,
)
from bolsa_infrastructure.database.repositories.mandate_repository import (
    MandateTenureRecord,
    MandateTradeLinkRecord,
    SqlAlchemyMandateRepository,
)

router = APIRouter()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _tenure_dto(row: MandateTenureRecord) -> MandateTenureDto:
    return MandateTenureDto(
        id=row.id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        timeframe=row.timeframe,
        strategy_definition_id=row.strategy_definition_id,
        strategy_label_snapshot=row.strategy_label_snapshot,
        effective_from=_iso(row.effective_from),
        effective_to=_iso(row.effective_to) if row.effective_to else None,
        actor=row.actor,
        reason=row.reason,
        source_top_id=row.source_top_id,
        source_top_version=row.source_top_version,
        evidence_level=row.evidence_level,
    )


def _link_dto(row: MandateTradeLinkRecord) -> MandateTradeLinkDto:
    return MandateTradeLinkDto(
        transaction_id=row.transaction_id,
        mandate_tenure_id=row.mandate_tenure_id,
        instrument_id=row.instrument_id,
        account_id=row.account_id,
        linked_at=_iso(row.linked_at),
        engine=row.engine,
    )


@router.get(
    "/accounts/{account_id}/mandates",
    response_model=MandateBundleResponseDto,
)
async def get_account_mandates(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    instrument_id: str | None = Query(default=None, alias="instrumentId"),
) -> MandateBundleResponseDto:
    repo = SqlAlchemyMandateRepository(session)
    tenures = await repo.list_tenures(account_id, instrument_id=instrument_id)
    links = await repo.list_links(account_id, instrument_id=instrument_id)
    return MandateBundleResponseDto(
        data=MandateBundleDto(
            tenures=[_tenure_dto(t) for t in tenures],
            links=[_link_dto(link) for link in links],
        )
    )


@router.put(
    "/accounts/{account_id}/mandates",
    response_model=MandateBundleResponseDto,
)
async def sync_account_mandates(
    account_id: str,
    body: SyncMandateBundleDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MandateBundleResponseDto:
    """Push cliente → BD (cache localStorage + SoT PostgreSQL)."""
    repo = SqlAlchemyMandateRepository(session)
    tenures, links = await repo.sync_account(
        account_id,
        [t.model_dump(by_alias=True) for t in body.tenures],
        [link.model_dump(by_alias=True) for link in body.links],
    )
    return MandateBundleResponseDto(
        data=MandateBundleDto(
            tenures=[_tenure_dto(t) for t in tenures],
            links=[_link_dto(link) for link in links],
        )
    )
