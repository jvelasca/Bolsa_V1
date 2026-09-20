"""V2.46 / AUTO-6 — Concurrent AUTO (capa HERMÉTICA, sin PG).

Certifica que **1 señal ⇒ 1 decisión ⇒ 1 orden ⇒ fills correctos** cuando varias
instancias del motor evalúan la MISMA cuenta/cartera/barra al mismo tiempo.

Qué se hace distinto para que la concurrencia sea REAL (y no un gather secuencial): las
operaciones de los espejos durables ceden el control al event loop
(``await asyncio.sleep(0)``), que es exactamente lo que hace una ida y vuelta real a
PostgreSQL. Ese ``await`` es el punto de interleaving que el camino PG serializa con
locks/``ON CONFLICT``; sin él, un store in-memory corre hasta el final sin suspender y el
``asyncio.gather`` sería una mentira (tres turnos en serie disfrazados de carrera).

El escenario usa un **fill PARCIAL** a propósito: si la reserva pudiera duplicarse, la
cola viva de cada worker se apilaría (tres reservas vivas sobre la misma señal) y el
presupuesto comprometido quedaría triplicado. Con la identidad de reserva determinista
por ``(cuenta, señal)`` (``entry_decision_id``) la reserva es un **claim atómico**: gana
un solo worker y los demás reciben ``inserted=False`` ⇒ vetan su emisión con
``reservation_already_live``.

Invariantes medidos:

* ``count(distinct venue_order_id)`` por señal/barra **≤ 1** (una sola orden);
* exactamente UN worker abre la posición; los otros dos no emiten;
* **una sola fila** de reserva por ``(cuenta, instrumento)`` (sin doble compromiso);
* ``Σ reserved_cash`` viva == la cola NO llenada (nunca la cola completa × nº workers);
* ``Σ`` cantidades ``APPLIED`` == cantidad materializada, y la cola liberada == pedido −
  materializado (contabilidad cerrada);
* una SEGUNDA oleada (otra terna de workers) no añade ni una orden más.
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
from bolsa_application.auto_reason_codes import RESERVATION_ALREADY_LIVE
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.kill_switch_store import InMemoryKillSwitchStore
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimConsumedSignalStore,
    InMemorySimFillFinanceContextStore,
)

ACCOUNT_ID = "acc-v46-conc"
ENGINE_ID = "auto-sim-v46-conc"

_PROBE_QTY = Decimal("100")
_FILL_CHUNKS = 4
_MIN_BUY_CHUNKS = 2
_ENTRY_MINUTE = 1


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v46_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


def _partial_fill_instrument_id(prefix: str) -> str:
    """Id determinista cuyo BUY en el minuto de entrada es PARCIAL (≥2 tranchas)."""
    from bolsa_application.simulated_broker import simulated_fill_schedule

    for n in range(8192):
        candidate = f"{prefix}{n:010d}"
        result = simulated_fill_schedule(
            instrument_id=candidate,
            side="buy",
            quantity=_PROBE_QTY,
            venue_order_id=f"probe-{candidate}-{_ENTRY_MINUTE}",
            seed=_ENTRY_MINUTE * 100_003 + sum(map(ord, candidate)) % 9999,
            fill_chunks=_FILL_CHUNKS,
            base_mid=100.0,
        )
        if result.status == "partial" and len(result.fills) >= _MIN_BUY_CHUNKS:
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} tiene BUY parcial en el minuto "
        f"{_ENTRY_MINUTE}; revisar ``draw_queue_noise``"
    )


class _YieldingStore:
    """Delegación que cede el control al loop antes de cada operación.

    Es el `await` de una ida y vuelta real a PostgreSQL: el punto donde dos workers
    concurrentes pueden intercalarse. Sin él, el store in-memory no suspende y la
    «carrera» sería en realidad una ejecución en serie.
    """

    def __init__(self, inner: object) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        attribute = getattr(self._inner, name)
        if not callable(attribute):
            return attribute

        async def _delegated(*args: object, **kwargs: object) -> object:
            import asyncio

            await asyncio.sleep(0)
            return await attribute(*args, **kwargs)

        return _delegated


class _Stores:
    """Espejos durables COMPARTIDOS por A/B/C (misma cuenta/cartera/señales)."""

    def __init__(self) -> None:
        self.exec_store = _YieldingStore(InMemoryExecutionEventStore())
        self.contexts = _YieldingStore(InMemorySimFillFinanceContextStore())
        self.reservations = _YieldingStore(InMemoryReservationStore())
        self.positions = _YieldingStore(InMemorySimAutoPositionStore())
        self.exit_orders = _YieldingStore(InMemoryExitOrderStore())
        self.kill_state = _YieldingStore(InMemoryKillSwitchStore())
        self.consumed = _YieldingStore(InMemorySimConsumedSignalStore())
        self.marks = EquityMarkBook()


async def _apply_true(_event: object) -> bool:
    return True


def _canonical_reader(stores: _Stores) -> object:
    async def _read(account_id: str) -> object:
        from bolsa_application.applied_fills import (
            build_canonical_positions,
            read_applied_fill_facts,
        )

        read = await read_applied_fill_facts(stores.exec_store, stores.contexts, account_id)
        if not read.is_complete:
            return None
        return build_canonical_positions(read)

    return _read


def _worker(stores: _Stores, *, decider: _Prov) -> AutoSimulationWorker:
    """Worker A/B/C: mismo reloj, misma cuenta/engine, mismos stores durables."""
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _edge(_ref: str, _account: str | None) -> float | None:
        return 0.9

    _start, clock = step_minute_clock(datetime(2026, 9, 18, 9, 0, tzinfo=UTC))
    return AutoSimulationWorker(
        clock=clock,
        exec_store=stores.exec_store,
        context_store=stores.contexts,
        reservation_store=stores.reservations,
        position_store=stores.positions,
        exit_order_store=stores.exit_orders,
        kill_switch_store=stores.kill_state,
        consumed_signal_store=stores.consumed,
        account_id=ACCOUNT_ID,
        engine_id=ENGINE_ID,
        equity_marks=stores.marks,
        finance_applier=_apply_true,
        canonical_positions_reader=_canonical_reader(stores),
        price_script=lambda _symbol, _minute: 100.0,
        decider=decider,
        sector_source=lambda _symbol: "tech",
        liquidity_source=lambda _symbol: 1_000_000.0,
        atr_source=lambda _symbol: 2.0,
        edge_source=EdgeReportSource(reader=_edge),
    )


def _buy_once(symbol: str, quantity: float = 250.0) -> _Prov:
    def _d(_symbol: str) -> DecisionPackage:
        if _symbol == symbol:
            return DecisionPackage(
                action="BUY",
                instrument_id=symbol,
                quantity=quantity,
                source="active-strategy:conc-1",
            )
        return DecisionPackage(action="HOLD", instrument_id=_symbol, quantity=0)

    return _d


async def _run_wave(stores: _Stores, symbol: str, count: int = 3) -> list[AutoSimulationWorker]:
    import asyncio

    workers = [_worker(stores, decider=_buy_once(symbol)) for _ in range(count)]
    await asyncio.gather(*(worker.auto_turn() for worker in workers))
    return workers


# ── Lecturas del libro durable ────────────────────────────────────────────────────────


async def _buy_orders(stores: _Stores, symbol: str) -> dict[str, Decimal]:
    """``venue_order_id -> Σ qty`` de las trazas BUY materializadas del símbolo."""
    orders: dict[str, Decimal] = {}
    rows = stores.exec_store._inner._rows  # noqa: SLF001 — lectura de test.
    for event in rows.values():
        context = await stores.contexts.get(event.execution_id)
        if context is None or context.instrument_id != symbol:
            continue
        if str(context.side).lower() != "buy":
            continue
        orders[event.venue_order_id] = orders.get(event.venue_order_id, Decimal("0")) + Decimal(
            str(event.qty)
        )
    return orders


@pytest.mark.asyncio
async def test_concurrent_auto_three_workers_claim_one_signal_one_order(
    v46_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tres workers concurrentes: una sola orden, una sola reserva, sin sobre-riesgo."""
    symbol = _partial_fill_instrument_id("inst-v46conc-")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    stores = _Stores()

    workers = await _run_wave(stores, symbol)

    # (1) 1 señal ⇒ 1 orden: una sola identidad de orden, aunque tres lo intentaron.
    buys = await _buy_orders(stores, symbol)
    assert len(buys) == 1, f"la señal produjo {len(buys)} órdenes distintas: {list(buys)}"

    # (2) Exactamente UN worker abre; los otros dos NO emiten (claim perdido).
    opened = [w for w in workers if w._open.get(symbol, Decimal("0")) > 0]
    assert len(opened) == 1, (
        f"exactamente un worker debe abrir; abrieron {len(opened)}: "
        f"{[str(w._open.get(symbol)) for w in workers]}"
    )
    held = opened[0]._open[symbol]
    assert held > 0

    # (3) Una sola fila de reserva (sin doble compromiso) y su cola viva == lo no llenado.
    rows = await stores.reservations.list_all(ACCOUNT_ID, limit=1000)
    assert len(rows) == 1, (
        f"la reserva debe ser única por (cuenta, instrumento): hay {len(rows)} filas"
    )
    reservation = rows[0]
    requested = Decimal(str(reservation.quantity))
    assert held < requested, "el escenario exige fill PARCIAL"
    # Contabilidad cerrada: pedido = materializado + cola liberada.
    assert Decimal(str(reservation.released_qty)) == held, (
        "lo liberado por fill debe ser exactamente lo materializado"
    )
    assert Decimal(str(reservation.remaining_qty)) == requested - held

    # (4) Σ reserved_cash viva ≤ cola realmente comprometida (nunca × nº de workers).
    live = await stores.reservations.list_live(ACCOUNT_ID, limit=1000)
    assert len(live) <= 1
    committed = sum(float(row.reserved_cash or 0) for row in live)
    # La cola viva compromete, como máximo, su propio notional sin llenar.
    assert committed <= float(requested - held) * 100.0 + 1e-6, (
        f"sobre-riesgo: comprometido {committed} > cola {float(requested - held) * 100.0}"
    )

    # (5) Los perdedores declaran POR QUÉ no emitieron (no un veto silencioso).
    losers = [w for w in workers if w._open.get(symbol, Decimal("0")) <= 0]
    assert len(losers) == 2
    for loser in losers:
        assert RESERVATION_ALREADY_LIVE in loser._last_gate_reason, loser._last_gate_reason


@pytest.mark.asyncio
async def test_concurrent_auto_second_wave_adds_nothing(
    v46_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una segunda oleada de workers no añade ni una orden ni una reserva."""
    symbol = _partial_fill_instrument_id("inst-v46wave-")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    stores = _Stores()

    await _run_wave(stores, symbol)
    first_buys = await _buy_orders(stores, symbol)
    first_rows = await stores.reservations.list_all(ACCOUNT_ID, limit=1000)
    assert len(first_buys) == 1 and len(first_rows) == 1

    # Otra terna, MISMOS stores/cuenta/barra: la señal ya está consumida y la reserva
    # sigue viva ⇒ ni una orden ni una reserva nuevas.
    second = await _run_wave(stores, symbol)
    assert await _buy_orders(stores, symbol) == first_buys, (
        "la segunda oleada no puede añadir órdenes (señal consumida + claim vivo)"
    )
    assert len(await stores.reservations.list_all(ACCOUNT_ID, limit=1000)) == 1
    assert all(w._open.get(symbol, Decimal("0")) <= 0 for w in second), (
        "ningún worker de la segunda oleada debe abrir una posición nueva"
    )
