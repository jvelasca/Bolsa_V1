"""V2.87 · AUTO-MATERIAL-15 — costura del CICLO DURABLE de reserva→fill→liberación.

Suite HERMÉTICA (sin PostgreSQL) que certifica la costura que desbloquea el replay
multianual: el libro de compromisos se CIERRA en cada tick.

Qué fija, y por qué importa:

* El plan aprueba una entrada (y persiste su reserva) pero la ejecución downstream la veta
  (``fill_not_materialized``): la reserva queda VIVA sin orden. Es la reserva HUÉRFANA que
  en ``v2.86`` no se retiraba nunca y acababa agotando el presupuesto de riesgo
  (``risk_budget_exceeded`` ⇒ truncación tras ``2022-05-06``).
* ``close_tick`` (costura de ``v2.87``) reutiliza ``_v2_reconcile_reservations(startup=False)``
  y la retira como ``RELEASED_BY_CANCEL``; el modo CONTROL (``durable_cycle=False``) NO la
  retira, y ese goteo queda MEDIDO en vez de narrado.
* El espejo ``APPLIED`` con retención declarada mantiene la lectura del motor completa por
  debajo de su tope de 1000 filas y NO pierde los fills del tick: sin él, un replay
  multianual reintroduciría la truncación con otro nombre (``RECONCILIATION_FAILURE``).

Lo que esta suite NO afirma: que el horizonte multianual se complete. Eso lo mide la
corrida del instrumento, no un test hermético.
"""

from __future__ import annotations

import importlib.util
import pathlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

import bolsa_api.background.auto_simulation_worker as worker_module
from bolsa_analytics.cognitive.portfolio_reservation import build_reservation
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.applied_fills import DEFAULT_APPLIED_LIMIT, read_applied_fill_facts
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import ExecutionEvent, InMemoryExecutionEventStore
from bolsa_application.replay_oos import close_tick, snapshot_book
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)
from bolsa_application.simulated_broker import SimulatedOrderResult
from bolsa_application.simulated_settlement import auto_venue_order_id

_ACCOUNT = "acc-durable-cycle"
_ENGINE = "engine-durable-cycle"
#: Varios símbolos a propósito: el goteo de una reserva por instrumento es lo que se mide.
_WATCH = ("AAA", "BBB", "CCC")

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_V87_SCRIPT = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_87_replay_oos_durable_cycle.py"


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_WATCH))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


# ── dobles deterministas ─────────────────────────────────────────────────────────


class _ZeroFillSettlement:
    """Seam determinista: la orden NO materializa ni un chunk (``status=rejected``).

    Es el disparador de la reserva huérfana: el plan ya comprometió el capital, pero la
    liquidación no devuelve ningún fill, así que el bucle de ejecución veta con
    ``fill_not_materialized`` y NO libera la reserva por fill. Sin cierre de tick, su riesgo
    queda comprometido para siempre.
    """

    def __init__(self) -> None:
        self.requests: list[tuple[str, Decimal]] = []

    async def __call__(
        self, _store: Any, **kwargs: Any
    ) -> tuple[SimulatedOrderResult, dict[str, str]]:
        instrument_id = str(kwargs["instrument_id"])
        side = str(kwargs["side"])
        quantity = Decimal(str(kwargs["quantity"]))
        self.requests.append((instrument_id, quantity))
        venue_order_id = auto_venue_order_id(
            engine_id=kwargs.get("engine_id") or "engine",
            account_id=kwargs.get("account_id"),
            instrument_id=instrument_id,
            side=side,
            logical_order_id=kwargs.get("logical_order_id") or f"{kwargs.get('seed')}",
        )
        return (
            SimulatedOrderResult(
                venue_order_id=venue_order_id,
                status="rejected",
                reason="market_out",
                scheduled_gap_seconds=0.3,
                fills=(),
                queue_event="ok",
                cumulative_filled_quantity=Decimal("0"),
            ),
            {},
        )


class _MoneyApplier:
    """Applier hermético: confirma cada fill una sola vez (modo dinero, sin caja real)."""

    def __init__(self) -> None:
        self.applied: list[str] = []

    async def __call__(self, execution: ExecutionEvent) -> bool:
        self.applied.append(execution.execution_id)
        return True


def _buy() -> Any:
    def _decide(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _decide


def _edge_source(value: float = 0.9) -> Any:
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


def _worker(**kwargs: Any) -> AutoSimulationWorker:
    defaults: dict[str, Any] = {
        "engine_id": _ENGINE,
        "account_id": _ACCOUNT,
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": _edge_source(),
        "finance_applier": _MoneyApplier(),
    }
    defaults.update(kwargs)
    defaults.setdefault("exec_store", InMemoryExecutionEventStore())
    defaults.setdefault("position_store", InMemorySimAutoPositionStore())
    defaults.setdefault("reservation_store", InMemoryReservationStore())
    return AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 17, 9, 0, tzinfo=UTC))[1],
        **defaults,
    )


def _load_v87_script() -> Any:
    """Carga el orquestador del replay por ruta (no es un módulo instalable)."""
    spec = importlib.util.spec_from_file_location("v2_87_replay_oos_durable_cycle", _V87_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── la costura: reserva huérfana retirada al cierre ──────────────────────────────


@pytest.mark.asyncio
async def test_orphan_reservation_is_released_as_cancel_at_tick_close(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El plan aprueba, la ejecución veta y la reserva NACE... y muere al cerrar el tick."""
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    worker = _worker(reservation_store=store)
    worker._decider = _buy()  # noqa: SLF001 — el decider propone la entrada del tick.

    report = await worker.auto_turn()

    live = await store.list_live(_ACCOUNT)
    assert live, "el plan debe comprometer la reserva ANTES de emitir (fail-closed)"
    assert worker._v2_reservations, "el libro vivo del worker la refleja"  # noqa: SLF001
    assert report.fills == 0, "la orden no materializó ningún chunk"
    assert "fill_not_materialized" in worker._last_gate_reason, worker._last_gate_reason  # noqa: SLF001

    # Modo CONTROL: sin cierre de tick la reserva muerta sigue VIVA (el goteo de v2.86).
    assert await close_tick(worker, durable_cycle=False) is False
    assert worker._v2_reservations, "el modo CONTROL no debe retirar la reserva huérfana"  # noqa: SLF001

    # Ciclo durable: se retira como CANCELACIÓN (no por reinicio, no por fill).
    assert await close_tick(worker) is True
    assert worker._v2_reservations == ()  # noqa: SLF001
    rows = await store.list_all(_ACCOUNT)
    assert {row.status for row in rows} == {"RELEASED_BY_CANCEL"}
    assert {row.release_reason for row in rows} == {"cancel"}
    # Una cancelación total deja a 0 la cantidad viva y el riesgo comprometido: nada de la
    # reserva sobrevive al cierre (si sobreviviera, el presupuesto seguiría gastado).
    assert all(row.remaining_qty == 0.0 for row in rows)
    assert all(row.is_live is False for row in rows)
    shelf = snapshot_book("2026-09-17", reservations=rows, measurement="COMPLETE")
    assert shelf.live_reservations == 0
    assert shelf.reserved_risk == 0.0
    assert shelf.reserved_cash == 0.0


@pytest.mark.asyncio
async def test_book_does_not_drip_over_n_ticks_when_the_cycle_is_durable(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con ciclo durable el libro vuelve a 0 en CADA cierre; sin él, crece tick a tick."""
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    worker = _worker(reservation_store=store)
    worker._decider = _buy()  # noqa: SLF001
    ticks = 4

    durable_live: list[int] = []
    for _ in range(ticks):
        await worker.auto_turn()
        await close_tick(worker)
        durable_live.append(len(worker._v2_reservations))  # noqa: SLF001

    assert durable_live == [0] * ticks, f"el libro gotea: {durable_live}"
    rows = await store.list_all(_ACCOUNT)
    assert rows, "el ciclo durable retira, no evita el compromiso"
    assert {row.status for row in rows} == {"RELEASED_BY_CANCEL"}

    # CONTROL: el mismo escenario SIN cierre de tick deja reservas vivas acumulándose.
    control_store = InMemoryReservationStore()
    control = _worker(reservation_store=control_store)
    control._decider = _buy()  # noqa: SLF001
    control_live: list[int] = []
    for _ in range(ticks):
        await control.auto_turn()
        control_live.append(len(control._v2_reservations))  # noqa: SLF001

    assert control_live[-1] > 0, "el escenario de control debe reproducir el goteo"
    assert control_live[-1] > durable_live[-1], (
        f"la costura no cambia nada: durable={durable_live} control={control_live}"
    )


@pytest.mark.asyncio
async def test_close_tick_is_fail_loud_without_the_frozen_reconcile() -> None:
    """Sin la pieza de producción, el cierre NO se declara hecho: falla en vez de fingir."""

    class _NoReconcile:
        pass

    with pytest.raises(RuntimeError, match="_v2_reconcile_reservations"):
        await close_tick(_NoReconcile())


@pytest.mark.asyncio
async def test_close_tick_control_mode_does_not_touch_the_worker() -> None:
    """El modo CONTROL es inerte a propósito (y no exige que el worker sepa reconciliar)."""

    class _Boom:
        async def _v2_reconcile_reservations(self, *, startup: bool) -> None:  # pragma: no cover
            raise AssertionError("el modo CONTROL no debe reconciliar")

    assert await close_tick(_Boom(), durable_cycle=False) is False


# ── el techo de 1000 fills APPLIED ───────────────────────────────────────────────


async def _applied_event(store: Any, index: int) -> str:
    execution_id = f"exec-{index:05d}"
    await store.capture(
        ExecutionEvent(
            execution_id=execution_id,
            order_id=f"order-{index}",
            venue="paper",
            qty=Decimal("1"),
            account_id=_ACCOUNT,
        )
    )
    assert await store.start_apply(execution_id, owner="test") is True
    assert await store.mark_applied(execution_id) is True
    return execution_id


async def _save_context(contexts: Any, execution_id: str) -> None:
    await contexts.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id="AAA",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("100"),
            account_id=_ACCOUNT,
        )
    )


@pytest.mark.asyncio
async def test_applied_retention_keeps_the_engine_read_complete_beyond_its_limit() -> None:
    """>1000 fills aplicados con retención declarada ⇒ la medición del motor sigue COMPLETE."""
    module = _load_v87_script()
    retention = 900
    store = module._RetentionExecutionEventStore(retention=retention)
    contexts = InMemorySimFillFinanceContextStore()
    total = DEFAULT_APPLIED_LIMIT + 250

    for index in range(total):
        execution_id = await _applied_event(store, index)
        await _save_context(contexts, execution_id)

    # El espejo conserva la ventana declarada y ARCHIVA el resto (sin mentir sobre el libro).
    applied = await store.list_applied(_ACCOUNT, limit=DEFAULT_APPLIED_LIMIT)
    assert len(applied) == retention
    assert store.archived_applied == total - retention
    # El pico declara el hueco REAL hasta el tope del motor: el recorte es "uno entra, uno
    # sale" (se poda al aplicar), así que el espejo nunca sostuvo más de la ventana + 1.
    assert store.peak_applied == retention + 1

    read = await read_applied_fill_facts(store, contexts, _ACCOUNT, limit=DEFAULT_APPLIED_LIMIT)
    assert read.truncated is False, "la ventana debe caber en el tope de lectura del motor"
    assert read.measurement == "COMPLETE", read.error
    assert read.ledger.facts_applied == retention


@pytest.mark.asyncio
async def test_applied_retention_never_drops_the_fills_of_the_current_tick() -> None:
    """La ventana conserva siempre lo MÁS RECIENTE: el fill del tick no se archiva."""
    module = _load_v87_script()
    store = module._RetentionExecutionEventStore(retention=3)
    for index in range(8):
        await _applied_event(store, index)
    # El último fill aplicado (el del tick corriente) sigue dentro del libro.
    assert await store.get("exec-00007") is not None
    assert await store.get("exec-00000") is None
    assert store.archived_applied == 5


@pytest.mark.asyncio
async def test_applied_retention_never_drops_unapplied_capital_in_flight() -> None:
    """Lo NO aplicado (capital en vuelo) es input del guardarraíl: jamás se archiva."""
    module = _load_v87_script()
    store = module._RetentionExecutionEventStore(retention=1)
    for index in range(5):
        await _applied_event(store, index)
    await store.capture(
        ExecutionEvent(
            execution_id="exec-pending",
            order_id="order-pending",
            venue="paper",
            qty=Decimal("7"),
            account_id=_ACCOUNT,
        )
    )

    pending = await store.list_unapplied(_ACCOUNT)
    assert [row.execution_id for row in pending] == ["exec-pending"]
    assert len(await store.list_applied(_ACCOUNT, limit=DEFAULT_APPLIED_LIMIT)) == 1


# ── OBS-14: cierre de turno en el camino durable (``real_turn``) ──────────────────
#
# Antes de OBS-14 el motor retiraba reservas muertas SOLO al arranque del proceso. Estos
# tests fijan la costura nueva: ``real_turn`` cierra el ciclo del libro al FINAL de cada
# turno, sobre la MISMA sesión del tick y sin reiniciar. El modo CONTROL deja el cierre
# inerte (solo reconcilia el arranque) y reproduce el goteo pre-OBS-14.


def _buy_only(*symbols: str) -> Any:
    """Decider que solo aprueba BUY en los símbolos dados (HOLD-safe en el resto)."""

    def _decide(symbol: str) -> DecisionPackage:
        if symbol not in symbols:
            return DecisionPackage(action="HOLD", instrument_id=symbol)
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _decide


async def _real_turn(
    worker: AutoSimulationWorker,
    *,
    exec_store: Any,
    store: Any,
    contexts: Any = None,
) -> Any:
    """Un turno por el camino DURABLE (``real_turn``), con la MISMA sesión del tick."""
    return await worker.real_turn(
        exec_store=exec_store,
        auto_store=None,
        finance_applier=None,
        account_id=_ACCOUNT,
        context_store=contexts,
        reservation_store=store,
    )


def _startup_only_reconcile(worker: AutoSimulationWorker, monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL: deja el cierre de turno inerte (solo reconciliación de arranque).

    Es el comportamiento anterior a OBS-14: la reserva muerta del turno sobrevive hasta el
    siguiente reinicio, y con ella el presupuesto que consume.
    """
    original = worker._v2_reconcile_reservations  # noqa: SLF001

    async def _only_startup(*, startup: bool) -> None:
        if startup:
            await original(startup=startup)

    monkeypatch.setattr(worker, "_v2_reconcile_reservations", _only_startup)


@pytest.mark.asyncio
async def test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14: la reserva sin materializar se retira al cerrar ESE turno, sin reinicio."""
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    worker._decider = _buy()  # noqa: SLF001

    report = await _real_turn(worker, exec_store=exec_store, store=store)

    assert report.fills == 0, "la orden no materializó ningún chunk"
    assert "fill_not_materialized" in worker._last_gate_reason, worker._last_gate_reason  # noqa: SLF001
    # El MISMO turno cerró el libro: nada queda vivo (no hizo falta reiniciar).
    assert worker._v2_reservations == ()  # noqa: SLF001
    assert await store.list_live(_ACCOUNT) == []
    rows = await store.list_all(_ACCOUNT)
    assert rows, "el turno comprometió la reserva antes de emitir (fail-closed)"
    assert {row.status for row in rows} == {"RELEASED_BY_CANCEL"}
    assert {row.release_reason for row in rows} == {"cancel"}
    # El capital deja de estar comprometido: el libro pendiente vuelve a 0.
    shelf = snapshot_book("2026-09-17", reservations=rows, measurement="COMPLETE")
    assert shelf.live_reservations == 0
    assert shelf.reserved_risk == 0.0
    assert shelf.reserved_cash == 0.0


@pytest.mark.asyncio
async def test_two_real_turns_do_not_drip_the_book_between_them(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14: la reserva del primer turno no consume presupuesto en el segundo."""
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    worker._decider = _buy()  # noqa: SLF001

    await _real_turn(worker, exec_store=exec_store, store=store)
    assert worker._v2_reservations == (), "el turno 1 no deja compromiso vivo"  # noqa: SLF001
    assert await store.list_all(_ACCOUNT), "el turno 1 sí comprometió (y luego retiró)"

    await _real_turn(worker, exec_store=exec_store, store=store)
    # El turno 2 arranca con el libro a 0: sin goteo del turno 1.
    assert worker._v2_reservations == (), "el turno 2 no hereda presupuesto gastado"  # noqa: SLF001
    assert await store.list_live(_ACCOUNT) == []
    assert {row.status for row in await store.list_all(_ACCOUNT)} == {"RELEASED_BY_CANCEL"}


@pytest.mark.asyncio
async def test_control_without_tick_close_reproduces_the_drip(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL pre-OBS-14: sin cierre de turno el libro gotea (reservas vivas entre turnos)."""
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    worker._decider = _buy()  # noqa: SLF001
    _startup_only_reconcile(worker, monkeypatch)

    await _real_turn(worker, exec_store=exec_store, store=store)
    assert worker._v2_reservations, "el control NO cierra el libro al final del turno"  # noqa: SLF001

    await _real_turn(worker, exec_store=exec_store, store=store)
    assert worker._v2_reservations, "el control reproduce el goteo entre turnos"  # noqa: SLF001
    assert await store.list_live(_ACCOUNT), "el presupuesto sigue comprometido en el control"


@pytest.mark.asyncio
async def test_closing_reconcile_keeps_captured_unapplied_capital_in_flight(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14: la guarda ``in_flight`` también manda en el cierre de turno (capital en vuelo)."""
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    exec_store = InMemoryExecutionEventStore()
    # Fill CAPTURADO y NO aplicado (capital en vuelo) para AAA, con su contexto financiero.
    await exec_store.capture(
        ExecutionEvent(
            execution_id="exec-inflight",
            order_id="order-inflight",
            venue="paper",
            qty=Decimal("7"),
            account_id=_ACCOUNT,
        )
    )
    contexts = InMemorySimFillFinanceContextStore()
    await contexts.save(
        SimFillFinanceContext(
            execution_id="exec-inflight",
            instrument_id="AAA",
            side="buy",
            quantity=Decimal("7"),
            price=Decimal("100"),
            account_id=_ACCOUNT,
        )
    )
    store = InMemoryReservationStore()
    await store.save(
        build_reservation(
            reservation_id="RES-inflight-AAA",
            account_id=_ACCOUNT,
            tick_id="2026-09-17T09:00:00Z",
            instrument_id="AAA",
            side="buy",
            sector="tech",
            quantity=10,
            entry=100.0,
            reserved_risk=50.0,
            created_at="2026-09-17T09:00:00Z",
        )
    )
    worker = _worker(reservation_store=store, exec_store=exec_store, context_store=contexts)
    worker._decider = _buy_only("BBB")  # noqa: SLF001 — AAA queda intocado por el plan.

    await _real_turn(worker, exec_store=exec_store, store=store, contexts=contexts)

    rows = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert rows["RES-inflight-AAA"].is_live, "el capital capturado y no aplicado NO se libera"
    live_ids = {row.reservation_id for row in await store.list_live(_ACCOUNT)}
    assert live_ids == {"RES-inflight-AAA"}
    # El resto de reservas del turno (sin traza en vuelo) SÍ se retira por cancelación.
    released = [row for key, row in rows.items() if key != "RES-inflight-AAA"]
    assert released, "el turno debe comprometer otras reservas"
    assert {row.status for row in released} == {"RELEASED_BY_CANCEL"}
