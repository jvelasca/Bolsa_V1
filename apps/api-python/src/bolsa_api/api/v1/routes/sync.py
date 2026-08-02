from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_db_session,
    get_enqueue_stale_use_case,
    get_list_sync_queue_use_case,
    get_sync_settings_use_case,
    get_update_sync_settings_use_case,
)
from bolsa_api.schemas.sync import (
    EnqueueStaleResponseDto,
    SyncQueueItemDto,
    SyncQueueResponseDto,
    SyncSettingsDto,
    SyncSettingsResponseDto,
    UpdateSyncSettingsDto,
)
from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
    SyncQueueItemRecord,
    SyncSettingsRecord,
)

router = APIRouter()


def _settings_dto(record: SyncSettingsRecord) -> SyncSettingsDto:
    return SyncSettingsDto(
        auto_sync_enabled=record.auto_sync_enabled,
        scan_interval_minutes=record.scan_interval_minutes,
        min_delay_seconds=record.min_delay_seconds,
        post_market_only=record.post_market_only,
        max_retries=record.max_retries,
        retry_backoff_minutes=record.retry_backoff_minutes,
        scope=record.scope,
        updated_at=record.updated_at,
    )


def _queue_dto(item: SyncQueueItemRecord) -> SyncQueueItemDto:
    return SyncQueueItemDto(
        id=item.id,
        instrument_id=item.instrument_id,
        symbol=item.symbol,
        status=item.status,
        priority=item.priority,
        scheduled_at=item.scheduled_at,
        attempts=item.attempts,
        last_error=item.last_error,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/sync/settings", response_model=SyncSettingsResponseDto)
async def get_sync_settings(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SyncSettingsResponseDto:
    record = await get_sync_settings_use_case(session).execute()
    return SyncSettingsResponseDto(data=_settings_dto(record))


@router.patch("/sync/settings", response_model=SyncSettingsResponseDto)
async def update_sync_settings(
    body: UpdateSyncSettingsDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SyncSettingsResponseDto:
    record = await get_update_sync_settings_use_case(session).execute(
        auto_sync_enabled=body.auto_sync_enabled,
        scan_interval_minutes=body.scan_interval_minutes,
        min_delay_seconds=body.min_delay_seconds,
        post_market_only=body.post_market_only,
        max_retries=body.max_retries,
        retry_backoff_minutes=body.retry_backoff_minutes,
        scope=body.scope,
    )
    return SyncSettingsResponseDto(data=_settings_dto(record))


@router.get("/sync/queue", response_model=SyncQueueResponseDto)
async def list_sync_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SyncQueueResponseDto:
    items = await get_list_sync_queue_use_case(session).execute()
    return SyncQueueResponseDto(data=[_queue_dto(item) for item in items])


@router.post("/sync/queue/enqueue-stale", response_model=EnqueueStaleResponseDto)
async def enqueue_stale_instruments(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EnqueueStaleResponseDto:
    result = await get_enqueue_stale_use_case(session).execute()
    return EnqueueStaleResponseDto(data={"scanned": result.scanned, "enqueued": result.enqueued})
