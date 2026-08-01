from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_infrastructure.queue.scan_job_redis import SCAN_JOBS_QUEUE_KEY, ScanJobRedisQueue


@pytest.mark.asyncio
async def test_scan_job_redis_push_and_pop() -> None:
    queue = ScanJobRedisQueue("redis://localhost:6379/0")
    mock_redis = MagicMock()
    mock_redis.lpush = AsyncMock()
    mock_redis.brpop = AsyncMock(return_value=(SCAN_JOBS_QUEUE_KEY, "job-123"))
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()
    queue._redis = mock_redis

    await queue.push("job-123")
    mock_redis.lpush.assert_awaited_once_with(SCAN_JOBS_QUEUE_KEY, "job-123")

    job_id = await queue.pop(timeout_seconds=2)
    assert job_id == "job-123"
    mock_redis.brpop.assert_awaited_once_with(SCAN_JOBS_QUEUE_KEY, timeout=2)

    assert await queue.ping() is True
    await queue.close()
    mock_redis.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_scan_job_redis_pop_empty() -> None:
    queue = ScanJobRedisQueue("redis://localhost:6379/0")
    mock_redis = MagicMock()
    mock_redis.brpop = AsyncMock(return_value=None)
    queue._redis = mock_redis

    assert await queue.pop(timeout_seconds=1) is None
