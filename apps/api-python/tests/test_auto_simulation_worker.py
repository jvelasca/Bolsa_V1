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
