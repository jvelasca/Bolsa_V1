"""M7 (auditoría .183) — fallos del control plane y del turno dejan de ser mudos.

Tres huecos cerrados aquí:

1. **Universo/estrategia caducados**: un refresco fallido del watch o del decider se
   declara al motor, que sigue gestionando lo abierto (cerrar reduce riesgo) pero
   VETA ABRIR con el motivo propio ``control_plane_stale`` —no disfrazado de
   «reconciliación»—.
2. **Reintento a ciegas**: los fallos consecutivos del turno duplican la espera
   (``auto_sim_backoff_seconds``, acotada) y, al llegar al umbral, abren el breaker a
   ``PAUSED`` (``note_tick_failure``) en vez de martillear cada 60 s.
3. **Fallo sin rastro durable**: el turno fallido se matricula en el ledger del motor
   (``record_failure_tick`` → ``DEGRADED``/``PAUSED`` + ``activity=BLOCKED``), así que
   ni el monitor ni un reinicio leen «RUNNING» con el último tick bueno.

Los tests muerden: contra el código previo el loop no tenía backoff ni hooks, el
``_openings_vetoed`` no consultaba la frescura del control plane y un fallo del turno
no escribía ninguna fila.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from bolsa_api.background import auto_simulation_worker as sim
from bolsa_api.background.auto_simulation_worker import (
    CIRCUIT_BREAKER_PAUSED,
    CONTROL_PLANE_STALE,
    DECIDER_REFRESH_FAILED,
    WATCH_REFRESH_FAILED,
    AutoSimRuntime,
    AutoSimulationWorker,
    auto_sim_backoff_seconds,
    step_minute_clock,
)
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

_SYMBOLS = ("AAA", "GBP")


@pytest.fixture
def control_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")  # el loop no arranca solo.


def _decider(*, buy: set[str] = frozenset(), sell: set[str] = frozenset()) -> Any:
    def _d(symbol: str) -> DecisionPackage:
        if symbol in sell:
            return DecisionPackage(action="SELL", instrument_id=symbol, quantity=250.0)
        if symbol in buy:
            return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _worker() -> AutoSimulationWorker:
    _start, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    return AutoSimulationWorker(clock=clock, exec_store=InMemoryExecutionEventStore())


async def _open_symbol(worker: AutoSimulationWorker, symbol: str, *, max_minutes: int = 80) -> None:
    for _ in range(max_minutes):
        worker._decider = _decider(buy={symbol})  # noqa: SLF001 — seam de test.
        await worker.auto_turn()
        if symbol in worker.open_symbols:
            return
    raise AssertionError(f"el motor no abrió {symbol}: el escenario no llegó al caso")


@pytest.mark.asyncio
async def test_stale_control_plane_vetoes_openings_and_lets_exits_through(
    control_env: None,
) -> None:
    """Con el control plane caducado se CIERRA pero no se ABRE.

    Antes del cierre de M7 un refresco fallido sólo dejaba una línea de log: el turno
    siguiente abría con el universo anterior, indistinguible de un turno sano.
    """
    worker = _worker()
    await _open_symbol(worker, "AAA")
    assert "AAA" in worker.open_symbols

    worker.mark_control_stale(WATCH_REFRESH_FAILED)
    assert worker.control_plane_stale == (WATCH_REFRESH_FAILED,)
    assert worker._openings_vetoed("GBP") is True  # noqa: SLF001 — contrato del veto.

    worker._decider = _decider(buy={"GBP"})  # noqa: SLF001 — seam de test.
    report = await worker.auto_turn()
    assert report.fills == 0, "con universo caducado no se materializa ninguna apertura"
    assert CONTROL_PLANE_STALE in worker._last_gate_reason, (  # noqa: SLF001
        "el motivo declarado debe ser el del control plane, no «reconciliación»: "
        f"{worker._last_gate_reason!r}"  # noqa: SLF001
    )
    assert "GBP" not in worker.open_symbols

    # La salida NO se veta: reducir/cerrar nunca empeora el riesgo.
    worker._decider = _decider(sell={"AAA"})  # noqa: SLF001 — seam de test.
    closing = await worker.auto_turn()
    assert closing.fills >= 1, "con el control plane caducado la posición sigue cerrable"
    assert "AAA" not in worker.open_symbols

    # Levantar el token devuelve la capacidad de abrir: el veto era el control plane.
    worker.clear_control_stale(WATCH_REFRESH_FAILED)
    assert worker._openings_vetoed("GBP") is False  # noqa: SLF001 — contrato del veto.


@pytest.mark.asyncio
async def test_runtime_marks_the_specific_refresher_that_failed(control_env: None) -> None:
    """Cada refresco declara y levanta SU token: un éxito no perdona al otro."""
    runtime = AutoSimRuntime(object(), worker=_worker(), engine_id="auto-sim", account_id="acc")

    await runtime.note_control_failure(WATCH_REFRESH_FAILED)
    await runtime.note_control_failure(DECIDER_REFRESH_FAILED)
    assert runtime.worker.control_plane_stale == (
        DECIDER_REFRESH_FAILED,
        WATCH_REFRESH_FAILED,
    )

    await runtime.note_control_success(WATCH_REFRESH_FAILED)
    assert runtime.worker.control_plane_stale == (DECIDER_REFRESH_FAILED,)


def test_backoff_doubles_per_failure_and_is_capped() -> None:
    """Sin fallos el intervalo no cambia; con fallos se duplica hasta el tope."""
    assert auto_sim_backoff_seconds(60.0, 0) == 60.0
    assert auto_sim_backoff_seconds(60.0, 1, cap=300.0) == 120.0
    assert auto_sim_backoff_seconds(60.0, 2, cap=300.0) == 240.0
    assert auto_sim_backoff_seconds(60.0, 3, cap=300.0) == 300.0
    assert auto_sim_backoff_seconds(60.0, 10_000, cap=300.0) == 300.0
    # Un intervalo inválido no se convierte en espera negativa ni en ``inf``.
    assert auto_sim_backoff_seconds(-5.0, 2, cap=300.0) == 0.0


@pytest.mark.asyncio
async def test_loop_backs_off_reports_failures_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El loop declara cada fallo, espera más en cada uno y limpia al recuperar."""
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")

    delays: list[float] = []
    failures: list[int] = []
    successes = 0
    control_ok: list[str] = []

    class _FailingRuntime:
        async def run_tick(self) -> None:
            raise RuntimeError("tick roto")

        async def note_tick_failure(self, streak: int) -> bool:
            failures.append(streak)
            return False

        async def note_tick_success(self) -> None:
            nonlocal successes
            successes += 1

        async def note_control_success(self, reason: str) -> None:
            control_ok.append(reason)

        async def note_control_failure(self, reason: str) -> None:  # pragma: no cover
            raise AssertionError(f"no debía fallar el control plane: {reason}")

    async def _sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) >= 4:
            raise asyncio.CancelledError

    monkeypatch.setattr(sim.asyncio, "sleep", _sleep)

    async def _watch() -> None:
        return None

    async def _decider_refresh() -> None:
        return None

    task = asyncio.create_task(
        sim.auto_sim_loop(
            _FailingRuntime(),
            interval_seconds=60.0,
            watch_refresher=_watch,
            decider_refresher=_decider_refresh,
        )
    )
    with pytest.raises(asyncio.CancelledError):
        await task

    assert delays == [60.0, 120.0, 240.0, 300.0], (
        f"el backoff debe duplicar por fallo consecutivo y quedar acotado: {delays}"
    )
    assert failures == [1, 2, 3], f"cada fallo se declara con su racha: {failures}"
    assert control_ok == [WATCH_REFRESH_FAILED, DECIDER_REFRESH_FAILED] * 3, (
        "un refresco bueno levanta su token antes de operar"
    )
    assert successes == 0, "no hubo turno bueno: no se puede declarar recuperación"


@pytest.mark.asyncio
async def test_loop_clears_the_tick_streak_after_a_good_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tras fallar, un turno bueno reinicia la racha: el breaker no se abre por historia."""
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")

    delays: list[float] = []
    ticks = 0
    successes = 0

    class _FlakyRuntime:
        async def run_tick(self) -> None:
            nonlocal ticks
            ticks += 1
            if ticks == 1:
                raise RuntimeError("primer turno roto")

        async def note_tick_failure(self, streak: int) -> bool:
            assert streak == 1, f"la racha se reinicia con un turno bueno: {streak}"
            return False

        async def note_tick_success(self) -> None:
            nonlocal successes
            successes += 1

    async def _sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) >= 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(sim.asyncio, "sleep", _sleep)

    task = asyncio.create_task(sim.auto_sim_loop(_FlakyRuntime(), interval_seconds=60.0))
    with pytest.raises(asyncio.CancelledError):
        await task

    assert delays == [60.0, 120.0, 60.0], f"el intervalo vuelve al base al recuperar: {delays}"
    assert successes == 1


@pytest.mark.asyncio
async def test_runtime_breaker_pauses_and_needs_an_explicit_resume(control_env: None) -> None:
    """Tras el umbral el motor queda PAUSED: no se ejecutan turnos y las aperturas siguen vetadas."""
    runtime = AutoSimRuntime(object(), worker=_worker(), engine_id="auto-sim", account_id="acc")
    threshold = sim.auto_sim_breaker_failures()

    for streak in range(1, threshold):
        assert await runtime.note_tick_failure(streak) is False
    assert await runtime.note_tick_failure(threshold) is True
    assert runtime.paused_reason is not None
    assert runtime.paused_reason.startswith(CIRCUIT_BREAKER_PAUSED), runtime.paused_reason
    assert runtime.worker._openings_vetoed("AAA") is True  # noqa: SLF001 — contrato del veto.

    # El turno ni se intenta: la sesión es un ``object()`` que reventaría si se abriera.
    assert await runtime.run_tick() is None
    assert runtime.worker._last_gate_reason == (runtime.paused_reason,)  # noqa: SLF001

    runtime.resume()
    assert runtime.paused_reason is None
    assert runtime.tick_failure_streak == 0
    assert runtime.worker._openings_vetoed("AAA") is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_failure_tick_is_durable_and_declares_the_reason() -> None:
    """El turno fallido deja fila en el ledger: DEGRADED primero, PAUSED al abrir el breaker."""
    factory, _db = await _pg_factory_or_skip()
    import uuid

    from bolsa_application.auto_engine_state_store import PostgresAutoEngineStore

    engine_id = f"m7-{uuid.uuid4().hex[:10]}"
    runtime = AutoSimRuntime(factory, worker=_worker(), engine_id=engine_id, account_id="acc")

    await runtime.record_failure_tick("DEGRADED", "tick_failed:1")
    await runtime.record_failure_tick("PAUSED", f"{CIRCUIT_BREAKER_PAUSED}:3")

    async with factory() as session:
        snap = await PostgresAutoEngineStore(session).read(engine_id)
    assert snap is not None, "el fallo del turno debe quedar matriculado"
    assert snap.state == "PAUSED", snap.state
    assert snap.ticks == 2, f"cada turno fallido es un turno: {snap.ticks}"
    assert snap.last_reason == (f"{CIRCUIT_BREAKER_PAUSED}:3",), snap.last_reason
    assert snap.activity == "BLOCKED", snap.activity


async def _pg_factory_or_skip() -> tuple[Any, str]:
    """Factory PG real o ``skip`` (mismo criterio que la suite M4)."""
    import os
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — sin PG el test se salta (no finge verde).
        if os.environ.get("AUTO_M7_PG_REQUIRED") == "1":
            raise AssertionError(f"M7 PG requerido pero no disponible: {exc}") from exc
        pytest.skip(f"PostgreSQL no disponible para M7: {exc}")
    return create_session_factory(engine), os.environ.get("DB_NAME") or "bolsa_v1"


def test_worker_reports_stale_tokens_sorted(control_env: None) -> None:
    """La traza de frescura es determinista (orden estable) para poder compararla."""
    worker = _worker()
    worker.mark_control_stale(WATCH_REFRESH_FAILED)
    worker.mark_control_stale(DECIDER_REFRESH_FAILED)
    worker.mark_control_stale(WATCH_REFRESH_FAILED)  # idempotente
    assert worker.control_plane_stale == (
        DECIDER_REFRESH_FAILED,
        WATCH_REFRESH_FAILED,
    )
    assert worker._openings_vetoed("AAA") is True  # noqa: SLF001 — contrato del veto.
    worker.clear_control_stale(WATCH_REFRESH_FAILED)
    worker.clear_control_stale(WATCH_REFRESH_FAILED)  # idempotente
    assert worker.control_plane_stale == (DECIDER_REFRESH_FAILED,)


@pytest.mark.asyncio
async def test_paper_loop_declares_degraded_when_the_watch_refresh_throws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La lane SAFE/dry tampoco calla: un refresco que revienta deja el motor DEGRADED."""
    from bolsa_api.background import paper_auto_engine_worker as paper

    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_ENABLED", "1")
    paper.reset_watch_memory_for_tests()

    class _Engine:
        store = None
        _state = "RUNNING"

        def run_tick(self) -> None:
            return None

    engine = _Engine()
    calls = 0

    async def _broken_refresh() -> None:
        raise RuntimeError("ESTUDIO caído")

    async def _sleep(_delay: float) -> None:
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(paper.asyncio, "sleep", _sleep)

    task = asyncio.create_task(
        paper.paper_auto_engine_loop(engine, interval_seconds=1.0, watch_refresher=_broken_refresh)
    )
    with pytest.raises(asyncio.CancelledError):
        await task

    assert engine._state == "DEGRADED", (  # noqa: SLF001 — estado del motor SAFE.
        "un refresh que lanza no puede dejar el motor en RUNNING"
    )
