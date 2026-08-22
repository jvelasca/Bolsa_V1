"""API: listas / universos (IBEX, watchlists)."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_import_instrument_use_case,
    get_instrument_repository,
    get_list_repository,
    get_list_trackers_for_list_use_case,
    get_remove_instrument_from_list_use_case,
)
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.schemas.instrument_lifecycle import (
    RemoveInstrumentFromListRequestDto,
    RemoveInstrumentFromListResponseDto,
)
from bolsa_api.schemas.lifecycle_mappers import to_remove_from_list_result_dto
from bolsa_api.schemas.lists import (
    CreateListRequestDto,
    InstrumentListDetailDto,
    InstrumentListMembershipsResponseDto,
    InstrumentListResponseDto,
    InstrumentListsResponseDto,
    InstrumentListSummaryDto,
    ListQuotesResponseDto,
    UpdateListRequestDto,
)
from bolsa_api.schemas.mappers import to_instrument_dto
from bolsa_api.schemas.trackers import (
    TrackerDefinitionDetailDto,
    TrackerDefinitionDetailsListResponseDto,
    TrackerDefinitionSummaryDto,
)
from bolsa_application.lists import (
    CreateInstrumentList,
    DeleteInstrumentList,
    GetInstrumentList,
    GetListQuotes,
    ListInstrumentListMemberships,
    ListInstrumentLists,
    UpdateInstrumentList,
)
from bolsa_application.market_indices import SubscribeMarketIndex, SyncSubscribedCatalogIndices
from bolsa_application.trackers import ListTrackerDefinitionsForList
from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord
from bolsa_infrastructure.database.repositories.list_repository import (
    InstrumentListDetail,
    InstrumentListSummary,
)

router = APIRouter()

# Sync de índices en GET /lists es caro; TTL evita rehacerlo en cada refetch del shell.
_LISTS_CATALOG_SYNC_TTL_S = 60.0
_lists_catalog_sync_mono = 0.0


def _should_sync_catalog_on_list() -> bool:
    global _lists_catalog_sync_mono
    now = time.monotonic()
    if now - _lists_catalog_sync_mono >= _LISTS_CATALOG_SYNC_TTL_S:
        _lists_catalog_sync_mono = now
        return True
    return False


def _to_summary_dto(item: InstrumentListSummary) -> InstrumentListSummaryDto:
    return InstrumentListSummaryDto(
        id=item.id,
        name=item.name,
        source=item.source,
        item_count=item.item_count,
        updated_at=item.updated_at,
        kind=item.kind,
        universe_code=item.universe_code,
        last_synced_at=item.last_synced_at,
        content_hash=item.content_hash,
    )


def _to_detail_dto(item: InstrumentListDetail) -> InstrumentListDetailDto:
    return InstrumentListDetailDto(
        id=item.id,
        name=item.name,
        source=item.source,
        instrument_ids=item.instrument_ids,
        updated_at=item.updated_at,
        kind=item.kind,
        universe_code=item.universe_code,
        last_synced_at=item.last_synced_at,
        content_hash=item.content_hash,
        membership_changelog=item.membership_changelog,
    )


def _tracker_summary(record: TrackerDefinitionRecord) -> TrackerDefinitionSummaryDto:
    return TrackerDefinitionSummaryDto(
        id=record.id,
        name=record.name,
        strategy_definition_id=record.strategy_definition_id,
        strategy_version=record.strategy_version,
        timeframe=record.timeframe,
        evaluation_mode=record.evaluation_mode,
        origin=record.origin,
        enabled=record.enabled,
        updated_at=record.updated_at,
        created_at=record.created_at,
    )


def _tracker_detail(record: TrackerDefinitionRecord) -> TrackerDefinitionDetailDto:
    return TrackerDefinitionDetailDto(
        **_tracker_summary(record).model_dump(),
        definition=record.definition,
    )


@router.get("/lists", response_model=InstrumentListsResponseDto)
async def list_lists(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentListsResponseDto:
    repo = get_list_repository(session)
    sync_catalog = _should_sync_catalog_on_list()
    sync = None
    if sync_catalog:
        sync = SyncSubscribedCatalogIndices(
            SubscribeMarketIndex(
                repo,
                get_instrument_repository(session),
                get_import_instrument_use_case(session),
            ),
            repo,
        )
    items = await ListInstrumentLists(repo, sync_indices=sync).execute(
        sync_catalog=sync_catalog,
    )
    return InstrumentListsResponseDto(data=[_to_summary_dto(item) for item in items])


@router.get("/lists/memberships", response_model=InstrumentListMembershipsResponseDto)
async def list_memberships(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentListMembershipsResponseDto:
    """Batch: id → instrumentIds para el sync de membresía del shell (evita N+1)."""
    repo = get_list_repository(session)
    data = await ListInstrumentListMemberships(repo).execute()
    return InstrumentListMembershipsResponseDto(data=data)


@router.get("/lists/{list_id}", response_model=InstrumentListResponseDto)
async def get_list(
    list_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentListResponseDto:
    repo = get_list_repository(session)
    detail = await GetInstrumentList(repo).execute(list_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="List not found")
    return InstrumentListResponseDto(data=_to_detail_dto(detail))


@router.get("/lists/{list_id}/quotes", response_model=ListQuotesResponseDto)
async def get_list_quotes(
    list_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ListQuotesResponseDto:
    repo = get_list_repository(session)
    try:
        quotes = await GetListQuotes(repo).execute(list_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ListQuotesResponseDto(data=[to_instrument_dto(item) for item in quotes])


@router.get("/lists/{list_id}/trackers", response_model=TrackerDefinitionDetailsListResponseDto)
async def get_list_trackers(
    list_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TrackerDefinitionDetailsListResponseDto:
    principal = get_request_principal(request)
    repo = get_list_repository(session)
    detail = await GetInstrumentList(repo).execute(list_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="List not found")
    use_case: ListTrackerDefinitionsForList = get_list_trackers_for_list_use_case(session)
    records = await use_case.execute(list_id, limit=50, owner_user_id=principal)
    return TrackerDefinitionDetailsListResponseDto(
        data=[_tracker_detail(record) for record in records],
    )


@router.post("/lists", response_model=InstrumentListResponseDto, status_code=201)
async def create_list(
    body: CreateListRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentListResponseDto:
    repo = get_list_repository(session)
    try:
        detail = await CreateInstrumentList(repo).execute(
            name=body.name,
            instrument_ids=body.instrument_ids,
            source=body.source,
            kind=body.kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InstrumentListResponseDto(data=_to_detail_dto(detail))


@router.patch("/lists/{list_id}", response_model=InstrumentListResponseDto)
async def update_list(
    list_id: str,
    body: UpdateListRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstrumentListResponseDto:
    repo = get_list_repository(session)
    try:
        detail = await UpdateInstrumentList(repo).execute(
            list_id,
            name=body.name,
            instrument_ids=body.instrument_ids,
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if "not found" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg) from exc
    return InstrumentListResponseDto(data=_to_detail_dto(detail))


@router.delete("/lists/{list_id}", status_code=204)
async def delete_list(
    list_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repo = get_list_repository(session)
    try:
        await DeleteInstrumentList(repo).execute(list_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/lists/{list_id}/instruments/{instrument_id}/remove",
    response_model=RemoveInstrumentFromListResponseDto,
)
async def remove_instrument_from_list(
    list_id: str,
    instrument_id: str,
    body: RemoveInstrumentFromListRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RemoveInstrumentFromListResponseDto:
    try:
        result = await get_remove_instrument_from_list_use_case(session).execute(
            list_id,
            instrument_id,
            purge_if_orphan=body.purge_if_orphan,
        )
    except ValueError as exc:
        detail = str(exc)
        missing = "no encontrada" in detail.lower() or "no encontrado" in detail.lower()
        status = 404 if missing else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    return RemoveInstrumentFromListResponseDto(data=to_remove_from_list_result_dto(result))
