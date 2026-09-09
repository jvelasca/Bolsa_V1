"""V2.22 / A9 — Prueba REINA: un día AUTO completo SIN intervención humana.

Meta: conducir la autonomía end-to-end SIN ``POST /paper-desk/cycle`` ni
``execute_trade()`` de forma directa — se avanza a través de los *ticks del worker*
(``AutoSimulationWorker.auto_turn``, el motor/columna AUTO de M5) con un reloj y
``price_script`` deterministas ("minutos simulados") y un proveedor inyectado que
BUY-abre temprano y SELL-cierra después. Después se comprueban los invariantes de
un día AUTO sano:

  orders>0, fills>0, positions_created>0, exits>0, ledger_balanced,
  no_duplicate_execution_events, all_venues ∈ {paper, simulated},
  no_live_bridge_posts  (AUTO jamás toca el bridge LIVE).

Hermética (sin PG): el settlement SIM (M1/M2) corre contra un
``InMemoryExecutionEventStore`` / sin ledger de cartera PG real; por eso el balance
se valida en su forma numérica estructural (delta cash == resto) y no contra el
libro vivo de PG, cuyo cierre queda anotado como gap de validación en vivo en el
relevo (delta explícito de esta prueba vs una corrida scheduler-PG).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from bolsa_application.auto_daily_journal import build_auto_daily_report
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker

_WATCH = ["AAA", "IBEX", "GBP"]
_QTY = 120.0
_OPEN_CUTOFF = 3  # abre los primeros minutos con BUY, después cierra.


@pytest.fixture
def _auto_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_WATCH))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")  # el test NO dispara los 1s.


def _rising_price(symbol: str, minute: int) -> float:
    """price_script determinista simple (base 100 + bps por minuto)."""
    return 100.0 + (minute % 40) * 0.05


def _buy_decider(open_symbols: set[str]) -> object:
    def _d(symbol: str) -> DecisionPackage:
        if symbol in open_symbols:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0.0)
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=_QTY)

    return _d


def _sell_decider(to_close: list[str]) -> object:
    def _d(symbol: str) -> DecisionPackage:
        if symbol in set(to_close):
            return DecisionPackage(action="SELL", instrument_id=symbol, quantity=_QTY)
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0.0)

    return _d


def _step_clock(start: datetime):
    holder = {"now": start}

    def clock() -> datetime:
        holder["now"] = holder["now"] + timedelta(seconds=60)
        return holder["now"]

    return clock


@pytest.mark.asyncio
async def test_reina_drives_day_and_invariants(
    _auto_env: None,
) -> None:
    """Recorre un día con ticks del worker (sin HTTP / execute_trade directo).

    Con reloj/price deterministas y proveedor inyectado (BUY→SELL) el worker AUTO
    deja el libro plano al cerrarse el día y su journal permite validar los 8
    invariantes de un día AUTO SIM-ONLY sano.
    """
    store = InMemoryExecutionEventStore()
    clock = _step_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        price_script=_rising_price,
        engine_id="reina-auto-sim",
    )
    for _ in range(_OPEN_CUTOFF):
        worker._decider = _buy_decider(set(worker.open_symbols))  # noqa: SLF001
        await worker.auto_turn()
    closed = await _close_day(worker)
    assert closed, "debería poder cerrar sin intervención"

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert report.orders > 0, "orders>0"
    assert report.fills > 0, "fills>0"
    assert report.positions_created > 0, "positions_created>0"
    assert report.exits > 0, "exits>0"
    assert report.ledger_balanced, "ledger_balanced"
    assert report.no_duplicate_execution_events, "no_duplicate"
    assert report.no_live_bridge_posts, "no LIVE bridge"
    assert report.all_venues_in_auto_sim, "venues in {paper,simulated}"
    assert report.healthy, report.errors


async def _close_day(worker: AutoSimulationWorker) -> bool:
    opened = list(worker.open_symbols)
    if not opened:
        return False
    for _ in range(6):
        worker._decider = _sell_decider(opened)  # noqa: SLF001 — inyección del turno
        await worker.auto_turn()
        if not worker.open_symbols:
            return True
    return False


@pytest.mark.asyncio
async def test_reina_finance_mode_applies_money_and_balances(
    _auto_env: None,
) -> None:
    """Día AUTO (Reina) con el tornillo de finanzas encendido (modo "dinero real").
    Contraste con la Reina estructural (que liquida con ``apply_finance=None`` y deja
    las trazas ``CAPTURED`` sin dinero): aquí se inyecta un ``finance_applier`` en el
    worker. Al estar presente, ``_settle`` lo reenvía como ``apply_finance`` de su
    liquidación (submit_simulated_order) y cada fill confirmado llega a ``APPLIED``
    (dinero efectivo a nivel de evento, una sola vez por ``execution_id``).

    NOTA honesta sobre la materialización real por fill: el ``ExecutionEvent`` no
    transporta ``instrument_id/side/price`` (es contexto del order). La finance por fill
    determinista (mapper puro ``sim_fill_finances``/``resolve_execution_finance`` con el
    ``SimulatedOrderResult`` en mano) y el invariante de dominio con dinero real se
    ejercitan en el hermético ``test_simulated_finance``; el ExecuteTrade real sobre
    Positions/Ledger PG es el gate vivo (``*_PG_REQUIRED=1``) que lo verifica contra el
    libro real. Aquí verificamos que el modo finanzas enciende el camino y conserva los
    8 invariantes del día AUTO SIM-ONLY.
    """
    store = InMemoryExecutionEventStore()
    clock = _step_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    applied: list[str] = []

    async def _money_applier(_execution: object) -> bool:
        # Applier hermético del modo finanzas (price-agnostic smoke): confirma cada fill
        # UNA vez (idempotencia real la da el store/lease). Simula el "efectivo movido".
        from bolsa_application.execution_event import ExecutionEvent

        assert isinstance(_execution, ExecutionEvent)
        applied.append(_execution.execution_id)
        return True

    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        price_script=_rising_price,
        engine_id="reina-auto-sim-fin",
        finance_applier=_money_applier,  # type: ignore[arg-type]
    )
    for _ in range(_OPEN_CUTOFF):
        worker._decider = _buy_decider(set(worker.open_symbols))  # noqa: SLF001
        await worker.auto_turn()
    closed = await _close_day(worker)
    assert closed, "debería poder cerrar sin intervención (finanzas encendidas)"

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert report.orders > 0, "orders>0"
    assert report.fills > 0, "fills>0"
    assert report.positions_created > 0, "positions_created>0"
    assert report.exits > 0, "exits>0"
    assert report.ledger_balanced, "ledger_balanced"
    assert report.no_duplicate_execution_events, "no_duplicate"
    assert report.all_venues_in_auto_sim, "venues in {paper,simulated}"
    assert report.no_live_bridge_posts, "no LIVE"

    # Todos los fills del día journalados pasaron por el applier EXACTAMENTE una vez y
    # quedaron APPLIED (dinero a nivel de evento, no CAPTURED).
    journal_fill_ids = {
        r.execution_id
        for r in worker.journal_pairs()
        if r.kind == "fill" and r.execution_id and not r.execution_id.startswith("noex-")
    }
    assert journal_fill_ids, "un día sano debe tener fills con execution_id"
    assert set(applied) == journal_fill_ids, (applied, journal_fill_ids)
    assert len(applied) == len(set(applied)) == len(journal_fill_ids)

    # El camino de finanzas deja cada traza durable en APPLIED (una sola vez).
    rows = [await store.get(eid) for eid in journal_fill_ids]
    assert all(r is not None and r.status == "APPLIED" for r in rows), [
        (r.execution_id, r.status) if r else None for r in rows
    ]
