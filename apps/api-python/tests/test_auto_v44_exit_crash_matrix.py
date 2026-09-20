"""V2.43.3 (AUTO-3 cierre) — matriz de crash sobre la identidad de SALIDA y el HALT.

Cuatro ventanas de crash, las que la auditoría de ``v2.43.2-beta`` señaló como no cubiertas
porque la identidad de una salida y la parada dura vivían en la RAM del proceso:

    C1  decisión tomada  →  crash ANTES de reservar
    C2  reserva persistida  →  crash ANTES de emitir
    C3  orden emitida  →  crash ANTES de que el fill sea APPLIED
    C4  fill PARCIAL aplicado  →  crash

En las cuatro, el reinicio se modela como lo que es: la RAM se pierde y se construye un
worker NUEVO sobre los MISMOS stores durables. La convergencia que se exige es la misma:

* exactly-once del INTENT de salida (un ``exit_order_id``, no uno por reintento);
* sin reserva de salida duplicada y sin ejecución duplicada;
* posición correcta tras reconciliar y operar;
* estado del latch/kill coherente (nunca se levanta solo).

Hermético: sin PG, sin red, reloj y precios deterministas. El guard ``AUTO_ENGINE_SIM_V2_*``
es el mismo del camino real (``auto_turn``), no un atajo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple, Protocol

import pytest

from bolsa_analytics.cognitive.exit_order import build_exit_order
from bolsa_analytics.cognitive.portfolio_reservation import (
    RESERVATION_RELEASED_BY_RESTART,
    SIDE_SELL,
    build_reservation,
)
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.account_drawdown import EquityMarkBook
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import (
    ExecutionEvent,
    InMemoryExecutionEventStore,
    apply_execution_financial_once,
)
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.kill_switch_store import InMemoryKillSwitchStore
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)

ACCOUNT_ID = "acc-crash-matrix"
ENGINE_ID = "auto-sim"


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    # RISK_OFF fuerza el cierre: es el escenario de la salida protectora.
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")


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


class _Stores:
    """Los cinco espejos durables que sobreviven a un crash (la RAM no)."""

    def __init__(self) -> None:
        self.exec_store = InMemoryExecutionEventStore()
        self.contexts = InMemorySimFillFinanceContextStore()
        self.reservations = InMemoryReservationStore()
        self.positions = InMemorySimAutoPositionStore()
        self.exit_orders = InMemoryExitOrderStore()
        self.kill_state = InMemoryKillSwitchStore()
        self.marks = EquityMarkBook()


def _restart(stores: _Stores, *, minute: int) -> AutoSimulationWorker:
    _s, clock = step_minute_clock(datetime(2026, 9, 15, 9, minute, tzinfo=UTC))
    return AutoSimulationWorker(
        clock=clock,
        exec_store=stores.exec_store,
        context_store=stores.contexts,
        reservation_store=stores.reservations,
        position_store=stores.positions,
        exit_order_store=stores.exit_orders,
        kill_switch_store=stores.kill_state,
        account_id=ACCOUNT_ID,
        equity_marks=stores.marks,
        price_script=lambda _symbol, _minute: 100.0,
        **_trade_kwargs(),
    )


async def _seed_buy_position(
    stores: _Stores, *, execution_id: str, qty: Decimal, price: Decimal
) -> None:
    """Materializa una posición de compra durable (fill APPLIED + contexto + proyección)."""

    async def _finance(_event: object) -> bool:
        return True

    buy = ExecutionEvent(
        execution_id=execution_id,
        order_id=f"o-{execution_id}",
        venue="paper",
        venue_order_id=f"v-{execution_id}",
        fill_seq=1,
        qty=qty,
        account_id=ACCOUNT_ID,
    )
    await stores.exec_store.capture(buy)
    await apply_execution_financial_once(
        stores.exec_store, execution=buy, apply_finance=_finance
    )
    await stores.contexts.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id="AAA",
            side="buy",
            quantity=qty,
            price=price,
            account_id=ACCOUNT_ID,
        )
    )
    await stores.positions.upsert(
        ACCOUNT_ID,
        ENGINE_ID,
        "AAA",
        qty,
        entry_price=price,
        high_watermark=price,
        stop_price=price * Decimal("0.97"),
    )
    stores.marks.update(ACCOUNT_ID, 100000.0, now=datetime(2026, 9, 15, 9, 0, tzinfo=UTC))


async def _seed_emit_before_applied(
    stores: _Stores, *, execution_id: str, qty: Decimal, price: Decimal
) -> None:
    """Una orden capturada pero NO aplicada: está en vuelo (ni muerta ni materializada)."""
    sell = ExecutionEvent(
        execution_id=execution_id,
        order_id=f"o-{execution_id}",
        venue="paper",
        venue_order_id=f"v-{execution_id}",
        fill_seq=1,
        qty=qty,
        account_id=ACCOUNT_ID,
        status="CAPTURED",
    )
    await stores.exec_store.capture(sell)
    await stores.contexts.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id="AAA",
            side="sell",
            quantity=qty,
            price=price,
            account_id=ACCOUNT_ID,
        )
    )


async def _seed_partial_sell_fill(
    stores: _Stores, *, execution_id: str, qty: Decimal, price: Decimal
) -> None:
    """Un fill de venta PARCIAL ya aplicado (la cola del INTENT sigue viva)."""

    async def _finance(_event: object) -> bool:
        return True

    sell = ExecutionEvent(
        execution_id=execution_id,
        order_id=f"o-{execution_id}",
        venue="paper",
        venue_order_id=f"v-{execution_id}",
        fill_seq=1,
        qty=qty,
        account_id=ACCOUNT_ID,
    )
    await stores.exec_store.capture(sell)
    await apply_execution_financial_once(
        stores.exec_store, execution=sell, apply_finance=_finance
    )
    await stores.contexts.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id="AAA",
            side="sell",
            quantity=qty,
            price=price,
            account_id=ACCOUNT_ID,
        )
    )


async def _seed_live_sell_reservation(
    stores: _Stores, *, reservation_id: str, qty: float, at: str
) -> None:
    await stores.reservations.save(
        build_reservation(
            reservation_id=reservation_id,
            account_id=ACCOUNT_ID,
            instrument_id="AAA",
            side=SIDE_SELL,
            quantity=qty,
            entry=100.0,
            sector="tech",
            reserved_cash=0.0,
            reserved_risk=0.0,
            created_at=at,
        )
    )


async def _seed_exit_intent(
    stores: _Stores, *, exit_order_id: str, reservation_id: str, qty: float, at: str
) -> None:
    order = build_exit_order(
        exit_order_id=exit_order_id,
        instrument_id="AAA",
        side=SIDE_SELL,
        requested_qty=qty,
        account_id=ACCOUNT_ID,
        engine_id=ENGINE_ID,
        created_at=at,
        updated_at=at,
    )
    assert order is not None
    await stores.exit_orders.save(order.with_reserved(reservation_id, at=at))


class _SellFill(NamedTuple):
    execution_id: str
    order_id: str
    qty: Decimal
    status: str


async def _sell_fills(stores: _Stores) -> list[_SellFill]:
    """Todos los fills de venta durables, con la identidad LÓGICA (que embebe el INTENT)."""
    contexts = stores.contexts
    out: list[_SellFill] = []
    for event in stores.exec_store._rows.values():  # noqa: SLF001 — lectura de test.
        ctx = await contexts.get(event.execution_id)
        if ctx is not None and ctx.side == "sell":
            out.append(
                _SellFill(
                    execution_id=event.execution_id,
                    order_id=event.order_id,
                    qty=Decimal(str(event.qty)),
                    status=event.status,
                )
            )
    return sorted(out, key=lambda fill: fill.execution_id)


def _sell_order_ids(fills: list[_SellFill]) -> set[str]:
    return {fill.order_id for fill in fills}


def _sell_total(fills: list[_SellFill]) -> Decimal:
    return sum((fill.qty for fill in fills), Decimal("0"))


@pytest.mark.asyncio
async def test_c1_crash_before_reserving_yields_exactly_one_exit_intent(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: se decidió cerrar y el proceso murió antes de reservar. El reinicio cierra UNA vez."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # DD 16 % ⇒ RISK_OFF
    stores = _Stores()
    await _seed_buy_position(stores, execution_id="buy-c1", qty=Decimal("200"), price=Decimal("100"))

    w = _restart(stores, minute=1)
    await w.readopt_positions()
    await w._v2_reconcile_reservations(startup=True)
    w._decider = _hold()
    await w.auto_turn()

    assert w._open.get("AAA", Decimal("0")) == 0, "el reinicio debe cerrar la posición"
    open_intents = await stores.exit_orders.list_open(ACCOUNT_ID)
    assert open_intents == [], "el INTENT de salida debe quedar cerrado (FILLED)"
    all_intents = list(stores.exit_orders._rows.values())  # noqa: SLF001 — lectura de test.
    assert len(all_intents) == 1, "exactly-once del INTENT: uno, no uno por reintento"
    assert all_intents[0].exit_order_id
    assert all_intents[0].state == "FILLED"
    assert all_intents[0].filled_qty == 200.0

    fills = await _sell_fills(stores)
    assert _sell_total(fills) == Decimal("200"), "se vende la posición exacta, ni más ni menos"
    assert len(_sell_order_ids(fills)) == 1, (
        "una sola ORDEN de salida: los fills parciales del venue comparten identidad lógica"
    )
    assert await stores.reservations.list_live(ACCOUNT_ID) == []


@pytest.mark.asyncio
async def test_c2_crash_after_reserving_before_emit_releases_dead_and_exits_once(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2: reserva de salida persistida y crash antes de emitir. Se libera UNA vez y se cierra."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # DD 16 % ⇒ RISK_OFF
    stores = _Stores()
    await _seed_buy_position(stores, execution_id="buy-c2", qty=Decimal("200"), price=Decimal("100"))
    await _seed_live_sell_reservation(
        stores, reservation_id="exit:seed-c2", qty=200.0, at="2026-09-15T09:01:00Z"
    )
    await _seed_exit_intent(
        stores, exit_order_id="seed-c2", reservation_id="exit:seed-c2", qty=200.0, at="2026-09-15T09:01:00Z"
    )

    w = _restart(stores, minute=1)
    await w.readopt_positions()
    await w._v2_reconcile_reservations(startup=True)

    rows = await stores.reservations.list_all(ACCOUNT_ID)
    dead = [row for row in rows if row.reservation_id == "exit:seed-c2"]
    assert dead and dead[0].status == RESERVATION_RELEASED_BY_RESTART, (
        "la orden muerta (sin fill ni vuelo) se libera al reiniciar"
    )
    assert await stores.reservations.list_live(ACCOUNT_ID) == []
    abandoned = await stores.exit_orders.get("seed-c2")
    assert abandoned is not None and abandoned.state == "ABANDONED"
    assert abandoned.emergency is False

    w._decider = _hold()
    await w.auto_turn()
    assert w._open.get("AAA", Decimal("0")) == 0
    assert await stores.reservations.list_live(ACCOUNT_ID) == []
    fills = await _sell_fills(stores)
    assert _sell_total(fills) == Decimal("200"), "la cola liberada se cierra exactamente una vez"
    assert len(_sell_order_ids(fills)) == 1, "un solo INTENT para la cola liberada"
    intents = list(stores.exit_orders._rows.values())  # noqa: SLF001 — lectura de test.
    assert len(intents) == 2, "el INTENT muerto (ABANDONED) + el del cierre efectivo"
    assert {intent.state for intent in intents} == {"ABANDONED", "FILLED"}


@pytest.mark.asyncio
async def test_c3_crash_after_emit_before_applied_does_not_release_or_duplicate(
    v2_env: None,
) -> None:
    """C3: la orden está EN VUELO (emitida, aún sin APPLIED). No se libera ni se re-emite."""
    stores = _Stores()
    await _seed_buy_position(stores, execution_id="buy-c3", qty=Decimal("200"), price=Decimal("100"))
    await _seed_live_sell_reservation(
        stores, reservation_id="exit:seed-c3", qty=200.0, at="2026-09-15T09:01:00Z"
    )
    await _seed_exit_intent(
        stores, exit_order_id="seed-c3", reservation_id="exit:seed-c3", qty=200.0, at="2026-09-15T09:01:00Z"
    )
    await _seed_emit_before_applied(
        stores, execution_id="sell-c3-inflight", qty=Decimal("200"), price=Decimal("100")
    )

    w = _restart(stores, minute=1)
    await w.readopt_positions()
    await w._v2_reconcile_reservations(startup=True)

    live = await stores.reservations.list_live(ACCOUNT_ID)
    assert [row.reservation_id for row in live] == ["exit:seed-c3"], (
        "una orden en vuelo NO se libera: liberarla devolvería al mercado una orden viva"
    )
    intent = await stores.exit_orders.get("seed-c3")
    assert intent is not None and intent.is_open and intent.state == "RESERVED"

    before = await _sell_fills(stores)
    w._decider = _hold()
    await w.auto_turn()
    after = await _sell_fills(stores)
    assert after == before, "un reinicio no puede emitir una segunda venta de la misma cola"


@pytest.mark.asyncio
async def test_c4_crash_after_partial_fill_carries_the_intent_and_converges(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C4: fill PARCIAL aplicado. La reserva libera lo materializado y el INTENT queda PARTIAL."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # DD 16 % ⇒ RISK_OFF
    stores = _Stores()
    await _seed_buy_position(stores, execution_id="buy-c4", qty=Decimal("200"), price=Decimal("100"))
    await _seed_live_sell_reservation(
        stores, reservation_id="exit:seed-c4", qty=200.0, at="2026-09-15T09:01:00Z"
    )
    await _seed_exit_intent(
        stores, exit_order_id="seed-c4", reservation_id="exit:seed-c4", qty=200.0, at="2026-09-15T09:01:00Z"
    )
    await _seed_partial_sell_fill(
        stores, execution_id="sell-c4-partial", qty=Decimal("80"), price=Decimal("101")
    )
    # Un fill APPLIED ya movió el libro: el reinicio debe ver 120, no 200.
    await stores.positions.upsert(
        ACCOUNT_ID,
        ENGINE_ID,
        "AAA",
        Decimal("120"),
        entry_price=Decimal("100"),
        high_watermark=Decimal("100"),
        stop_price=Decimal("97"),
    )

    w = _restart(stores, minute=1)
    await w.readopt_positions()
    await w._v2_reconcile_reservations(startup=True)

    intent = await stores.exit_orders.get("seed-c4")
    assert intent is not None
    assert intent.state == "PARTIAL", "el INTENT refleja el fill parcial, no la cantidad pedida"
    assert intent.filled_qty == 80.0
    assert intent.remaining_qty == 120.0
    assert intent.is_open is True

    w._decider = _hold()
    await w.auto_turn()
    # La gestión termina de cerrar la cola viva sin volver a vender lo ya materializado.
    assert w._open.get("AAA", Decimal("0")) == 0, "la posición converge a FLAT"
    fills = await _sell_fills(stores)
    assert _sell_total(fills) == Decimal("200"), (
        "los 80 parciales no se revenden: el total vendido es la posición, no 280"
    )
    assert len(_sell_order_ids(fills)) == 2, "el INTENT parcial + el INTENT de la cola residual"
    final = await stores.exit_orders.get("seed-c4")
    assert final is not None
    assert final.state == "PARTIAL"
    assert final.filled_qty == 80.0
    assert final.remaining_qty == 120.0
    assert final.emergency is False


@pytest.mark.asyncio
async def test_a_durable_halt_survives_the_restart_and_still_blocks_entry(
    v2_env: None,
) -> None:
    """P0-1: la parada dura persistida se RESTAURA en el arranque y sigue vetando entradas."""
    stores = _Stores()
    w1 = _restart(stores, minute=0)
    w1._account_id = ACCOUNT_ID
    w1._engine_id = ENGINE_ID
    assert await w1.engage_kill_switch_durable("DATA_CORRUPTION", at="2026-09-15T09:00:00Z") is True

    w2 = _restart(stores, minute=1)
    assert w2._v2_kill_switch_halted() is False, "la RAM nueva nace limpia (no recuerda nada)"
    await w2._v2_load_kill_state()
    assert w2._v2_kill_switch_halted() is True, "el HALT durable se restaura al arrancar"
    assert w2._v2_kill_switch.reason == "DATA_CORRUPTION"
    assert w2._v2_kill_switch.engagement_id

    w2._decider = _hold()
    await w2.auto_turn()
    assert w2.open_symbols == (), "con la parada restaurada no se abre nada"


@pytest.mark.asyncio
async def test_a_durable_release_requires_a_reconciliation_id_and_is_persisted(
    v2_env: None,
) -> None:
    """P0-1: liberar exige reconciliación explícita; sin id no se levanta y queda persistido."""
    stores = _Stores()
    w = _restart(stores, minute=0)
    w._account_id = ACCOUNT_ID
    w._engine_id = ENGINE_ID
    await w.engage_kill_switch_durable("RECONCILIATION_FAILURE", at="2026-09-15T09:00:00Z")

    assert (
        await w.release_kill_switch_durable(
            reconciliation_ok=True, reconciliation_id=None
        )
        is False
    )
    assert w._v2_kill_switch_halted() is True, "sin reconciliation_id NO se levanta"

    assert (
        await w.release_kill_switch_durable(
            reconciliation_ok=True, reconciliation_id="recon-42"
        )
        is True
    )
    state = await stores.kill_state.load(ACCOUNT_ID, ENGINE_ID)
    assert state is not None
    assert state.engaged is False
    assert state.release_reconciliation_id == "recon-42"

    w2 = _restart(stores, minute=1)
    await w2._v2_load_kill_state()
    assert w2._v2_kill_switch_halted() is False, "una liberación persistida no revive la parada"


# ── P1-4 · política B: el fallo de la reserva de salida ──────────────────────────


class _ExplodingReservationStore(InMemoryReservationStore):
    """La reserva de salida no llega a ser durable (store caído)."""

    async def save(self, reservation: object) -> bool:  # type: ignore[override]
        raise RuntimeError("reservation store down")


class _ExplodingExitOrderStore(InMemoryExitOrderStore):
    """El intent de salida tampoco llega a ser durable (store caído)."""

    async def save(self, order: object) -> bool:  # type: ignore[override]
        raise RuntimeError("exit order store down")


@pytest.mark.asyncio
async def test_p1_4_reservation_failure_persists_an_emergency_intent_and_still_exits(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La salida protectora NO se bloquea por un fallo de reserva, pero deja rastro durable."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # RISK_OFF
    stores = _Stores()
    stores.reservations = _ExplodingReservationStore()  # type: ignore[assignment]
    await _seed_buy_position(stores, execution_id="buy-p14", qty=Decimal("200"), price=Decimal("100"))

    w = _restart(stores, minute=1)
    await w.readopt_positions()
    w._decider = _hold()
    await w.auto_turn()

    assert w._open.get("AAA", Decimal("0")) == 0, "reducir riesgo nunca empeora: se vende igual"
    intents = list(stores.exit_orders._rows.values())  # noqa: SLF001 — lectura de test.
    assert len(intents) == 1
    assert intents[0].emergency is True
    assert intents[0].state == "EMERGENCY"
    assert intents[0].reason == "reservation_persist_failed"
    assert await stores.kill_state.load(ACCOUNT_ID, ENGINE_ID) is None, (
        "con el intent de emergencia durable NO se para el sistema"
    )
    assert _sell_total(await _sell_fills(stores)) == Decimal("200")


@pytest.mark.asyncio
async def test_p1_4_when_neither_store_is_durable_the_system_halts_and_does_not_emit(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si el intent de emergencia TAMPOCO es durable: HALT persistido y NINGUNA orden emitida."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")  # RISK_OFF
    stores = _Stores()
    stores.reservations = _ExplodingReservationStore()  # type: ignore[assignment]
    stores.exit_orders = _ExplodingExitOrderStore()  # type: ignore[assignment]
    await _seed_buy_position(stores, execution_id="buy-p14b", qty=Decimal("200"), price=Decimal("100"))

    w = _restart(stores, minute=1)
    await w.readopt_positions()
    w._decider = _hold()
    await w.auto_turn()

    assert w._open.get("AAA", Decimal("0")) == 200, "fail-closed: no se emite la salida"
    assert await _sell_fills(stores) == [], "sin identidad durable no hay venta"
    state = await stores.kill_state.load(ACCOUNT_ID, ENGINE_ID)
    assert state is not None and state.engaged is True
    assert state.reason == "SYSTEM_ERROR"
    assert w._v2_kill_switch_halted() is True
