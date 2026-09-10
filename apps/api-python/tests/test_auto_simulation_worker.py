"""V2.22 / A9 (M5) — hermético del AutoSimulationWorker (bucle SIM-ONLY).

Sin PG ninguno: settlement contra ``InMemoryExecutionEventStore`` (M1/M2), reloj y
precio deterministas. Recorre un día autónomo BUY-then-SELL hasta dejar el libro
plano y valida que el day-journal (M7) es un día AUTO sano (orders/fills/
positions/exits, sin duplicados, venues {paper, simulated}, sin LIVE).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

import pytest
from bolsa_application.auto_daily_journal import build_auto_daily_report
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)

_SYMBOLS = ["AAA", "GBP"]


@pytest.fixture
def auto_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")  # OFF no dispara loop.


@pytest.mark.asyncio
async def test_auto_sim_worker_full_day_sim_only(auto_env: None) -> None:
    store = InMemoryExecutionEventStore()
    _start, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
    )
    await _open_all(worker, max_minutes=140)
    assert worker.open_symbols, "el día autónomo debería abrir posiciones SIM"
    await _close_all(worker, max_minutes=140)
    assert not worker.open_symbols, "el día debería cerrar el libro (exits>0)"

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert report.orders > 0
    assert report.fills > 0
    assert report.positions_created > 0
    assert report.exits > 0
    assert report.no_duplicate_execution_events
    assert report.all_venues_in_auto_sim
    assert report.no_live_bridge_posts
    assert report.ledger_balanced
    assert report.healthy, report.errors


async def _open_all(worker: AutoSimulationWorker, max_minutes: int) -> None:
    for _ in range(max_minutes):
        open_now = set(worker.open_symbols)
        worker._decider = _buy_decider(open_now, set(_SYMBOLS))
        await worker.auto_turn()
        if set(_SYMBOLS).issubset(worker.open_symbols):
            return


async def _close_all(worker: AutoSimulationWorker, max_minutes: int) -> None:
    for _ in range(max_minutes):
        to_close = tuple(worker.open_symbols)
        if not to_close:
            return
        worker._decider = _sell_decider(set(to_close))
        await worker.auto_turn()


@pytest.mark.asyncio
async def test_settle_persists_fill_finance_context(auto_env: None) -> None:
    """Bloque 5 (P1-05): cada fill deja contexto financiero durable por ``execution_id``."""
    from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

    store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()
    _start, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        context_store=ctx_store,
    )
    await _open_all(worker, max_minutes=140)
    assert ctx_store.size() > 0, "la liquidación debe persistir contexto por fill"
    # El contexto debe cubrir TODOS los execution_id confirmados (resolver durable).
    for row in worker.journal_pairs():
        if row.kind == "fill":
            ctx = await ctx_store.get(row.execution_id)
            assert ctx is not None, f"falta contexto durable para {row.execution_id}"
            assert ctx.side in {"buy", "sell"}
            assert ctx.quantity > 0 and ctx.price > 0


@pytest.mark.asyncio
async def test_readopt_prevents_second_buy_after_crash(auto_env: None) -> None:
    """Bloque 5 (P1-06 / G7): crash+restart readopta posición ⇒ NO segundo BUY."""
    from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

    store = InMemoryExecutionEventStore()
    pos_store = InMemorySimAutoPositionStore()
    account_id = "acc-readopt"

    # Día 1: abre AAA (queda espejado en el store durable).
    _s1, clock1 = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1, exec_store=store, position_store=pos_store, account_id=account_id
    )
    w1._decider = _buy_decider(set(), {"AAA"})
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) > 0

    # Crash y restart: nuevo worker sobre el MISMO espejo durable (G7).
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 9, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2, exec_store=store, position_store=pos_store, account_id=account_id
    )
    await w2.real_turn(
        exec_store=store,
        auto_store=None,
        finance_applier=None,
        account_id=account_id,
        position_store=pos_store,
    )
    assert w2._open.get("AAA", Decimal("0")) > 0, "debe readoptar la posición durable"
    # Un BUY sobre posición readoptada NO apila (guarda held>0).
    before = w2._open["AAA"]
    w2._decider = _buy_decider(set(), {"AAA"})
    await w2.auto_turn()
    assert w2._open["AAA"] == before, "no debe haber segundo BUY tras readopción"


@pytest.mark.asyncio
async def test_protective_stop_closes_position(auto_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bloque 6 (G8): caída ≥stop% desde la entrada ⇒ SELL de protección."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_PROTECTION", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_STOP_PCT", "0.02")
    monkeypatch.setenv("AUTO_ENGINE_SIM_T1_PCT", "0.0")  # aísla el SL
    monkeypatch.setenv("AUTO_ENGINE_SIM_TRAILING_PCT", "0.0")

    store = InMemoryExecutionEventStore()
    # Entrada a 100; luego el precio cae a 90 (−10% ⇒ dispara SL).
    prices = {"n": 0}

    def script(symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= len(_SYMBOLS) else 90.0

    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
        price_script=script,
    )
    worker._decider = _buy_decider(set(), {"AAA"})
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    # Siguiente tick (precio 90): la protección cierra sin esperar al decider.
    worker._decider = _hold_decider()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, "SL debe cerrar la posición"


@pytest.mark.asyncio
async def test_t1_exit_takes_profit(auto_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bloque 6 (G9): subida ≥T1% desde entrada ⇒ SELL de toma de beneficio."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_PROTECTION", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_STOP_PCT", "0.0")
    monkeypatch.setenv("AUTO_ENGINE_SIM_T1_PCT", "0.02")
    monkeypatch.setenv("AUTO_ENGINE_SIM_TRAILING_PCT", "0.0")

    store = InMemoryExecutionEventStore()
    prices = {"n": 0}

    def script(symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= len(_SYMBOLS) else 110.0

    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
        price_script=script,
    )
    worker._decider = _buy_decider(set(), {"AAA"})
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    worker._decider = _hold_decider()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, "T1 debe cerrar la posición"


@pytest.mark.asyncio
async def test_session_close_flattens_book(auto_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bloque 6: cierre por fin de sesión deja el libro plano (exits>0)."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_PROTECTION", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_SESSION_END_MINUTE", "2")
    store = InMemoryExecutionEventStore()
    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
    )
    worker._decider = _buy_decider(set(), {"AAA"})
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    worker._decider = _hold_decider()
    await worker.auto_turn()  # minuto 2 ≥ session_end ⇒ cierre
    assert worker._open.get("AAA", Decimal("0")) == 0, "fin de sesión debe aplanar"


def _hold_decider() -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


def _buy_decider(open_now: set[str], targets: set[str]) -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        if symbol in open_now or symbol not in targets:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _d


def _sell_decider(to_close: set[str]) -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        if symbol in to_close:
            return DecisionPackage(action="SELL", instrument_id=symbol, quantity=250.0)
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


# ── V2.28 / A10 (P1-02 real): atribución del fill a la versión de estrategia ────────


def test_strategy_version_from_source_extracts_active_version() -> None:
    from bolsa_api.background.auto_simulation_worker import _strategy_version_from_source

    assert _strategy_version_from_source("active-strategy:ver-123") == "ver-123"


def test_strategy_version_from_source_ignores_non_strategy_sources() -> None:
    from bolsa_api.background.auto_simulation_worker import _strategy_version_from_source

    assert _strategy_version_from_source("protection:protective_stop") is None
    assert _strategy_version_from_source("") is None
    assert _strategy_version_from_source(None) is None
    assert _strategy_version_from_source("active-strategy:") is None


@pytest.mark.asyncio
async def test_open_fills_carry_active_strategy_version(auto_env: None) -> None:
    """La apertura atribuye sus fills a la versión del ``DecisionPackage.source``."""
    from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

    store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()
    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
        context_store=ctx_store,
    )

    def _decider(symbol: str) -> DecisionPackage:
        if symbol == "AAA" and worker._open.get("AAA", Decimal("0")) <= 0:
            return DecisionPackage(
                action="BUY",
                instrument_id=symbol,
                quantity=250.0,
                source="active-strategy:ver-abc",
            )
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    worker._decider = _decider
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0, "debe abrir posición"

    rows = await ctx_store.list_for_strategy_version("ver-abc")
    assert rows, "los fills de apertura deben quedar atribuidos a la versión"
    assert all(r.side == "buy" for r in rows)


@pytest.mark.asyncio
async def test_close_by_protection_inherits_position_version(
    auto_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El cierre por protección hereda la versión que abrió la posición.

    Sin esta herencia, la serie de la versión tendría compras sin ventas y el PnL
    observado no cuadraría.
    """
    monkeypatch.setenv("AUTO_ENGINE_SIM_PROTECTION", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_STOP_PCT", "0.02")
    monkeypatch.setenv("AUTO_ENGINE_SIM_T1_PCT", "0.0")
    monkeypatch.setenv("AUTO_ENGINE_SIM_TRAILING_PCT", "0.0")

    from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

    store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= len(_SYMBOLS) else 90.0

    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
        price_script=script,
        context_store=ctx_store,
    )

    def _decider(symbol: str) -> DecisionPackage:
        if symbol == "AAA" and worker._open.get("AAA", Decimal("0")) <= 0:
            return DecisionPackage(
                action="BUY",
                instrument_id=symbol,
                quantity=250.0,
                source="active-strategy:ver-xyz",
            )
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    worker._decider = _decider
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0

    # El precio cae: la protección vende sin pasar por el decider (source=protection:*).
    worker._decider = _hold_decider()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, "SL debe cerrar"

    rows = await ctx_store.list_for_strategy_version("ver-xyz")
    sides = {r.side for r in rows}
    assert "buy" in sides
    assert "sell" in sides, "el cierre debe heredar la atribución de la apertura"


@pytest.mark.asyncio
async def test_deterministic_spine_fills_have_no_attribution(auto_env: None) -> None:
    """Sin estrategia ACTIVA, los fills no se atribuyen a ninguna versión."""
    from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

    store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()
    worker = AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))[1],
        exec_store=store,
        context_store=ctx_store,
    )
    await _open_all(worker, max_minutes=140)
    assert ctx_store.size() > 0, "debe haber fills"
    # Ninguno atribuido a una versión: el origen es el spine determinista.
    assert await ctx_store.list_for_strategy_version("ver-abc") == []
