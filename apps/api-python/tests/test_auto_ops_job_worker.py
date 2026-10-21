"""Worker de la cola ``auto_ops_jobs`` (hermético, sin PostgreSQL).

Cubre: reclamo de UN job por tick, desenlace durable ``completed``/``failed`` (con el
``result`` parcial cuando lo hay), despacho por ``kind`` (un tipo desconocido falla
cerrado) y el interruptor ``AUTO_OPS_JOB_WORKER_ENABLED``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.auto_ops_job_worker as worker
import bolsa_application.estudio_daily_ops as daily_ops
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_DIA_D_REPLAY,
    JOB_KIND_DIA_D_VALUE_REPLAY,
    JOB_KIND_ESTUDIO_DAILY,
    JOB_STATUS_RUNNING,
    AutoOpsJob,
)


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


class _FakeJobRepo:
    job: AutoOpsJob | None = None
    completed: tuple[str, dict[str, Any]] | None = None
    failed: tuple[str, str, dict[str, Any] | None] | None = None
    progress: list[dict[str, Any]] = []
    claim_kwargs: dict[str, Any] | None = None
    exhausted_kwargs: dict[str, Any] | None = None

    def __init__(self, _session: Any = None) -> None:
        pass

    async def claim_next(
        self, *, stale_after_seconds: int, max_attempts: int = 5
    ) -> AutoOpsJob | None:
        type(self).claim_kwargs = {
            "stale_after_seconds": stale_after_seconds,
            "max_attempts": max_attempts,
        }
        return type(self).job

    async def fail_exhausted(
        self, *, max_attempts: int = 5, stale_after_seconds: int = 1800
    ) -> int:
        type(self).exhausted_kwargs = {
            "max_attempts": max_attempts,
            "stale_after_seconds": stale_after_seconds,
        }
        return 0

    async def complete(self, job_id: str, result: dict[str, Any]) -> None:
        type(self).completed = (job_id, result)

    async def fail(
        self, job_id: str, error: str, result: dict[str, Any] | None = None
    ) -> None:
        type(self).failed = (job_id, error, result)

    async def set_progress(self, _job_id: str, progress: dict[str, Any]) -> None:
        type(self).progress.append(dict(progress))

    async def touch(self, _job_id: str) -> None:
        return None


def _job(kind: str = JOB_KIND_ESTUDIO_DAILY, account: str | None = "acc-1") -> AutoOpsJob:
    return AutoOpsJob(
        id="job-1",
        kind=kind,
        status=JOB_STATUS_RUNNING,
        day="2026-10-18",
        account_id=account,
        attempt=1,
    )


def _value_job(symbol: str | None = "SAN") -> AutoOpsJob:
    return AutoOpsJob(
        id="job-1",
        kind=JOB_KIND_DIA_D_VALUE_REPLAY,
        status=JOB_STATUS_RUNNING,
        day="2026-10-18",
        account_id="acc-1",
        attempt=1,
        payload={} if symbol is None else {"symbol": symbol, "instrumentId": symbol},
    )


def _settings(**overrides: Any) -> SimpleNamespace:
    base = {
        "auto_ops_job_stale_seconds": 300.0,
        "auto_ops_dia_d_timeout_seconds": 60.0,
        "auto_ops_job_interval_seconds": 2.0,
        "auto_ops_job_worker_enabled": True,
        "auto_ops_job_max_attempts": 5,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _factory() -> Any:
    """``session_factory()`` debe devolver un context manager async."""
    return _FakeSessions


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeJobRepo.job = None
    _FakeJobRepo.completed = None
    _FakeJobRepo.failed = None
    _FakeJobRepo.progress = []
    _FakeJobRepo.claim_kwargs = None
    _FakeJobRepo.exhausted_kwargs = None
    monkeypatch.setattr(worker, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    monkeypatch.setattr(worker, "get_settings", _settings)


@pytest.mark.asyncio
async def test_an_empty_queue_does_not_work() -> None:
    assert await worker.process_next_auto_ops_job(_factory()) is False
    assert _FakeJobRepo.completed is None
    assert _FakeJobRepo.failed is None


@pytest.mark.asyncio
async def test_a_successful_job_is_completed_with_its_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeJobRepo.job = _job()
    result = {"status": "ok", "scannedCount": 2}

    async def _run(job: Any, _factory: Any, **_kwargs: Any) -> dict[str, Any]:
        return result

    monkeypatch.setattr(worker, "run_auto_ops_job", _run)

    assert await worker.process_next_auto_ops_job(_factory()) is True
    assert _FakeJobRepo.completed == ("job-1", result)
    assert _FakeJobRepo.failed is None


@pytest.mark.asyncio
async def test_a_declared_failure_keeps_the_partial_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeJobRepo.job = _job()
    partial = {"status": "unavailable"}

    async def _run(job: Any, _factory: Any, **_kwargs: Any) -> dict[str, Any]:
        raise worker.AutoOpsJobFailed("universo no disponible", result=partial)

    monkeypatch.setattr(worker, "run_auto_ops_job", _run)

    assert await worker.process_next_auto_ops_job(_factory()) is True
    assert _FakeJobRepo.failed == (
        "job-1",
        "universo no disponible",
        partial,
    )
    assert _FakeJobRepo.completed is None


@pytest.mark.asyncio
async def test_an_unexpected_error_fails_closed_with_its_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeJobRepo.job = _job()

    async def _run(job: Any, _factory: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "run_auto_ops_job", _run)

    assert await worker.process_next_auto_ops_job(_factory()) is True
    assert _FakeJobRepo.failed is not None
    assert _FakeJobRepo.failed[0] == "job-1"
    assert _FakeJobRepo.failed[1].startswith("RuntimeError: boom")


@pytest.mark.asyncio
async def test_unknown_kind_fails_closed() -> None:
    with pytest.raises(worker.AutoOpsJobFailed, match="no soportado"):
        await worker.run_auto_ops_job(_job(kind="nope"), _factory())


@pytest.mark.asyncio
async def test_dia_d_replay_is_dispatched_to_the_subprocess_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def _run(job: Any, _factory: Any, *, timeout_seconds: float) -> dict[str, Any]:
        seen["job"] = job
        seen["timeout"] = timeout_seconds
        return {"day": job.day}

    monkeypatch.setattr(worker, "run_dia_d_replay_job", _run)

    result = await worker.run_auto_ops_job(
        _job(kind=JOB_KIND_DIA_D_REPLAY), _factory(), dia_d_timeout_seconds=42.0
    )

    assert result == {"day": "2026-10-18"}
    assert seen["timeout"] == 42.0


@pytest.mark.asyncio
async def test_estudio_daily_without_account_fails_before_touching_the_universe() -> None:
    with pytest.raises(worker.AutoOpsJobFailed, match="requiere cuenta"):
        await worker.run_auto_ops_job(_job(account=None), _factory())


@pytest.mark.asyncio
async def test_value_replay_is_dispatched_with_its_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def _run(
        job: Any, _factory: Any, *, timeout_seconds: float, symbol: str | None = None
    ) -> dict[str, Any]:
        seen["job"] = job
        seen["timeout"] = timeout_seconds
        seen["symbol"] = symbol
        return {"day": job.day, "symbol": symbol}

    monkeypatch.setattr(worker, "run_dia_d_replay_job", _run)

    result = await worker.run_auto_ops_job(
        _value_job("san"), _factory(), dia_d_timeout_seconds=42.0
    )

    assert result == {"day": "2026-10-18", "symbol": "SAN"}
    assert seen["symbol"] == "SAN"
    assert seen["timeout"] == 42.0


@pytest.mark.asyncio
async def test_value_replay_without_symbol_fails_closed_instead_of_running_the_whole_day() -> None:
    """Sin símbolo NO se cae al replay del día: escribiría otra evidencia (y pisaría la del día)."""
    with pytest.raises(worker.AutoOpsJobFailed, match="requiere 'symbol'"):
        await worker.run_auto_ops_job(_value_job(None), _factory())


@pytest.mark.asyncio
async def test_estudio_daily_reports_a_non_ok_universe_as_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = SimpleNamespace(
        status="unavailable",
        notes=["Universo ESTUDIO no disponible"],
        to_dict=lambda: {"status": "unavailable", "notes": ["universo no disponible"]},
    )

    class _Service:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def execute(self, *, account_id: str, as_of: str, on_progress: Any) -> Any:
            await on_progress({"phase": "universe", "done": 0, "total": 0})
            return report

    monkeypatch.setattr(daily_ops, "RunEstudioDailyOps", _Service)

    with pytest.raises(worker.AutoOpsJobFailed) as caught:
        await worker.run_auto_ops_job(_job(), _factory())

    assert caught.value.result == report.to_dict()
    assert _FakeJobRepo.progress == [{"phase": "universe", "done": 0, "total": 0}]


@pytest.mark.asyncio
async def test_a_partial_report_completes_the_job_with_its_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-3/H-145-3 — un parte con mediciones ausentes es un RESULTADO, no un fallo."""
    payload = {
        "status": "partial",
        "degraded": True,
        "degradedReasons": ["positions_unavailable"],
        "values": [],
    }
    report = SimpleNamespace(
        status="partial",
        degraded_reasons=["positions_unavailable"],
        notes=["allowTrading=true ..."],
        to_dict=lambda: payload,
    )

    class _Service:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def execute(self, *, account_id: str, as_of: str, on_progress: Any) -> Any:
            return report

    monkeypatch.setattr(daily_ops, "RunEstudioDailyOps", _Service)

    result = await worker.run_auto_ops_job(_job(), _factory())

    assert result == payload
    # Al NO lanzar ``AutoOpsJobFailed``, el tick lo guarda como ``completed``.
    assert _FakeJobRepo.failed is None


@pytest.mark.asyncio
async def test_the_configured_attempt_cap_is_forwarded_to_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H-145-5 — el tope es configurable y llega al reclamo y al cierre de agotados."""
    monkeypatch.setattr(
        worker, "get_settings", lambda: _settings(auto_ops_job_max_attempts=7)
    )
    assert await worker.process_next_auto_ops_job(_factory()) is False
    assert _FakeJobRepo.claim_kwargs is not None
    assert _FakeJobRepo.claim_kwargs["max_attempts"] == 7
    assert _FakeJobRepo.exhausted_kwargs is not None
    assert _FakeJobRepo.exhausted_kwargs["max_attempts"] == 7


@pytest.mark.asyncio
async def test_worker_switch_respects_the_disabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        worker, "get_settings", lambda: _settings(auto_ops_job_worker_enabled=False)
    )
    assert worker.start_auto_ops_job_worker(_factory()) is None

    monkeypatch.setattr(worker, "get_settings", _settings)
    task = worker.start_auto_ops_job_worker(_factory())
    assert task is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
