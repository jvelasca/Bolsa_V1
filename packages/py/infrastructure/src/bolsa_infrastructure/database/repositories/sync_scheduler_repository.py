from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bolsa_infrastructure.database.models import (
    InstrumentListItemRow,
    SyncQueueItemRow,
    SyncSettingsRow,
)
from bolsa_infrastructure.ids import new_id

DEFAULT_SETTINGS_ID = "default"


@dataclass(frozen=True, slots=True)
class SyncSettingsRecord:
    auto_sync_enabled: bool
    scan_interval_minutes: int
    min_delay_seconds: int
    post_market_only: bool
    max_retries: int
    retry_backoff_minutes: int
    scope: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SyncQueueItemRecord:
    id: str
    instrument_id: str
    symbol: str
    status: str
    priority: int
    scheduled_at: str
    attempts: int
    last_error: str | None
    created_at: str
    updated_at: str


def _settings_from_row(row: SyncSettingsRow) -> SyncSettingsRecord:
    return SyncSettingsRecord(
        auto_sync_enabled=row.auto_sync_enabled,
        scan_interval_minutes=row.scan_interval_minutes,
        min_delay_seconds=row.min_delay_seconds,
        post_market_only=row.post_market_only,
        max_retries=row.max_retries,
        retry_backoff_minutes=row.retry_backoff_minutes,
        scope=row.scope,
        updated_at=row.updated_at.isoformat(),
    )


def _queue_from_row(row: SyncQueueItemRow) -> SyncQueueItemRecord:
    return SyncQueueItemRecord(
        id=row.id,
        instrument_id=row.instrument_id,
        symbol=row.instrument.symbol if row.instrument else row.instrument_id,
        status=row.status,
        priority=row.priority,
        scheduled_at=row.scheduled_at.isoformat(),
        attempts=row.attempts,
        last_error=row.last_error,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


class SqlAlchemySyncSchedulerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_settings(self) -> SyncSettingsRecord:
        stmt = select(SyncSettingsRow).where(SyncSettingsRow.id == DEFAULT_SETTINGS_ID)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            now = datetime.now(UTC)
            row = SyncSettingsRow(
                id=DEFAULT_SETTINGS_ID,
                auto_sync_enabled=True,
                scan_interval_minutes=30,
                min_delay_seconds=3,
                post_market_only=False,
                max_retries=5,
                retry_backoff_minutes=45,
                scope="lists",
                updated_at=now,
            )
            self._session.add(row)
            await self._session.flush()
        return _settings_from_row(row)

    async def update_settings(
        self,
        *,
        auto_sync_enabled: bool | None = None,
        scan_interval_minutes: int | None = None,
        min_delay_seconds: int | None = None,
        post_market_only: bool | None = None,
        max_retries: int | None = None,
        retry_backoff_minutes: int | None = None,
        scope: str | None = None,
    ) -> SyncSettingsRecord:
        await self.get_settings()  # ensure default row exists
        stmt = select(SyncSettingsRow).where(SyncSettingsRow.id == DEFAULT_SETTINGS_ID)
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        if auto_sync_enabled is not None:
            row.auto_sync_enabled = auto_sync_enabled
        if scan_interval_minutes is not None:
            row.scan_interval_minutes = scan_interval_minutes
        if min_delay_seconds is not None:
            row.min_delay_seconds = min_delay_seconds
        if post_market_only is not None:
            row.post_market_only = post_market_only
        if max_retries is not None:
            row.max_retries = max_retries
        if retry_backoff_minutes is not None:
            row.retry_backoff_minutes = retry_backoff_minutes
        if scope is not None:
            row.scope = scope
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _settings_from_row(row)

    async def list_member_instrument_ids(self) -> set[str]:
        """IDs de instrumentos que aparecen en al menos una lista de usuario."""
        stmt = select(InstrumentListItemRow.instrument_id).distinct()
        result = await self._session.execute(stmt)
        return {row[0] for row in result.all() if row[0]}

    async def has_pending(self, instrument_id: str) -> bool:
        stmt = (
            select(SyncQueueItemRow.id)
            .where(
                SyncQueueItemRow.instrument_id == instrument_id,
                SyncQueueItemRow.status == "pending",
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def enqueue(
        self,
        instrument_id: str,
        *,
        priority: int = 0,
        scheduled_at: datetime | None = None,
        error: str | None = None,
    ) -> SyncQueueItemRecord | None:
        if await self.has_pending(instrument_id):
            return None
        now = datetime.now(UTC)
        row = SyncQueueItemRow(
            id=new_id(),
            instrument_id=instrument_id,
            status="pending",
            priority=priority,
            scheduled_at=scheduled_at or now,
            attempts=0,
            last_error=error,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row, attribute_names=["instrument"])
        stmt = (
            select(SyncQueueItemRow)
            .where(SyncQueueItemRow.id == row.id)
            .options(selectinload(SyncQueueItemRow.instrument))
        )
        loaded = (await self._session.execute(stmt)).scalar_one()
        return _queue_from_row(loaded)

    async def list_queue(self, *, limit: int = 100) -> list[SyncQueueItemRecord]:
        stmt = (
            select(SyncQueueItemRow)
            .where(SyncQueueItemRow.status.in_(("pending", "processing", "failed")))
            .options(selectinload(SyncQueueItemRow.instrument))
            .order_by(SyncQueueItemRow.priority.desc(), SyncQueueItemRow.scheduled_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_queue_from_row(row) for row in result.scalars().all()]

    async def claim_next(self, now: datetime | None = None) -> SyncQueueItemRecord | None:
        moment = now or datetime.now(UTC)
        stmt = (
            select(SyncQueueItemRow)
            .where(
                SyncQueueItemRow.status == "pending",
                SyncQueueItemRow.scheduled_at <= moment,
            )
            .options(selectinload(SyncQueueItemRow.instrument))
            .order_by(SyncQueueItemRow.priority.desc(), SyncQueueItemRow.scheduled_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "processing"
        row.updated_at = moment
        await self._session.flush()
        return _queue_from_row(row)

    async def complete_item(self, item_id: str) -> None:
        await self._session.execute(
            update(SyncQueueItemRow)
            .where(SyncQueueItemRow.id == item_id)
            .values(status="completed", updated_at=datetime.now(UTC)),
        )

    async def fail_item(
        self,
        item_id: str,
        *,
        error: str,
        retry: bool,
        backoff_minutes: int,
        max_retries: int,
    ) -> None:
        stmt = select(SyncQueueItemRow).where(SyncQueueItemRow.id == item_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        now = datetime.now(UTC)
        row.attempts += 1
        row.last_error = error
        row.updated_at = now
        if retry and row.attempts < max_retries:
            row.status = "pending"
            row.scheduled_at = now + timedelta(minutes=backoff_minutes * row.attempts)
        else:
            row.status = "failed"
        await self._session.flush()

    async def requeue_failed(self, instrument_id: str, error: str, backoff_minutes: int) -> None:
        stmt = (
            select(SyncQueueItemRow)
            .where(
                SyncQueueItemRow.instrument_id == instrument_id,
                SyncQueueItemRow.status.in_(("failed", "processing")),
            )
            .order_by(SyncQueueItemRow.updated_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        now = datetime.now(UTC)
        if row:
            row.status = "pending"
            row.scheduled_at = now + timedelta(minutes=backoff_minutes)
            row.last_error = error
            row.updated_at = now
            await self._session.flush()
            return
        await self.enqueue(instrument_id, error=error, scheduled_at=now + timedelta(minutes=backoff_minutes))
