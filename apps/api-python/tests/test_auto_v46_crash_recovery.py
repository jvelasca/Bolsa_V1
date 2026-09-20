"""V2.46 / AUTO-6 — Crash/Recovery Day (capa HERMÉTICA, sin PG).

Certifica la mitad hermética del escenario ``Crash/Recovery`` del roadmap §8: el día
AUTO sobrevive a la MUERTE del proceso a mitad de un fill PARCIAL sin duplicar ni
perder dinero.

La RAM se pierde de verdad: al "proceso muerto" se le abandona el objeto
``AutoSimulationWorker`` y el reinicio construye un worker NUEVO sobre los MISMOS
espejos durables (``_Stores``), que es exactamente el contrato del camino real
(``test_auto_v44_exit_crash_matrix.py``). La secuencia:

    BUY (fill PARCIAL: la cola SIM corta la orden en 2 tranchas)
      → MUERTE (se descarta el worker: nada de reinicio "limpio" del objeto)
      → REINICIO (worker nuevo, RAM vacía)
      → RECONCILIACIÓN (readopt + reconciliación de arranque: converge OK/REBUILT)
      → CONTINUAR (el gobernador en RISK_OFF pide la salida porque el equity cae)
      → SALIDA LIMPIA (libro plano, reservas vivas a 0)

Invariantes que mide (y que el escenario real del tag re-mide con PG + proceso):

* reconciliación CONVERGENTE: ningún símbolo ``DIVERGENT``/``UNKNOWN`` al reiniciar;
* TODO ``ExecutionEvent`` en ``APPLIED`` (ningún fill sin materializar);
* CADA fill con su contexto financiero durable y su traza ``APPLIED`` (la "transacción"
  del camino hermético);
* ``POSITION == Σ APPLIED BUY − Σ APPLIED SELL``;
* SIN doble efecto: reiniciar y continuar no añade ni una traza BUY más;
* libro plano y reservas vivas a 0 al cerrar.

Determinismo (lección de AUTO-5): la cola SIM deriva su ruido de
``sha256(seed, instrument_id, side, ...)``, así que el id del instrumento se elige con
una barrida PURA que exige, en toda la ventana de minutos: BUY **parcial** con ≥2
tranchas y SELL **completa**. Si ningún candidato cumpliera, el test falla con
diagnóstico propio en vez de dejar un rojo espurio al azar. El reparto de tranchas
depende SOLO del contexto de mercado (seed/side/instrument), nunca de la cantidad ni de
la identidad del order (V2.24/A9.1), por eso la barrida es válida para la cantidad real
que el sizing del pipeline decida.
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
from bolsa_application.kill_switch_store import InMemoryKillSwitchStore
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimConsumedSignalStore,
    InMemorySimFillFinanceContextStore,
)
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    POSITION_PROJECTION_UNKNOWN,
)

ACCOUNT_ID = "acc-v46-crash"
ENGINE_ID = "auto-sim-v46-crash"

#: Cantidad de la barrida: el reparto de tranchas NO depende de ella (solo del contexto
#: de mercado), así que sirve para elegir el id con independencia del sizing real.
_PROBE_QTY = Decimal("100")
_FILL_CHUNKS = 4
_MIN_BUY_CHUNKS = 2
#: Ventanas de minutos probadas. El primer ``auto_turn`` de cada proceso avanza el reloj
#: a minuto 1 (``_advance``), y la apertura/el cierre ocurren en los primeros turnos; se
#: exige la propiedad en los minutos 1 y 2 de la BUY y en 1..3 de la SELL para que el
#: reparto no dependa de cuántos turnos tarde el pipeline en aprobar o en cerrar.
_BUY_WINDOW = (1, 2)
_SELL_WINDOW = (1, 2, 3)

#: Equity declarada del primer proceso (día normal: la entrada se aprueba).
_EQUITY_OPEN = "100000"
#: Equity del segundo proceso: DD 16 % ⇒ ``RISK_OFF`` ⇒ ``RISK_EXIT`` (salida limpia).
_EQUITY_RISK_OFF = "84000"


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v46_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # El instrumento vigilado lo fija cada test (depende de la barrida determinista).
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", _EQUITY_OPEN)
    # El gobernador permite pedir la salida por ``RISK_OFF`` (11 puntos de DD ⇒ exit).
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")


def _partial_fill_instrument_id(prefix: str) -> str:
    """Id determinista cuyo BUY es PARCIAL (≥2 tranchas) y cuyo SELL llena COMPLETO.

    Barrida pura (sin BD, sin proceso): mismo id en cada ejecución. Exige las dos
    propiedades en TODA la ventana de minutos relevante, de modo que el reparto sea fijo
    con independencia del minuto exacto en que el test abra y cierre.
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    def _probe(side: str, minute: int, candidate: str, quantity: Decimal) -> object:
        return simulated_fill_schedule(
            instrument_id=candidate,
            side=side,
            quantity=quantity,
            venue_order_id=f"probe-{side}-{candidate}-{minute}",
            seed=minute * 100_003 + sum(map(ord, candidate)) % 9999,
            fill_chunks=_FILL_CHUNKS,
            base_mid=100.0,
        )

    for n in range(8192):
        candidate = f"{prefix}{n:010d}"
        buys = [_probe("buy", minute, candidate, _PROBE_QTY) for minute in _BUY_WINDOW]
        buy_partial = all(r.status == "partial" and len(r.fills) >= _MIN_BUY_CHUNKS for r in buys)
        if not buy_partial:
            continue
        sells = [_probe("sell", minute, candidate, _PROBE_QTY) for minute in _SELL_WINDOW]
        if all(r.status == "filled" for r in sells):
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} tiene BUY parcial (≥{_MIN_BUY_CHUNKS} "
        f"tranchas) y SELL completa en las ventanas del Crash/Recovery; revisar "
        "``draw_queue_noise``"
    )


class _Stores:
    """Los espejos durables que sobreviven a la muerte del proceso (la RAM no)."""

    def __init__(self) -> None:
        self.exec_store = InMemoryExecutionEventStore()
        self.contexts = InMemorySimFillFinanceContextStore()
        self.reservations = InMemoryReservationStore()
        self.positions = InMemorySimAutoPositionStore()
        self.exit_orders = InMemoryExitOrderStore()
        self.kill_state = InMemoryKillSwitchStore()
        self.consumed = InMemorySimConsumedSignalStore()
        self.marks = EquityMarkBook()


async def _apply_true(_event: object) -> bool:
    """Applier de dinero del camino hermético: cada chunk confirmado materializa."""
    return True


def _canonical_reader(stores: _Stores) -> object:
    """Lector canónico = Σ FILLS APLICADOS (mismo read-model que producción).

    Sin él la reconciliación tras el crash sería ``UNKNOWN`` (no hay canónico contra el
    que contrastar), que es fail-closed pero no el escenario que se certifica: aquí el
    canónico se deriva del libro durable de fills aplicados, exactamente como
    ``_compose_canonical_reader`` en producción.
    """

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


def _worker(stores: _Stores, *, minute: int, decider: _Prov) -> AutoSimulationWorker:
    """Worker del día sobre los espejos COMPARTIDOS (un proceso = un worker)."""
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _edge(_ref: str, _account: str | None) -> float | None:
        return 0.9

    _start, clock = step_minute_clock(datetime(2026, 9, 18, 9, minute, tzinfo=UTC))
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
    """Spine determinista: BUY mientras el símbolo esté plano; HOLD si ya hay posición."""

    def _d(_symbol: str) -> DecisionPackage:
        if _symbol == symbol:
            return DecisionPackage(
                action="BUY",
                instrument_id=symbol,
                quantity=quantity,
                source="active-strategy:crash-1",
            )
        return DecisionPackage(action="HOLD", instrument_id=_symbol, quantity=0)

    return _d


def _hold() -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


# ── Lecturas del estado durable (la "verdad" que sobrevive al proceso) ────────────────


def _applied_events(stores: _Stores) -> list[object]:
    return [row for row in stores.exec_store._rows.values() if row.status == "APPLIED"]  # noqa: SLF001 — lectura de test.


def _non_applied_events(stores: _Stores) -> list[object]:
    return [row for row in stores.exec_store._rows.values() if row.status != "APPLIED"]  # noqa: SLF001 — lectura de test.


async def _position_from_applied(stores: _Stores, symbol: str) -> Decimal:
    """``Σ APPLIED BUY − Σ APPLIED SELL`` para el símbolo (la autoridad financiera)."""
    net = Decimal("0")
    for event in _applied_events(stores):
        context = await stores.contexts.get(event.execution_id)
        if context is None or context.instrument_id != symbol:
            continue
        qty = Decimal(str(event.qty))
        if str(context.side).lower() == "buy":
            net += qty
        elif str(context.side).lower() == "sell":
            net -= qty
    return net


@pytest.mark.asyncio
async def test_crash_recovery_day_partial_fill_survives_kill_and_restart(
    v46_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUY parcial → MUERTE → REINICIO → reconciliación → salida limpia (sin doble efecto)."""
    symbol = _partial_fill_instrument_id("inst-v46crash-")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    stores = _Stores()

    # ── FASE 1 · apertura con fill PARCIAL (la cola SIM corta la orden) ────────────
    w1 = _worker(stores, minute=0, decider=_buy_once(symbol))
    for _ in range(6):
        await w1.auto_turn()
        if w1._open.get(symbol, Decimal("0")) > 0:
            break

    held = w1._open.get(symbol, Decimal("0"))
    assert held > 0, "el día debe abrir la posición (fill parcial materializado)"
    from_applied_open = await _position_from_applied(stores, symbol)
    assert held == from_applied_open, (
        "la posición del worker debe ser EXACTAMENTE Σ APPLIED BUY (fill parcial), "
        f"worker={held} libro={from_applied_open}"
    )
    buys_open = [e for e in _applied_events(stores)]
    assert len(buys_open) >= _MIN_BUY_CHUNKS, (
        f"el escenario exige ≥{_MIN_BUY_CHUNKS} tranchas BUY (fill parcial): {len(buys_open)}"
    )
    assert w1._v2_positions.get(symbol) is not None, "la apertura V2 crea el PositionState"
    live = await stores.reservations.list_live(ACCOUNT_ID, limit=1000)
    assert live and live[0].instrument_id == symbol, (
        "la cola NO materializada de la reserva sigue comprometida tras el fill parcial"
    )
    requested = Decimal(str(live[0].quantity))
    assert held < requested, (
        f"el fill debe ser PARCIAL (no completo): materializado {held} de {requested}"
    )
    applied_after_open = len(_applied_events(stores))

    # ── MUERTE: la RAM se pierde (se abandona el worker) ──────────────────────────
    w1 = None  # noqa: F841 — el proceso muere; nada de reiniciar el objeto.

    # ── REINICIO: worker NUEVO sobre la MISMA BD, con el equity en RISK_OFF ────────
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", _EQUITY_RISK_OFF)
    w2 = _worker(stores, minute=0, decider=_hold())
    readopted = await w2.readopt_positions()
    await w2._v2_reconcile_reservations(startup=True)

    # (1) Reconciliación CONVERGENTE: ni DIVERGENT ni UNKNOWN.
    statuses = dict(w2.reconciliation_status)
    assert statuses, "el reinicio debe reconciliar el símbolo vivo"
    assert POSITION_PROJECTION_DIVERGENT not in statuses.values(), statuses
    assert POSITION_PROJECTION_UNKNOWN not in statuses.values(), statuses
    assert w2.reconciliation_blocks_openings is False, statuses

    # (2) La posición readoptada es la MATERIALIZADA (no la pedida).
    assert readopted.get(symbol, Decimal("0")) == held, (
        f"readopción debe recuperar la cantidad materializada: {readopted} vs {held}"
    )
    assert w2._open.get(symbol, Decimal("0")) == held

    # (3) Sin doble BUY: la RAM nueva no re-emite la entrada (señal consumida).
    buys_after_restart = len(_applied_events(stores))
    assert buys_after_restart == applied_after_open, (
        "reiniciar no puede añadir trazas APPLIED (doble efecto financiero)"
    )

    # ── CONTINUAR + SALIDA LIMPIA (el gobernador pide RISK_EXIT) ────────────────────
    for _ in range(6):
        await w2.auto_turn()
        if w2._open.get(symbol, Decimal("0")) <= 0:
            break

    assert w2._open.get(symbol, Decimal("0")) <= 0, "el día debe cerrar la posición"

    # ── Invariantes finales del día ────────────────────────────────────────────────
    # Todo fill materializado: nada queda CAPTURED/RETRY (dinero a medias).
    stuck = sorted({str(e.status) for e in _non_applied_events(stores)})
    assert not stuck, f"ExecutionEvents sin materializar tras el día: {stuck}"

    # Cada fill con su "transacción" (contexto financiero durable + traza APPLIED).
    events = _applied_events(stores)
    assert events, "el día debe dejar fills aplicados"
    for event in events:
        context = await stores.contexts.get(event.execution_id)
        assert context is not None, (
            f"fill APPLIED sin contexto financiero durable: {event.execution_id}"
        )

    # POSITION == Σ APPLIED BUY − Σ APPLIED SELL y libro plano.
    final_net = await _position_from_applied(stores, symbol)
    assert final_net == 0, f"el libro debe quedar plano: POSITION={final_net}"

    sides = {str(c.side).lower() for c in stores.contexts._rows.values()}  # noqa: SLF001
    assert {"buy", "sell"} <= sides, f"el día debe ver las dos patas: {sorted(sides)}"

    # Sides coherentes: la VENTA no excede la COMPRA (jamás se inventa un corto).
    bought = Decimal("0")
    sold = Decimal("0")
    for event in events:
        context = await stores.contexts.get(event.execution_id)
        assert context is not None
        qty = Decimal(str(event.qty))
        if str(context.side).lower() == "buy":
            bought += qty
        elif str(context.side).lower() == "sell":
            sold += qty
    assert sold == bought, f"vendido {sold} != comprado {bought} (libro no plano)"

    # ── FASE 4 · la MISMA barra no vuelve a abrir (dedupe durable de la señal) ────────
    # Con el día plano el gobernador se apaga y el equity vuelve al nivel normal: si algo
    # volviera a abrir, la culpa NO sería del gobernador ni del drawdown — sería que el
    # dedupe de la señal consumida no aguantó el reinicio. La ÚNICA protección posible
    # aquí es la marca durable (``sim_consumed_signals``) releída por el proceso nuevo.
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "0")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", _EQUITY_OPEN)
    applied_before_reentry = len(_applied_events(stores))
    reservations_before = len(await stores.reservations.list_all(ACCOUNT_ID, limit=1000))
    w3 = _worker(stores, minute=0, decider=_buy_once(symbol))
    for _ in range(6):
        await w3.auto_turn()
    assert w3._open.get(symbol, Decimal("0")) <= 0, (
        "la MISMA barra no puede re-abrir la oportunidad ya tomada (señal consumida): "
        f"abrió {w3._open.get(symbol)}"
    )
    assert len(_applied_events(stores)) == applied_before_reentry, (
        "re-planificar la misma barra no puede añadir trazas APPLIED (doble efecto)"
    )
    assert (
        len(await stores.reservations.list_all(ACCOUNT_ID, limit=1000)) == reservations_before
    ), "la misma barra no puede crear una reserva nueva"


@pytest.mark.asyncio
async def test_crash_recovery_releases_the_unfilled_tail_of_the_partial_reservation(
    v46_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La cola NO llenada de la reserva parcial se libera al reiniciar (no queda viva)."""
    symbol = _partial_fill_instrument_id("inst-v46tail-")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    stores = _Stores()

    w1 = _worker(stores, minute=0, decider=_buy_once(symbol))
    for _ in range(6):
        await w1.auto_turn()
        if w1._open.get(symbol, Decimal("0")) > 0:
            break
    held = w1._open.get(symbol, Decimal("0"))
    assert held > 0
    live_before = await stores.reservations.list_live(ACCOUNT_ID, limit=1000)
    assert live_before and live_before[0].remaining_qty > 0, (
        "el fill parcial deja una cola de reserva viva (capital comprometido)"
    )

    w2 = _worker(stores, minute=0, decider=_hold())
    await w2.readopt_positions()
    await w2._v2_reconcile_reservations(startup=True)

    # Consolidado el fill parcial, la cola que nunca llenó deja de consumir presupuesto.
    live_after = await stores.reservations.list_live(ACCOUNT_ID, limit=1000)
    assert live_after == [], (
        "tras reconciliar, la reserva parcial no debe quedar viva sin orden en vuelo"
    )
    assert w2._v2_reservations_measurement == "COMPLETE"
    # La posición materializada NO se toca: la liberación es contable, no financiera.
    assert w2._open.get(symbol, Decimal("0")) == held
    final_net = await _position_from_applied(stores, symbol)
    assert final_net == held, "la reconciliación no puede alterar Σ APPLIED"
