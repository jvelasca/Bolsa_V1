"""Worker P9 — encola scans de rastreadores on_bar_close tras cierre de barra."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_process_tracker_schedules_use_case
from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)


async def _run_tracker_schedules_once(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        try:
            result = await get_process_tracker_schedules_use_case(session).execute()
            await session.commit()
            if result.enqueued_count:
                logger.info(
                    "Tracker schedule: %s jobs encolados (%s revisados)",
                    result.enqueued_count,
                    result.checked_count,
                )
                for run in result.runs:
                    if run.status == "enqueued":
                        logger.info(
                            "Tracker %s (%s) → scan job %s @ bar %s",
                            run.tracker_name,
                            run.tracker_id,
                            run.scan_job_id,
                            run.latest_bar_timestamp,
                        )
            return result.enqueued_count
        except Exception:
            await session.rollback()
            raise


async def tracker_schedule_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(30, int(settings.tracker_schedule_interval_seconds))
    logger.info("Worker tracker schedule iniciado — intervalo %ds", interval)

    while True:
        await asyncio.sleep(interval)
        try:
            await _run_tracker_schedules_once(session_factory)
        except Exception:
            logger.exception("Error en worker tracker schedule")


def start_tracker_schedule_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.tracker_schedule_enabled:
        logger.info("Tracker schedule worker desactivado (TRACKER_SCHEDULE_ENABLED=false)")
        return None
    return asyncio.create_task(tracker_schedule_worker_loop(session_factory))
