from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bolsa_infrastructure.queue.scan_job_arq import (
    OPTIMIZE_JOB_ARQ_TASK,
    SCAN_JOB_ARQ_TASK,
    ScanJobArqQueue,
    redis_settings_from_url,
)


def test_redis_settings_from_url() -> None:
    settings = redis_settings_from_url("redis://localhost:6379/2")
    assert settings.host == "localhost"
    assert settings.port == 6379
    assert settings.database == 2


@pytest.mark.asyncio
async def test_scan_job_arq_enqueue() -> None:
    queue = ScanJobArqQueue("redis://localhost:6379/0")
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.ping = AsyncMock(return_value=True)

    with patch(
        "bolsa_infrastructure.queue.scan_job_arq.get_scan_job_arq_pool",
        AsyncMock(return_value=mock_pool),
    ):
        await queue.enqueue("job-456")

    mock_pool.enqueue_job.assert_awaited_once_with(SCAN_JOB_ARQ_TASK, "job-456")


@pytest.mark.asyncio
async def test_optimize_job_arq_enqueue() -> None:
    queue = ScanJobArqQueue("redis://localhost:6379/0")
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.ping = AsyncMock(return_value=True)

    with patch(
        "bolsa_infrastructure.queue.scan_job_arq.get_scan_job_arq_pool",
        AsyncMock(return_value=mock_pool),
    ):
        await queue.enqueue("run-789", task_name=OPTIMIZE_JOB_ARQ_TASK)

    mock_pool.enqueue_job.assert_awaited_once_with(OPTIMIZE_JOB_ARQ_TASK, "run-789")
