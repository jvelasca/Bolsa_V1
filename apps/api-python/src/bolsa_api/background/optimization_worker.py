"""RD-3b — worker inline para optimization_runs (poll PostgreSQL)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_process_optimization_run_use_case

logger = logging.getLogger(__name__)

TICK_SECONDS = 5


async def optimization_worker_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    logger.info("Worker optimization_runs iniciado — poll postgres cada %ss", TICK_SECONDS)
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            async with session_factory() as session:
                processor = get_process_optimization_run_use_case(session)
                result = await processor.execute()
                await session.commit()

            if result.processed and result.run_id:
                level = logging.INFO if result.status == "completed" else logging.WARNING
                logger.log(
                    level,
                    "Optimization run %s → %s%s",
                    result.run_id,
                    result.status,
                    f" ({result.error})" if result.error else "",
                )
        except Exception:
            logger.exception("Error en worker optimization_runs")


def start_optimization_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None]:
    return asyncio.create_task(optimization_worker_loop(session_factory))
