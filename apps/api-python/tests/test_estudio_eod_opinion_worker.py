"""``estudio_eod_opinion_worker`` — encola el job diario una vez por día (sin tick vacío).

Hermético: repositorios en memoria y sesión falsa. Cubre: sin cuenta activa no se
encola, un job del día ya ``queued|running|completed`` no se duplica, y un día con
fallos reintenta solo hasta ``_MAX_ATTEMPTS_PER_DAY``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

import bolsa_api.background.estudio_eod_opinion_worker as worker
from bolsa_application.auto_ops_jobs import EnqueueOutcome
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_ESTUDIO_DAILY,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    AutoOpsJob,
)

_NOW = datetime(2026, 10, 18, 21, 0, tzinfo=UTC)


class _FakeSessions:
    info: dict[str, Any] = {}

    async def __aenter__(self) -> _FakeSessions:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _FakeAccountRepo:
    account_id: str | None = "acc-1"

    def __init__(self, _session: Any = None) -> None:
        pass

    async def resolve_default_account_for_owner(self, **_kwargs: Any) -> str | None:
        return type(self).account_id


class _FakeJobRepo:
    jobs: list[AutoOpsJob] = []
    enqueued: list[dict[str, Any]] = []
    _seq = 0

    def __init__(self, _session: Any = None) -> None:
        pass

    async def list_for_day(
        self, *, kind: str, day: str, account_id: str | None, limit: int = 20
    ) -> list[AutoOpsJob]:
        return [
            job
            for job in self.jobs
            if job.kind == kind and job.day == day and job.account_id == account_id
        ][:limit]

    async def enqueue(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> AutoOpsJob:
        outcome = await self.enqueue_with_outcome(
            kind=kind, day=day, account_id=account_id, payload=payload
        )
        return outcome.job

    async def enqueue_with_outcome(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> EnqueueOutcome:
        type(self)._seq += 1
        job = AutoOpsJob(
            id=f"job-{type(self)._seq}",
            kind=kind,
            status=JOB_STATUS_QUEUED,
            day=day,
            account_id=account_id,
            payload=dict(payload or {}),
        )
        self.jobs.append(job)
        type(self).enqueued.append({"id": job.id, "day": day, "payload": job.payload})
        return EnqueueOutcome(job=job, created=True)


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAccountRepo.account_id = "acc-1"
    _FakeJobRepo.jobs = []
    _FakeJobRepo.enqueued = []
    _FakeJobRepo._seq = 0
    monkeypatch.setattr(worker, "SqlAlchemyAccountRepository", _FakeAccountRepo)
    monkeypatch.setattr(worker, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)


@pytest.mark.asyncio
async def test_without_an_active_account_nothing_is_enqueued() -> None:
    _FakeAccountRepo.account_id = None

    assert await worker.enqueue_daily_estudio_job(_FakeSessions, now=_NOW) is None
    assert _FakeJobRepo.enqueued == []


@pytest.mark.asyncio
async def test_the_daily_job_is_enqueued_once() -> None:
    first = await worker.enqueue_daily_estudio_job(_FakeSessions, now=_NOW)
    second = await worker.enqueue_daily_estudio_job(_FakeSessions, now=_NOW)

    assert first == "job-1"
    assert second is None
    assert len(_FakeJobRepo.enqueued) == 1
    assert _FakeJobRepo.enqueued[0]["payload"]["enqueuedBy"] == "scheduler"


@pytest.mark.asyncio
async def test_a_completed_job_of_the_day_is_not_duplicated() -> None:
    _FakeJobRepo.jobs.append(
        AutoOpsJob(
            id="job-done",
            kind=JOB_KIND_ESTUDIO_DAILY,
            status=JOB_STATUS_COMPLETED,
            day="2026-10-18",
            account_id="acc-1",
        )
    )

    assert await worker.enqueue_daily_estudio_job(_FakeSessions, now=_NOW) is None


@pytest.mark.asyncio
async def test_failures_are_retried_only_up_to_the_cap() -> None:
    for index in range(worker._MAX_ATTEMPTS_PER_DAY):
        _FakeJobRepo.jobs.append(
            AutoOpsJob(
                id=f"job-failed-{index}",
                kind=JOB_KIND_ESTUDIO_DAILY,
                status=JOB_STATUS_FAILED,
                day="2026-10-18",
                account_id="acc-1",
            )
        )

    assert await worker.enqueue_daily_estudio_job(_FakeSessions, now=_NOW) is None
    assert _FakeJobRepo.enqueued == []


@pytest.mark.asyncio
async def test_a_failed_day_below_the_cap_is_retried() -> None:
    _FakeJobRepo.jobs.append(
        AutoOpsJob(
            id="job-failed",
            kind=JOB_KIND_ESTUDIO_DAILY,
            status=JOB_STATUS_FAILED,
            day="2026-10-18",
            account_id="acc-1",
        )
    )

    assert await worker.enqueue_daily_estudio_job(_FakeSessions, now=_NOW) == "job-1"
