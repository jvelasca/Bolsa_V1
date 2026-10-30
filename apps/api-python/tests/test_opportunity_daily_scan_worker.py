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
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_api.background import opportunity_daily_scan_worker as worker


class _SentinelStop(Exception):
    """Corta el bucle tras el primer ``sleep``."""


async def _no_failures(_session: Any) -> list[dict[str, Any]]:
    """D-3 — sin discovery fallido hoy (caso sano)."""
    return []


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
    monkeypatch.setattr(worker, "_failed_discoveries_today", _no_failures)
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
    monkeypatch.setattr(worker, "_failed_discoveries_today", _no_failures)
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


def test_dedupe_keys_normalizes_the_discovery_payload() -> None:
    """D-3 — la clave del dedupe es ``(listId, cuenta)``, no el payload entero."""
    assert worker._dedupe_keys(
        [
            {"universe": {"listId": "estudio"}, "opportunityAccountId": "acc-1"},
            {"listId": "estudio", "opportunityAccountId": "acc-1"},
            # Sin cuenta (scan-only del funnel) y con ``listId`` plano: misma clave.
            {"universe": {"listId": "estudio"}},
            {"listId": "estudio"},
        ]
    ) == {("estudio", "acc-1"), ("estudio", None)}


@pytest.mark.asyncio
async def test_the_durable_dedupe_only_counts_live_or_completed_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-3 — un ``failed`` de hoy NO cuenta como encolado: el reinicio lo reintenta.

    Antes el dedupe no filtraba por estado: el job fallido bloqueaba el día entero y
    ``scan_queue_health`` (que solo mira ``pending``) no lo declaraba. Ahora la consulta
    del dedupe pide una lista de INCLUSIÓN y los fallidos se consultan aparte.
    """
    from bolsa_infrastructure.database.repositories.scan_job_repository import (
        SqlAlchemyScanJobRepository,
    )

    captured: dict[str, Any] = {}
    captured_failed: dict[str, Any] = {}

    async def _list(_self: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured.update(kwargs)
        return [{"universe": {"listId": "estudio"}}]

    async def _list_records(_self: Any, **kwargs: Any) -> list[Any]:
        captured_failed.update(kwargs)
        return []

    monkeypatch.setattr(SqlAlchemyScanJobRepository, "list_payloads_since", _list)
    monkeypatch.setattr(SqlAlchemyScanJobRepository, "list_since", _list_records)

    assert await worker._targets_already_enqueued_today(_StubSession()) == {
        ("estudio", None)
    }
    assert captured["statuses"] == worker.SCAN_DAILY_DEDUPE_STATUSES
    assert "failed" not in worker.SCAN_DAILY_DEDUPE_STATUSES

    await worker._failed_discoveries_today(_StubSession())
    assert captured_failed["statuses"] == ("failed",)


@pytest.mark.asyncio
async def test_a_failed_discovery_is_declared_and_the_day_is_retried(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-3 — el fallo del día se declara con su universo/cuenta y se reintenta YA."""
    enqueued: list[dict[str, Any]] = []

    async def _targets(_session: Any) -> list[dict[str, Any]]:
        return [{"accountId": "acc-1", "listId": "estudio", "proposeCap": 3}]

    async def _already(_session: Any) -> set[tuple[str, str | None]]:
        # El fallido NO está en el dedupe: el mismo día se vuelve a encolar.
        return set()

    async def _failed(_session: Any) -> list[Any]:
        return [
            SimpleNamespace(
                id="job-failed",
                payload={
                    "universe": {"listId": "estudio"},
                    "opportunityAccountId": "acc-1",
                },
            )
        ]

    class _Discovery:
        def __init__(self, _enqueue: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> Any:
            enqueued.append(kwargs)

            class _Job:
                id = "job-2"

            return _Job()

    monkeypatch.setattr(worker, "_resolve_targets", _targets)
    monkeypatch.setattr(worker, "_targets_already_enqueued_today", _already)
    monkeypatch.setattr(worker, "_failed_discoveries_today", _failed)
    monkeypatch.setattr(worker, "EnqueueOpportunityDailyScan", _Discovery)
    monkeypatch.setattr(worker, "get_enqueue_scan_job_use_case", lambda _s: object())

    with caplog.at_level("WARNING"):
        day = await worker._run_opportunity_daily_once(
            lambda: _StubSession()  # type: ignore[arg-type]
        )

    assert day == worker._utc_day_key()
    assert len(enqueued) == 1
    assert worker.SCAN_DAILY_FAILED_TODAY in caplog.text
    assert "job-failed" in caplog.text
    assert "acc-1" in caplog.text and "estudio" in caplog.text


@pytest.mark.asyncio
async def test_a_failed_discovery_is_retried_within_the_same_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-3 — el reintento NO exige reiniciar: con el día ya sellado, un fallido pendiente
    vuelve a encolar. El dedupe durable sigue evitando el duplicado (un job vivo cubre la
    clave), así que los reintentos quedan serializados uno a uno."""
    enqueued: list[dict[str, Any]] = []

    async def _targets(_session: Any) -> list[dict[str, Any]]:
        return [{"accountId": "acc-1", "listId": "estudio", "proposeCap": 3}]

    async def _already(_session: Any) -> set[tuple[str, str | None]]:
        return set()

    async def _failed(_session: Any) -> list[Any]:
        return [
            SimpleNamespace(
                id="job-failed",
                payload={
                    "universe": {"listId": "estudio"},
                    "opportunityAccountId": "acc-1",
                },
            )
        ]

    class _Discovery:
        def __init__(self, _enqueue: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> Any:
            enqueued.append(kwargs)

            class _Job:
                id = "job-retry"

            return _Job()

    monkeypatch.setattr(worker, "_resolve_targets", _targets)
    monkeypatch.setattr(worker, "_targets_already_enqueued_today", _already)
    monkeypatch.setattr(worker, "_failed_discoveries_today", _failed)
    monkeypatch.setattr(worker, "EnqueueOpportunityDailyScan", _Discovery)
    monkeypatch.setattr(worker, "get_enqueue_scan_job_use_case", lambda _s: object())
    # El día YA se intentó en este proceso: sin el reintento intra-proceso, el fallo
    # dejaría el día sin discovery hasta el siguiente reinicio.
    monkeypatch.setattr(worker, "_last_ran_day_key", worker._utc_day_key())

    day = await worker._run_opportunity_daily_once(lambda: _StubSession())  # type: ignore[arg-type]

    assert day == worker._utc_day_key()
    assert len(enqueued) == 1


@pytest.mark.asyncio
async def test_no_retry_and_no_warning_when_the_slot_is_already_covered(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-3 — si un job vivo/completado ya cubre la clave, el fallido NO se reintenta.

    El aviso ``scan_daily_failed_today`` afirma «se REINTENTA»: solo puede emitirse cuando
    de verdad hay un reintento por delante. Con la clave cubierta, el proceso no encola ni
    declara nada nuevo (y el guard del día corta el tick).
    """
    enqueued: list[dict[str, Any]] = []

    async def _targets(_session: Any) -> list[dict[str, Any]]:
        return [{"accountId": "acc-1", "listId": "estudio", "proposeCap": 3}]

    async def _already(_session: Any) -> set[tuple[str, str | None]]:
        # El reintento de ayer/antes de hoy ya está vivo o completado.
        return {("estudio", "acc-1")}

    async def _failed(_session: Any) -> list[Any]:
        return [
            SimpleNamespace(
                id="job-failed",
                payload={
                    "universe": {"listId": "estudio"},
                    "opportunityAccountId": "acc-1",
                },
            )
        ]

    class _Discovery:
        def __init__(self, _enqueue: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> Any:  # pragma: no cover — no se usa
            enqueued.append(kwargs)
            raise AssertionError("no hay nada que reintentar")

    monkeypatch.setattr(worker, "_resolve_targets", _targets)
    monkeypatch.setattr(worker, "_targets_already_enqueued_today", _already)
    monkeypatch.setattr(worker, "_failed_discoveries_today", _failed)
    monkeypatch.setattr(worker, "EnqueueOpportunityDailyScan", _Discovery)
    monkeypatch.setattr(worker, "get_enqueue_scan_job_use_case", lambda _s: object())
    monkeypatch.setattr(worker, "_last_ran_day_key", worker._utc_day_key())

    session = _StubSession()
    with caplog.at_level("WARNING"):
        day = await worker._run_opportunity_daily_once(lambda: session)  # type: ignore[arg-type]

    assert day is None
    assert enqueued == []
    assert worker.SCAN_DAILY_FAILED_TODAY not in caplog.text
