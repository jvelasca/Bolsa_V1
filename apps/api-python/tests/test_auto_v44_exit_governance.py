"""V2.44 (AUTO-3 slice 2) — el gobernador gobierna también el CICLO DE VIDA.

Cuatro invariantes que este fichero muerde, con el camino REAL del worker
(``auto_turn`` → ``_v2_plan_tick`` / ``_v2_position_package``):

* Un ``RiskRegime == RISK_OFF`` real transforma una posición abierta en ``RISK_EXIT``
  (venta total), por encima de objetivo/trailing/tiempo.
* Un ``HardKillSwitch`` latcheado veta ENTRADAS (``governor_halted``) sin congelar la
  salida protectora: reducir riesgo nunca empeora.
* ``market_data`` stale ⇒ NO ENTRY, pero la salida protectora sigue permitida.
* Una salida deja una reserva ``sell`` VIVA y durable que se libera por fill (parcial
  incluido), de modo que un reinicio no puede re-emitir la MISMA orden.

Hermético: sin PG, sin red y con reloj/precios deterministas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.account_drawdown import EquityMarkBook
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

_SYMBOLS = ["AAA"]


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


def _buy() -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _d


def _hold() -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _trade_kwargs() -> dict[str, object]:
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _edge(_ref: str, _account: str | None) -> float | None:
        return 0.9

    return {
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": EdgeReportSource(reader=_edge),
    }


def _worker(**kwargs: object) -> AutoSimulationWorker:
    defaults: dict[str, object] = dict(_trade_kwargs())
    defaults.setdefault("exec_store", InMemoryExecutionEventStore())
    defaults.update(kwargs)
    return AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))[1],
        **defaults,  # type: ignore[arg-type]
    )


def _journal_reasons(worker: AutoSimulationWorker) -> list[str]:
    return [
        code
        for entry in worker._v2_journal
        if entry.payload is not None
        for code in entry.payload.get("reasonCodes", ())
    ]


@pytest.mark.asyncio
async def test_v2_risk_off_liquidates_open_position_with_risk_exit(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un drawdown real ⇒ ``RISK_OFF`` ⇒ la posición abierta se liquida con ``RISK_EXIT``.

    Control del tramo: el mismo tick con DD benigno (12 % ⇒ ``ENTRY_RESTRICTED``) NO
    liquida: la restricción veta APERTURAS, no cierra posiciones. La liquidación es del
    eje de RIESGO, no de un veto de entrada disfrazado.
    """
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")
    marks = EquityMarkBook()
    worker = _worker(equity_marks=marks)
    worker._decider = _buy()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0

    # 12 % ⇒ ENTRY_RESTRICTED: la posición NO se toca (el veto es de aperturas).
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "88000")
    worker._decider = _hold()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    assert worker._v2_snapshot(worker._v2_regime()).drawdown_pct == pytest.approx(12.0)

    # 16 % ⇒ NO_ENTRY ⇒ RiskRegime RISK_OFF ⇒ RISK_EXIT (venta total).
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, "RISK_OFF debe liquidar la posición"
    assert "risk_exit" in worker._v2_last_exit_reasons["AAA"]
    assert "risk_exit" in _journal_reasons(worker)


@pytest.mark.asyncio
async def test_v2_hard_kill_switch_vetoes_entry_with_governor_halted(v2_env: None) -> None:
    """La parada DURA veta la apertura incluso con el gobernador OFF (independencia)."""
    worker = _worker()
    assert worker._v2_tunables.governor_enabled is False
    assert worker.engage_kill_switch("MANUAL_KILL", at="2026-09-15T09:00:00Z") is True
    worker._decider = _buy()
    await worker.auto_turn()
    assert worker.open_symbols == (), "con la parada activa no se abre nada"
    assert "governor_halted" in _journal_reasons(worker)
    # Latcheada: reavisar no la libera ni cambia el motivo original.
    assert worker.release_kill_switch(reconciliation_ok=False) is False
    assert worker._v2_kill_switch_halted() is True


@pytest.mark.asyncio
async def test_v2_halt_forces_protective_exit_not_congelation(v2_env: None) -> None:
    """La parada bloquea ENTRADAS pero la salida protectora sigue viva (invariante de oro)."""
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 96.0

    worker = _worker(price_script=script)
    worker._decider = _buy()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0

    worker.engage_kill_switch("DATA_CORRUPTION", at="2026-09-15T09:01:00Z")
    worker._decider = _hold()
    await worker.auto_turn()  # precio 96 ≤ stop: con la parada activa debe VENDER, no congelar
    assert worker._open.get("AAA", Decimal("0")) == 0
    assert "kill_switch" in worker._v2_last_exit_reasons["AAA"]


@pytest.mark.asyncio
async def test_v2_stale_market_data_vetoes_entry_but_allows_protective_exit(
    v2_env: None,
) -> None:
    """Frescura por dimensión: mercado stale ⇒ no entry; la salida protectora sigue."""
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 96.0

    worker = _worker(price_script=script)
    worker._decider = _buy()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0

    # Mercado con 1000 s de antigüedad (umbral 300) ⇒ el snapshot publica stale.
    now = worker._v2_marks_now().timestamp()
    worker._v2_data_timestamps["market_data"] = now - 1000.0
    assert worker._v2_snapshot(worker._v2_regime()).data_is_fresh is False

    worker._decider = _hold()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, (
        "la salida protectora NO se bloquea por datos stale"
    )


@pytest.mark.asyncio
async def test_v2_stale_data_blocks_new_entry(v2_env: None) -> None:
    worker = _worker()
    now = worker._v2_marks_now().timestamp()
    worker._v2_data_timestamps["market_data"] = now - 1000.0
    worker._decider = _buy()
    await worker.auto_turn()
    assert worker.open_symbols == ()
    assert "stale_data" in _journal_reasons(worker)


@pytest.mark.asyncio
async def test_v2_exit_leaves_a_live_sell_reservation_released_by_fill(
    v2_env: None,
) -> None:
    """Una salida crea reserva ``sell`` durable y la libera por fill (parcial incluido)."""
    account_id = "acc-v44-exit-res"
    store = InMemoryExecutionEventStore()
    res_store = InMemoryReservationStore()
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 96.0

    worker = _worker(
        exec_store=store,
        reservation_store=res_store,
        account_id=account_id,
        price_script=script,
    )
    worker._decider = _buy()
    await worker.auto_turn()
    worker._decider = _hold()
    await worker.auto_turn()  # stop-out ⇒ SELL con reserva de salida

    rows = await res_store.list_all(account_id)
    sells = [row for row in rows if row.side == "sell"]
    assert sells, "la salida debe dejar una reserva sell auditable"
    assert all(row.is_released for row in sells), "el fill debe liberar la reserva de salida"
    assert await res_store.list_live(account_id) == [], "no queda compromiso vivo"
    assert worker._v2_reservations == ()


# ── Golden Day dinámico (ENTRY → RESTRICTED → RISK_EXIT → FLAT) + crash ────────
#
# El escenario del roadmap, con reinicio dentro de cada fase: la escalera de drawdown
# manda la decisión y un reinicio no puede duplicar órdenes, reservas ni P&L.


def _golden_worker(
    *,
    store: InMemoryExecutionEventStore,
    contexts: object,
    reservations: InMemoryReservationStore,
    positions: InMemorySimAutoPositionStore,
    account_id: str,
    marks: EquityMarkBook,
    minute: int,
    exit_orders: InMemoryExitOrderStore | None = None,
) -> AutoSimulationWorker:
    _s, clock = step_minute_clock(datetime(2026, 9, 15, 9, minute, tzinfo=UTC))
    return AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        context_store=contexts,
        reservation_store=reservations,
        position_store=positions,
        exit_order_store=exit_orders,
        account_id=account_id,
        equity_marks=marks,
        price_script=lambda _symbol, _minute: 100.0,
        **_trade_kwargs(),
    )


@pytest.mark.asyncio
async def test_v2_golden_day_dynamic_entry_risk_exit_flat_with_restart(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T0 DD 0 % → ENTRY; T1 DD 12 % → RESTRICTED (no liquida); T2 DD 16 % → RISK_EXIT → FLAT."""
    from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")
    account_id = "acc-golden"
    marks = EquityMarkBook()
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    reservations = InMemoryReservationStore()
    positions = InMemorySimAutoPositionStore()
    exit_orders = InMemoryExitOrderStore()

    w1 = _golden_worker(
        store=store,
        contexts=contexts,
        reservations=reservations,
        positions=positions,
        account_id=account_id,
        marks=marks,
        minute=0,
        exit_orders=exit_orders,
    )
    w1._decider = _buy()
    await w1.auto_turn()  # T0: DD 0 % ⇒ ENTRY_ALLOWED
    assert w1._open.get("AAA", Decimal("0")) > 0

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "88000")  # T1: DD 12 %
    w1._decider = _hold()
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) > 0, "ENTRY_RESTRICTED no liquida"

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # T2: DD 16 % ⇒ RISK_OFF
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) == 0, "T2 debe dejar la posición FLAT"
    assert "risk_exit" in w1._v2_last_exit_reasons["AAA"]

    # Crash + reinicio: los stores durables sobreviven, la RAM no.
    w2 = _golden_worker(
        store=store,
        contexts=contexts,
        reservations=reservations,
        positions=positions,
        account_id=account_id,
        marks=marks,
        minute=1,
        exit_orders=exit_orders,
    )
    await w2.readopt_positions()
    await w2._v2_reconcile_reservations(startup=True)
    w2._decider = _hold()
    await w2.auto_turn()
    assert w2._open.get("AAA", Decimal("0")) == 0, "tras el reinicio sigue FLAT"
    assert await reservations.list_live(account_id) == [], "sin compromisos vivos"
    # V2.43.3 (P0-2): la salida del día dorado tiene UNA identidad durable y queda cerrada.
    assert await exit_orders.list_open(account_id) == [], "ningún INTENT de salida abierto"
    intents = list(exit_orders._rows.values())  # noqa: SLF001 — lectura de test.
    assert len(intents) == 1, "exactly-once del INTENT de salida en todo el día"
    assert intents[0].state == "FILLED"
    assert intents[0].filled_qty == 200.0


@pytest.mark.asyncio
async def test_v2_restart_mid_risk_exit_releases_the_dead_sell_reservation_once(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crash DESPUÉS de decidir ``RISK_EXIT`` y ANTES del fill: una sola venta al reiniciar.

    La salida deja una reserva ``sell`` VIVA. Al reiniciar, la reconciliación ve que la
    orden no se llenó ni está en vuelo y la libera por ``restart``: el rebote no duplica
    la reserva. Después, la gestión vuelve a pedir la salida UNA vez y converge a FLAT.
    """
    from bolsa_analytics.cognitive.portfolio_reservation import (
        RESERVATION_RELEASED_BY_RESTART,
        SIDE_SELL,
        build_reservation,
    )
    from bolsa_application.execution_event import ExecutionEvent, apply_execution_financial_once
    from bolsa_application.reservation_store import InMemoryReservationStore
    from bolsa_application.sim_durable_store import (
        InMemorySimFillFinanceContextStore,
        SimFillFinanceContext,
    )

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")
    account_id = "acc-golden-crash"
    marks = EquityMarkBook()
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    reservations = InMemoryReservationStore()
    positions = InMemorySimAutoPositionStore()

    async def _finance(_event: object) -> bool:
        return True

    # Estado durable de ANTES del crash: posición 200 materializada (fill APPLIED con su
    # contexto) y la reserva de la salida decidida pero aún sin fill.
    buy = ExecutionEvent(
        execution_id="buy-seed-1",
        order_id="o-seed",
        venue="paper",
        venue_order_id="v-seed",
        fill_seq=1,
        qty=Decimal("200"),
        account_id=account_id,
    )
    await store.capture(buy)
    await apply_execution_financial_once(store, execution=buy, apply_finance=_finance)
    await contexts.save(
        SimFillFinanceContext(
            execution_id="buy-seed-1",
            instrument_id="AAA",
            side="buy",
            quantity=Decimal("200"),
            price=Decimal("100"),
            account_id=account_id,
        )
    )
    await positions.upsert(
        account_id,
        "auto-sim",
        "AAA",
        Decimal("200"),
        entry_price=Decimal("100"),
        high_watermark=Decimal("100"),
        stop_price=Decimal("97"),
    )
    await reservations.save(
        build_reservation(
            reservation_id="exit-seed-1",
            account_id=account_id,
            instrument_id="AAA",
            side=SIDE_SELL,
            quantity=200.0,
            entry=100.0,
            sector="tech",
            reserved_cash=0.0,
            reserved_risk=0.0,
            created_at="2026-09-15T09:01:00Z",
        )
    )
    marks.update(account_id, 100000.0, now=datetime(2026, 9, 15, 9, 0, tzinfo=UTC))

    # Reinicio sobre los MISMOS stores.
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # RISK_OFF
    _s, clock = step_minute_clock(datetime(2026, 9, 15, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        context_store=contexts,
        reservation_store=reservations,
        position_store=positions,
        account_id=account_id,
        equity_marks=marks,
        price_script=lambda _symbol, _minute: 100.0,
        **_trade_kwargs(),
    )
    await w2.readopt_positions()
    await w2._v2_reconcile_reservations(startup=True)

    rows = await reservations.list_all(account_id)
    dead = [row for row in rows if row.reservation_id == "exit-seed-1"]
    assert dead and dead[0].status == RESERVATION_RELEASED_BY_RESTART, (
        "la orden muerta se libera al reiniciar (nunca queda viva para re-emitirse doble)"
    )
    assert await reservations.list_live(account_id) == []

    # La gestión re-emite la salida UNA vez y deja la posición plana.
    w2._decider = _hold()
    await w2.auto_turn()
    assert w2._open.get("AAA", Decimal("0")) == 0
    assert await reservations.list_live(account_id) == []


@pytest.mark.asyncio
async def test_v2_restart_crash_before_reserving_still_closes_once_with_a_durable_intent(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V2.43.3 (P0-2/C1): crash ANTES de reservar. No hay reserva ni INTENT: solo la posición.

    La ventana más peligrosa del ciclo de salida: la decisión se tomó, el proceso murió antes
    de dejar rastro. Al reiniciar no hay nada que reconciliar, así que la gestión vuelve a
    decidir (RISK_OFF sigue) y la salida se emite EXACTAMENTE UNA vez, ahora con identidad
    durable (``exit_order_id``) que el reinicio posterior puede seguir.
    """
    from bolsa_application.execution_event import ExecutionEvent, apply_execution_financial_once
    from bolsa_application.sim_durable_store import (
        InMemorySimFillFinanceContextStore,
        SimFillFinanceContext,
    )

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # RISK_OFF desde el arranque
    account_id = "acc-golden-pre-reserve"
    marks = EquityMarkBook()
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    reservations = InMemoryReservationStore()
    positions = InMemorySimAutoPositionStore()
    exit_orders = InMemoryExitOrderStore()

    async def _finance(_event: object) -> bool:
        return True

    # Estado durable de ANTES del crash: SOLO la posición materializada. Ni reserva de
    # salida ni INTENT (el proceso murió en la ventana).
    buy = ExecutionEvent(
        execution_id="buy-pre-reserve",
        order_id="o-pre-reserve",
        venue="paper",
        venue_order_id="v-pre-reserve",
        fill_seq=1,
        qty=Decimal("200"),
        account_id=account_id,
    )
    await store.capture(buy)
    await apply_execution_financial_once(store, execution=buy, apply_finance=_finance)
    await contexts.save(
        SimFillFinanceContext(
            execution_id="buy-pre-reserve",
            instrument_id="AAA",
            side="buy",
            quantity=Decimal("200"),
            price=Decimal("100"),
            account_id=account_id,
        )
    )
    await positions.upsert(
        account_id,
        "auto-sim",
        "AAA",
        Decimal("200"),
        entry_price=Decimal("100"),
        high_watermark=Decimal("100"),
        stop_price=Decimal("97"),
    )
    marks.update(account_id, 100000.0, now=datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    assert await reservations.list_all(account_id) == []
    assert await exit_orders.list_open(account_id) == []

    w = _golden_worker(
        store=store,
        contexts=contexts,
        reservations=reservations,
        positions=positions,
        account_id=account_id,
        marks=marks,
        minute=1,
        exit_orders=exit_orders,
    )
    await w.readopt_positions()
    await w._v2_reconcile_reservations(startup=True)  # no-op: no hay nada que reconciliar
    w._decider = _hold()
    await w.auto_turn()

    assert w._open.get("AAA", Decimal("0")) == 0, "la salida pendiente se ejecuta al reiniciar"
    assert await reservations.list_live(account_id) == []
    intents = list(exit_orders._rows.values())  # noqa: SLF001 — lectura de test.
    assert len(intents) == 1, "un INTENT, no uno por tick"
    assert intents[0].state == "FILLED"
    assert intents[0].emergency is False
