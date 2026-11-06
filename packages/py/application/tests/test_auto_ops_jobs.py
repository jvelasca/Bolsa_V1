"""Casos de uso de la cola ``auto_ops_jobs`` (fakes, sin PostgreSQL).

Fija las reglas duras del contrato:

* idempotencia por ``(kind, cuenta, día)`` mientras el job está ACTIVO;
* una fecha futura no se puede replayar;
* un job de otra cuenta es INDISTINGUIBLE de inexistente (fail-closed);
* sin cuenta no se encola ni se lista nada.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.auto_ops_jobs import (
    EnqueueAutoOpsJob,
    EnqueueOutcome,
    GetAutoOpsJob,
    ListAutoOpsJobs,
)
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_DIA_D_REPLAY,
    JOB_KIND_DIA_D_VALUE_REPLAY,
    JOB_KIND_ESTUDIO_DAILY,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_QUEUED,
    AutoOpsJob,
)


class _FakeJobRepo:
    def __init__(self) -> None:
        self.jobs: list[AutoOpsJob] = []
        self._seq = 0

    async def get(self, job_id: str) -> AutoOpsJob | None:
        return next((job for job in self.jobs if job.id == job_id), None)

    async def find_active(
        self, *, kind: str, day: str, account_id: str | None
    ) -> AutoOpsJob | None:
        for job in self.jobs:
            if (
                job.kind == kind
                and job.day == day
                and job.account_id == account_id
                and job.status in (JOB_STATUS_QUEUED, "running")
            ):
                return job
        return None

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
        existing = await self.find_active(kind=kind, day=day, account_id=account_id)
        if existing is not None:
            return EnqueueOutcome(job=existing, created=False)
        self._seq += 1
        job = AutoOpsJob(
            id=f"job-{self._seq}",
            kind=kind,
            status=JOB_STATUS_QUEUED,
            day=day,
            account_id=account_id,
            payload=dict(payload or {}),
        )
        self.jobs.append(job)
        return EnqueueOutcome(job=job, created=True)

    async def list_for_account(
        self, *, account_id: str | None, kind: str | None = None, limit: int = 20
    ) -> list[AutoOpsJob]:
        rows = [j for j in self.jobs if j.account_id == account_id]
        if kind is not None:
            rows = [j for j in rows if j.kind == kind]
        return rows[:limit]


@pytest.mark.asyncio
async def test_two_runs_of_the_same_day_do_not_duplicate_the_active_job() -> None:
    repo = _FakeJobRepo()
    use_case = EnqueueAutoOpsJob(repo)

    first = await use_case.execute(
        kind=JOB_KIND_ESTUDIO_DAILY, account_id="acc-1", day="2026-10-18"
    )
    second = await use_case.execute(
        kind=JOB_KIND_ESTUDIO_DAILY, account_id="acc-1", day="2026-10-18"
    )

    assert first.id == second.id
    assert len(repo.jobs) == 1


@pytest.mark.asyncio
async def test_the_outcome_declares_whether_this_request_created_the_job() -> None:
    """D-4 — ``created`` distingue «encolado ahora» de «ya ocupado por otro trabajo»."""
    repo = _FakeJobRepo()
    use_case = EnqueueAutoOpsJob(repo)

    first = await use_case.execute_with_outcome(
        kind=JOB_KIND_DIA_D_VALUE_REPLAY,
        account_id="acc-1",
        day="2026-10-18",
        payload={"symbol": "AAA"},
    )
    second = await use_case.execute_with_outcome(
        kind=JOB_KIND_DIA_D_VALUE_REPLAY,
        account_id="acc-1",
        day="2026-10-18",
        payload={"symbol": "BBB"},
    )

    assert first.created is True
    assert second.created is False
    # El job devuelto es el MISMO: el segundo símbolo no se encoló.
    assert second.job.id == first.job.id
    # El camino histórico (`execute`) sigue devolviendo solo el job.
    assert (await use_case.execute(
        kind=JOB_KIND_DIA_D_VALUE_REPLAY,
        account_id="acc-1",
        day="2026-10-18",
        payload={"symbol": "CCC"},
    )).id == first.job.id


@pytest.mark.asyncio
async def test_a_completed_job_frees_the_slot_for_a_declared_manual_rerun() -> None:
    repo = _FakeJobRepo()
    use_case = EnqueueAutoOpsJob(repo)
    first = await use_case.execute(
        kind=JOB_KIND_ESTUDIO_DAILY, account_id="acc-1", day="2026-10-18"
    )
    repo.jobs[0] = AutoOpsJob(
        id=first.id,
        kind=first.kind,
        status=JOB_STATUS_COMPLETED,
        day=first.day,
        account_id=first.account_id,
    )

    second = await use_case.execute(
        kind=JOB_KIND_ESTUDIO_DAILY, account_id="acc-1", day="2026-10-18"
    )

    assert second.id != first.id
    assert len(repo.jobs) == 2


@pytest.mark.asyncio
async def test_unknown_kind_and_missing_account_fail_closed() -> None:
    use_case = EnqueueAutoOpsJob(_FakeJobRepo())

    with pytest.raises(ValueError, match="kind inválido"):
        await use_case.execute(kind="nope", account_id="acc-1", day="2026-10-18")
    with pytest.raises(ValueError, match="account_id requerido"):
        await use_case.execute(kind=JOB_KIND_ESTUDIO_DAILY, account_id=None)


@pytest.mark.asyncio
async def test_dia_d_replay_rejects_a_future_day() -> None:
    use_case = EnqueueAutoOpsJob(_FakeJobRepo())
    past = "2026-01-02"

    with pytest.raises(ValueError, match="fecha futura"):
        await use_case.execute(
            kind=JOB_KIND_DIA_D_REPLAY, account_id="acc-1", day="2999-01-01"
        )
    # Una fecha pasada sí se encola.
    job = await use_case.execute(
        kind=JOB_KIND_DIA_D_REPLAY, account_id="acc-1", day=past
    )
    assert job.kind == JOB_KIND_DIA_D_REPLAY


@pytest.mark.asyncio
async def test_a_job_of_another_account_is_indistinguishable_from_missing() -> None:
    repo = _FakeJobRepo()
    job = await EnqueueAutoOpsJob(repo).execute(
        kind=JOB_KIND_ESTUDIO_DAILY, account_id="acc-1", day="2026-10-18"
    )
    get = GetAutoOpsJob(repo)

    assert await get.execute(job.id, account_id="acc-1") is not None
    assert await get.execute(job.id, account_id="acc-2") is None
    assert await get.execute("does-not-exist", account_id="acc-1") is None
    assert await get.execute(job.id, account_id=None) is None


@pytest.mark.asyncio
async def test_listing_without_account_returns_nothing() -> None:
    repo = _FakeJobRepo()
    await EnqueueAutoOpsJob(repo).execute(
        kind=JOB_KIND_ESTUDIO_DAILY, account_id="acc-1", day="2026-10-18"
    )

    assert await ListAutoOpsJobs(repo).execute(account_id=None) == []
    listed = await ListAutoOpsJobs(repo).execute(
        account_id="acc-1", kind=JOB_KIND_ESTUDIO_DAILY
    )
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_value_replay_requires_and_normalizes_the_symbol() -> None:
    repo = _FakeJobRepo()
    use_case = EnqueueAutoOpsJob(repo)

    with pytest.raises(ValueError, match="symbol requerido"):
        await use_case.execute(
            kind=JOB_KIND_DIA_D_VALUE_REPLAY, account_id="acc-1", day="2026-10-18"
        )
    with pytest.raises(ValueError, match="symbol requerido"):
        await use_case.execute(
            kind=JOB_KIND_DIA_D_VALUE_REPLAY,
            account_id="acc-1",
            day="2026-10-18",
            payload={"symbol": "   "},
        )

    job = await use_case.execute(
        kind=JOB_KIND_DIA_D_VALUE_REPLAY,
        account_id="acc-1",
        day="2026-10-18",
        payload={"symbol": " san "},
    )

    # El símbolo se normaliza (el motor identifica en mayúsculas) y se declara el instrumento.
    assert job.payload["symbol"] == "SAN"
    assert job.payload["instrumentId"] == "SAN"


@pytest.mark.asyncio
async def test_value_replay_rejects_a_future_day() -> None:
    use_case = EnqueueAutoOpsJob(_FakeJobRepo())

    with pytest.raises(ValueError, match="fecha futura"):
        await use_case.execute(
            kind=JOB_KIND_DIA_D_VALUE_REPLAY,
            account_id="acc-1",
            day="2999-01-01",
            payload={"symbol": "SAN"},
        )


@pytest.mark.asyncio
async def test_value_replay_of_another_symbol_returns_the_active_job_of_the_slot() -> None:
    """El hueco de idempotencia es ``(kind, cuenta, día)``: el símbolo viaja en ``payload``.

    La UI lo declara en vez de fingir que encoló el suyo: el segundo símbolo recibe el job
    ACTIVO del primero y puede leer su ``payload.symbol``.
    """
    repo = _FakeJobRepo()
    use_case = EnqueueAutoOpsJob(repo)

    first = await use_case.execute(
        kind=JOB_KIND_DIA_D_VALUE_REPLAY,
        account_id="acc-1",
        day="2026-10-18",
        payload={"symbol": "SAN"},
    )
    second = await use_case.execute(
        kind=JOB_KIND_DIA_D_VALUE_REPLAY,
        account_id="acc-1",
        day="2026-10-18",
        payload={"symbol": "BBVA"},
    )

    assert second.id == first.id
    assert second.payload["symbol"] == "SAN"
    assert len(repo.jobs) == 1
