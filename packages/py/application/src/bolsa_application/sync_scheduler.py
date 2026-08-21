"""Use-cases de sync scheduler / cola stale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bolsa_application.get_instrument_data_status import GetInstrumentDataStatus
from bolsa_application.sync_instrument import SyncInstrumentDailyBars
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
    SqlAlchemySyncSchedulerRepository,
    SyncQueueItemRecord,
    SyncSettingsRecord,
)

MADRID = ZoneInfo("Europe/Madrid")
POST_CLOSE_HOUR = 17
POST_CLOSE_MINUTE = 35


def is_post_market_window(now: datetime | None = None) -> bool:
    moment = (now or datetime.now(MADRID)).astimezone(MADRID)
    if moment.weekday() >= 5:
        return False
    if moment.hour > POST_CLOSE_HOUR:
        return True
    return moment.hour == POST_CLOSE_HOUR and moment.minute >= POST_CLOSE_MINUTE


class GetSyncSettings:
    """Obtiene Sync Settings."""
    def __init__(self, repo: SqlAlchemySyncSchedulerRepository) -> None:
        self._repo = repo

    async def execute(self) -> SyncSettingsRecord:
        return await self._repo.get_settings()


class UpdateSyncSettings:
    """Actualiza Sync Settings."""
    def __init__(self, repo: SqlAlchemySyncSchedulerRepository) -> None:
        self._repo = repo

    async def execute(self, **kwargs: Any) -> SyncSettingsRecord:
        return await self._repo.update_settings(**kwargs)


class ListSyncQueue:
    """Lista Sync Queue."""
    def __init__(self, repo: SqlAlchemySyncSchedulerRepository) -> None:
        self._repo = repo

    async def execute(self, *, limit: int = 100) -> list[SyncQueueItemRecord]:
        return await self._repo.list_queue(limit=limit)


@dataclass(frozen=True, slots=True)
class EnqueueStaleResult:
    """Encola Stale Result."""
    scanned: int
    enqueued: int


SYNC_SCOPE_LISTS = "lists"


class EnqueueStaleInstruments:
    """Encola instrumentos con diarias desfasadas.

    scope=`lists` (defecto): solo valores presentes en alguna lista de usuario.
    scope=`stale`|`all`: todos los activos. El worker sigue rate-limitando
    (1 ítem / tick + minDelaySeconds + throttle Yahoo).
    """

    def __init__(
        self,
        instrument_repo: SqlAlchemyInstrumentRepository,
        scheduler_repo: SqlAlchemySyncSchedulerRepository,
        data_status: GetInstrumentDataStatus,
        *,
        list_member_ids: set[str] | None = None,
    ) -> None:
        self._instruments = instrument_repo
        self._scheduler = scheduler_repo
        self._data_status = data_status
        self._list_member_ids = list_member_ids

    async def execute(self) -> EnqueueStaleResult:
        settings = await self._scheduler.get_settings()
        scope = (settings.scope or SYNC_SCOPE_LISTS).strip().lower()
        items = await self._instruments.list_with_meta()
        list_ids = self._list_member_ids
        if list_ids is None and scope == SYNC_SCOPE_LISTS:
            list_ids = await self._scheduler.list_member_instrument_ids()

        enqueued = 0
        scanned = 0
        for item in items:
            if not item.is_active:
                continue
            if scope == SYNC_SCOPE_LISTS and list_ids is not None and item.id not in list_ids:
                continue
            scanned += 1
            status = await self._data_status.execute(item.id)
            if status is None:
                continue
            if status.freshness_status not in ("stale", "empty", "error"):
                continue
            # Prioridad: vacíos primero; miembros de lista un peldaño por encima del resto.
            priority = 0
            if status.freshness_status == "empty":
                priority += 2
            if list_ids is not None and item.id in list_ids:
                priority += 1
            created = await self._scheduler.enqueue(item.id, priority=priority)
            if created:
                enqueued += 1
        return EnqueueStaleResult(scanned=scanned, enqueued=enqueued)


@dataclass(frozen=True, slots=True)
class ProcessQueueResult:
    """Procesa Queue Result."""
    processed: bool
    instrument_id: str | None = None
    status: str | None = None
    error: str | None = None


class ProcessNextSyncQueueItem:
    """Procesa Next Sync Queue Item."""
    def __init__(
        self,
        scheduler_repo: SqlAlchemySyncSchedulerRepository,
        sync_use_case: SyncInstrumentDailyBars,
    ) -> None:
        self._scheduler = scheduler_repo
        self._sync = sync_use_case

    async def execute(self) -> ProcessQueueResult:
        settings = await self._scheduler.get_settings()
        if settings.post_market_only and not is_post_market_window():
            return ProcessQueueResult(processed=False)

        item = await self._scheduler.claim_next()
        if item is None:
            return ProcessQueueResult(processed=False)

        result = await self._sync.execute(item.instrument_id)
        if result is None:
            await self._scheduler.fail_item(
                item.id,
                error="Instrument not found",
                retry=False,
                backoff_minutes=settings.retry_backoff_minutes,
                max_retries=settings.max_retries,
            )
            return ProcessQueueResult(processed=True, instrument_id=item.instrument_id, status="failed")

        if result.status == "failed":
            await self._scheduler.fail_item(
                item.id,
                error=result.error or "sync failed",
                retry=result.retryable,
                backoff_minutes=settings.retry_backoff_minutes,
                max_retries=settings.max_retries,
            )
            return ProcessQueueResult(
                processed=True,
                instrument_id=item.instrument_id,
                status="failed",
                error=result.error,
            )

        await self._scheduler.complete_item(item.id)
        return ProcessQueueResult(processed=True, instrument_id=item.instrument_id, status=result.status)
