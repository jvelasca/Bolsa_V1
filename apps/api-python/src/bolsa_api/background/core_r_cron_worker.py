"""Worker — CORE-R cron servidor (informe BD + PnL DEMO).

Off-by-default: ``CORE_R_CRON_ENABLED=false``.
Solo actúa sobre cuentas con ``scheduler.enabled`` + ``listId`` en blob.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.run_core_r_server_cron import RunCoreRServerCron
from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)


async def _run_core_r_cron_once(session_factory: async_sessionmaker[AsyncSession]) -> dict:
    async with session_factory() as session:
        try:
            result = await RunCoreRServerCron(session).execute()
            await session.commit()
            if result.get("ticked"):
                logger.info(
                    "CORE-R cron: ticked=%s added=%s accounts=%s",
                    result.get("ticked"),
                    result.get("totalAdded"),
                    result.get("accounts"),
                )
            return result
        except Exception:
            await session.rollback()
            raise


async def core_r_cron_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(60, int(settings.core_r_cron_interval_seconds))
    logger.info("Worker CORE-R cron iniciado — intervalo %ds", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            await _run_core_r_cron_once(session_factory)
        except Exception:
            logger.exception("Error en worker CORE-R cron")


def start_core_r_cron_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.core_r_cron_enabled:
        logger.info("CORE-R cron worker desactivado (CORE_R_CRON_ENABLED=false)")
        return None
    return asyncio.create_task(core_r_cron_worker_loop(session_factory))
