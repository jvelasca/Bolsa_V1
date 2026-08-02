"""Worker L2 — procesa jobs de suscripción de índices (poll Postgres)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import (
    get_import_instrument_use_case,
    get_instrument_repository,
    get_list_repository,
)
from bolsa_application.market_indices import ProcessIndexSubscribeJob, SubscribeMarketIndex
from bolsa_infrastructure.database.repositories.index_subscribe_job_repository import (
    SqlAlchemyIndexSubscribeJobRepository,
)

logger = logging.getLogger(__name__)

TICK_SECONDS = 3


async def index_subscribe_worker_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    logger.info("Worker index-subscribe jobs iniciado")
    while True:
        try:
            await asyncio.sleep(TICK_SECONDS)
            async with session_factory() as session:
                jobs = SqlAlchemyIndexSubscribeJobRepository(session)
                subscribe = SubscribeMarketIndex(
                    get_list_repository(session),
                    get_instrument_repository(session),
                    get_import_instrument_use_case(session),
                )
                result = await ProcessIndexSubscribeJob(jobs, subscribe).execute()
                await session.commit()
                if result and result.status in {"completed", "failed"}:
                    level = logging.INFO if result.status == "completed" else logging.WARNING
                    logger.log(
                        level,
                        "Index subscribe job %s → %s%s",
                        result.id,
                        result.status,
                        f" ({result.error})" if result.error else "",
                    )
        except Exception:
            logger.exception("Error en worker index-subscribe")


def start_index_subscribe_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None]:
    return asyncio.create_task(index_subscribe_worker_loop(session_factory))

