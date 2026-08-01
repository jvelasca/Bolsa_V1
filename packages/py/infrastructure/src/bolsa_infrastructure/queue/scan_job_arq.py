"""RD-2 full — cola Arq para scan jobs."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

logger = logging.getLogger(__name__)

SCAN_JOB_ARQ_TASK = "process_scan_job"
OPTIMIZE_JOB_ARQ_TASK = "process_optimization_job"

_pool: ArqRedis | None = None


def redis_settings_from_url(redis_url: str) -> RedisSettings:
    parsed = urlparse(redis_url)
    database = parsed.path.lstrip("/")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(database) if database else 0,
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
    )


async def get_scan_job_arq_pool(redis_url: str) -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings_from_url(redis_url))
    return _pool


async def close_scan_job_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


class ScanJobArqQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def enqueue(self, job_id: str, *, task_name: str = SCAN_JOB_ARQ_TASK) -> None:
        pool = await get_scan_job_arq_pool(self._redis_url)
        await pool.enqueue_job(task_name, job_id)
        logger.debug("Job encolado en Arq (%s): %s", task_name, job_id)

    async def ping(self) -> bool:
        try:
            pool = await get_scan_job_arq_pool(self._redis_url)
            return bool(await pool.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await close_scan_job_arq_pool()
