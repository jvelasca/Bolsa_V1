"""RD-2 — worker scan jobs con cola Redis o polling PostgreSQL."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_process_scan_job_use_case
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.queue.scan_job_redis import ScanJobRedisQueue

logger = logging.getLogger(__name__)

TICK_SECONDS = 5


async def scan_worker_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    use_redis = settings.scan_queue_backend.lower() == "redis"
    redis_queue: ScanJobRedisQueue | None = None

    if use_redis:
        redis_queue = ScanJobRedisQueue(settings.redis_url)
        if not await redis_queue.ping():
            logger.warning(
                "SCAN_QUEUE_BACKEND=redis pero Redis no responde — fallback postgres poll",
            )
            use_redis = False

    backend = "redis" if use_redis else "postgres"
    logger.info("Worker scan jobs (RD-2) iniciado — backend=%s", backend)
    try:
        while True:
            try:
                job_id: str | None = None
                if use_redis and redis_queue is not None:
                    job_id = await redis_queue.pop(timeout_seconds=TICK_SECONDS)
                else:
                    await asyncio.sleep(TICK_SECONDS)

                async with session_factory() as session:
                    processor = get_process_scan_job_use_case(session)
                    if job_id is not None:
                        result = await processor.execute(job_id)
                    else:
                        result = await processor.execute()
                    await session.commit()

                if result.processed and result.job_id:
                    level = logging.INFO if result.status == "completed" else logging.WARNING
                    logger.log(
                        level,
                        "Scan job %s → %s%s",
                        result.job_id,
                        result.status,
                        f" ({result.error})" if result.error else "",
                    )
            except Exception:
                logger.exception("Error en worker scan jobs")
    finally:
        if redis_queue is not None:
            await redis_queue.close()


def start_scan_worker(session_factory: async_sessionmaker[AsyncSession]) -> asyncio.Task[None]:
    return asyncio.create_task(scan_worker_loop(session_factory))
