"""Worker — batch EOD dictámenes Estudio (ADR-022 D2).

Off-by-default: ``ESTUDIO_EOD_OPINION_ENABLED=false``.
Sin lista de instrumento en settings el loop no hace nada (solo tick vacío).
La corrida real usa POST /instrument-daily-opinions/eod-batch con IDs (Estudio UI).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)


async def estudio_eod_opinion_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(300, int(settings.estudio_eod_opinion_interval_seconds))
    logger.info(
        "Worker ESTUDIO_EOD_OPINION iniciado — intervalo %ds (sin universo fijo; usa API batch)",
        interval,
    )
    while True:
        await asyncio.sleep(interval)
        # Scaffold: no auto-universe yet (Estudio es membresía cliente).
        # Cuando haya lista servidor, llamar DailyOpinionService.run_eod_batch aquí.
        logger.debug("ESTUDIO_EOD_OPINION tick (noop hasta universo servidor)")


def start_estudio_eod_opinion_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.estudio_eod_opinion_enabled:
        logger.info(
            "Worker ESTUDIO_EOD_OPINION desactivado (ESTUDIO_EOD_OPINION_ENABLED=false)"
        )
        return None
    return asyncio.create_task(estudio_eod_opinion_worker_loop(session_factory))
