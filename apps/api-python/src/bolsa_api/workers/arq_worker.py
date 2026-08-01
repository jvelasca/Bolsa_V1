"""RD-2/3b — worker Arq para scan jobs y optimization runs."""

from __future__ import annotations

import logging
from typing import Any

from arq.worker import Worker
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import (
    get_process_optimization_run_use_case,
    get_process_scan_job_use_case,
)
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.session import create_engine, create_session_factory
from bolsa_infrastructure.queue.scan_job_arq import redis_settings_from_url

logger = logging.getLogger(__name__)


async def process_scan_job(ctx: dict[str, Any], job_id: str) -> dict[str, Any]:
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    async with session_factory() as session:
        processor = get_process_scan_job_use_case(session)
        result = await processor.execute(job_id)
        await session.commit()

    if result.processed and result.job_id:
        level = logging.INFO if result.status == "completed" else logging.WARNING
        logger.log(
            level,
            "Arq scan job %s → %s%s",
            result.job_id,
            result.status,
            f" ({result.error})" if result.error else "",
        )

    return {
        "processed": result.processed,
        "jobId": result.job_id,
        "status": result.status,
        "error": result.error,
    }


async def process_optimization_job(ctx: dict[str, Any], run_id: str) -> dict[str, Any]:
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    async with session_factory() as session:
        processor = get_process_optimization_run_use_case(session)
        result = await processor.execute(run_id)
        await session.commit()

    if result.processed and result.run_id:
        level = logging.INFO if result.status == "completed" else logging.WARNING
        logger.log(
            level,
            "Arq optimization run %s → %s%s",
            result.run_id,
            result.status,
            f" ({result.error})" if result.error else "",
        )

    return {
        "processed": result.processed,
        "runId": result.run_id,
        "status": result.status,
        "error": result.error,
    }


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    engine: AsyncEngine = create_engine(settings)
    ctx["engine"] = engine
    ctx["session_factory"] = create_session_factory(engine)
    logger.info(
        "Worker Arq research jobs iniciado (scan + optimize, max_jobs=%s)",
        settings.scan_arq_max_jobs,
    )


async def on_shutdown(ctx: dict[str, Any]) -> None:
    engine: AsyncEngine | None = ctx.get("engine")
    if engine is not None:
        await engine.dispose()
    logger.info("Worker Arq research jobs detenido")


def run() -> None:
    settings = get_settings()
    worker = Worker(
        functions=[process_scan_job, process_optimization_job],
        redis_settings=redis_settings_from_url(settings.redis_url),
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        max_jobs=settings.scan_arq_max_jobs,
        job_timeout=settings.scan_arq_job_timeout_seconds,
    )
    worker.run()


if __name__ == "__main__":
    run()
