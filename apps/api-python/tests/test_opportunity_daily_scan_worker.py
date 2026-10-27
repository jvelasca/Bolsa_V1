"""T-2 — el scan diario de oportunidades corre en el primer tick y no duplica al reiniciar.

Dos defectos del worker OPPORTUNITY_DAILY_SCAN:

1. ``opportunity_daily_scan_worker_loop`` dormía ``interval`` (86 400 s por defecto) **antes**
   del primer ``_run_opportunity_daily_once``: un proceso recién arrancado no escaneaba hasta
   el día siguiente.
2. El único guard era ``_last_ran_day_key``, en memoria: con el primer tick inmediato, cada
   reinicio habría encolado otro scan del mismo día.

El dedupe durable vive en ``scan_jobs`` (``payload["opportunityDiscovery"]``), así que el
mismo universo/cuenta no se encola dos veces el mismo día UTC.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from bolsa_api.background import opportunity_daily_scan_worker as worker


class _SentinelStop(Exception):
    """Corta el bucle tras el primer ``sleep``."""


class _StubSession:
    def __init__(self) -> None:
        self.committed = 0
        self.rolled_back = 0

    async def __aenter__(self) -> _StubSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, _stmt: Any) -> Any:  # pragma: no cover — no se usa aquí
        raise AssertionError("esta prueba no consulta la BD")

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1


@pytest.fixture(autouse=True)
def _reset_day_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "_last_ran_day_key", None)


@pytest.mark.asyncio
async def test_daily_scan_runs_immediately_when_due(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reloj en hora de ejecución ⇒ el primer intento ocurre SIN esperar el intervalo."""
    events: list[Any] = []

    async def _once(_factory: Any) -> str:
        events.append("run")
        return worker._utc_day_key()

    async def _sleep(seconds: float) -> None:
        events.append(("sleep", seconds))
        raise _SentinelStop

    monkeypatch.setattr(worker, "_run_opportunity_daily_once", _once)
    monkeypatch.setattr(worker.asyncio, "sleep", _sleep)

    interval = max(300, int(worker.get_settings().opportunity_daily_scan_interval_seconds))
    with pytest.raises(_SentinelStop):
        await worker.opportunity_daily_scan_worker_loop(_StubSession)  # type: ignore[arg-type]

    assert events[0] == "run", "el primer tick debe ejecutarse antes de dormir"
    assert events[1] == ("sleep", interval)
    assert interval >= 300


@pytest.mark.asyncio
async def test_fresh_day_enqueues_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin job de hoy: se encola exactamente un scan y se sella el día."""
    enqueued: list[dict[str, Any]] = []

    async def _targets(_session: Any) -> list[dict[str, Any]]:
        return [{"accountId": None, "listId": "estudio", "proposeCap": 3}]

    async def _already(_session: Any) -> set[tuple[str, str | None]]:
        return set()

    class _Discovery:
        def __init__(self, _enqueue: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> Any:
            enqueued.append(kwargs)

            class _Job:
                id = "job-1"

            return _Job()

    monkeypatch.setattr(worker, "_resolve_targets", _targets)
    monkeypatch.setattr(worker, "_targets_already_enqueued_today", _already)
    monkeypatch.setattr(worker, "EnqueueOpportunityDailyScan", _Discovery)
    monkeypatch.setattr(worker, "get_enqueue_scan_job_use_case", lambda _s: object())

    session = _StubSession()
    day = await worker._run_opportunity_daily_once(lambda: session)  # type: ignore[arg-type]

    assert day == worker._utc_day_key()
    assert len(enqueued) == 1
    assert session.committed == 1


@pytest.mark.asyncio
async def test_restart_does_not_reenqueue_the_same_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """El guard es durable: si ya hay un discovery de hoy, el reinicio NO encola otro."""
    enqueued: list[dict[str, Any]] = []

    async def _targets(_session: Any) -> list[dict[str, Any]]:
        return [{"accountId": "acc-1", "listId": "estudio", "proposeCap": 3}]

    async def _already(_session: Any) -> set[tuple[str, str | None]]:
        return {("estudio", "acc-1")}

    class _Discovery:
        def __init__(self, _enqueue: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> Any:  # pragma: no cover — no debe llamarse
            enqueued.append(kwargs)
            raise AssertionError("no debe encolar dos veces el mismo día")

    monkeypatch.setattr(worker, "_resolve_targets", _targets)
    monkeypatch.setattr(worker, "_targets_already_enqueued_today", _already)
    monkeypatch.setattr(worker, "EnqueueOpportunityDailyScan", _Discovery)
    monkeypatch.setattr(worker, "get_enqueue_scan_job_use_case", lambda _s: object())

    session = _StubSession()
    day = await worker._run_opportunity_daily_once(lambda: session)  # type: ignore[arg-type]

    assert day == worker._utc_day_key()
    assert enqueued == []
    assert session.committed == 1


def test_day_start_is_utc_midnight() -> None:
    """El dedupe durable corta por día UTC, igual que ``_last_ran_day_key``."""
    assert worker._utc_day_key() == datetime.now(UTC).strftime("%Y-%m-%d")
    assert asyncio.iscoroutinefunction(worker._run_opportunity_daily_once)
