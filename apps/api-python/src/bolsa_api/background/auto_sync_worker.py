"""Worker de actualización automática de OHLCV con cola y rate limiting."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from bolsa_application.sync_scheduler import is_post_market_window
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import (
    get_enqueue_stale_use_case,
    get_process_sync_queue_use_case,
    get_sync_scheduler_repository,
)

logger = logging.getLogger(__name__)

TICK_SECONDS = 15
_last_scan_at: datetime | None = None


async def _run_scan(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        try:
            result = await get_enqueue_stale_use_case(session).execute()
            await session.commit()
            if result.enqueued:
                logger.info(
                    "Auto-sync: %s instrumentos encolados (escaneados %s)",
                    result.enqueued,
                    result.scanned,
                )
            return result.enqueued
        except Exception:
            await session.rollback()
            raise


async def _run_queue_item(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    async with session_factory() as session:
        try:
            repo = get_sync_scheduler_repository(session)
            settings = await repo.get_settings()
            if not settings.auto_sync_enabled:
                return False
            result = await get_process_sync_queue_use_case(session).execute()
            await session.commit()
            if result.processed and result.instrument_id:
                level = logging.INFO if result.status != "failed" else logging.WARNING
                logger.log(
                    level,
                    "Auto-sync cola: %s → %s%s",
                    result.instrument_id,
                    result.status,
                    f" ({result.error})" if result.error else "",
                )
            return result.processed
        except Exception:
            await session.rollback()
            raise


async def auto_sync_worker_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    global _last_scan_at

    logger.info("Worker auto-sync OHLCV iniciado")
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            async with session_factory() as session:
                settings = await get_sync_scheduler_repository(session).get_settings()
            if not settings.auto_sync_enabled:
                continue
            if settings.post_market_only and not is_post_market_window():
                continue

            now = datetime.now(UTC)
            scan_due = (
                _last_scan_at is None
                or (now - _last_scan_at).total_seconds()
                >= settings.scan_interval_minutes * 60
            )
            if scan_due:
                await _run_scan(session_factory)
                _last_scan_at = now

            processed = await _run_queue_item(session_factory)
            if processed:
                async with session_factory() as session:
                    settings = await get_sync_scheduler_repository(session).get_settings()
                    delay = settings.min_delay_seconds
                await asyncio.sleep(delay)
        except Exception:
            logger.exception("Error en worker auto-sync")


def start_auto_sync_worker(session_factory: async_sessionmaker[AsyncSession]) -> asyncio.Task[None]:
    return asyncio.create_task(auto_sync_worker_loop(session_factory))
