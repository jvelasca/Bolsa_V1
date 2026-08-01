"""RD-2 — notificación Redis para scan jobs (evolución hacia Arq)."""

from __future__ import annotations

import redis.asyncio as aioredis

SCAN_JOBS_QUEUE_KEY = "bolsa:scan_jobs:pending"


class ScanJobRedisQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def push(self, job_id: str) -> None:
        await self._redis.lpush(SCAN_JOBS_QUEUE_KEY, job_id)

    async def pop(self, timeout_seconds: int = 5) -> str | None:
        result = await self._redis.brpop(SCAN_JOBS_QUEUE_KEY, timeout=timeout_seconds)
        if result is None:
            return None
        _key, job_id = result
        return job_id

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._redis.aclose()
