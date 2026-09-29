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
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

import bolsa_api.background.auto_simulation_worker as worker_module
from bolsa_analytics.cognitive.portfolio_reservation import build_reservation
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    reservation_grace_window,
    step_minute_clock,
)
from bolsa_application.applied_fills import DEFAULT_APPLIED_LIMIT, read_applied_fill_facts
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import ExecutionEvent, InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
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
        async def _v2_reconcile_reservations(  # pragma: no cover
            self,
            *,
            startup: bool,
            attribute_fills: bool = True,
            only_ids: frozenset[str] | None = None,
        ) -> None:
            raise AssertionError("el modo CONTROL no debe reconciliar")

    assert await close_tick(_Boom(), durable_cycle=False) is False


@pytest.mark.asyncio
async def test_close_tick_does_not_re_attribute_fills() -> None:
    """La costura de ``v2.87`` cierra con ``attribute_fills=False`` (nunca re-reparte fills).

    Sin ese kwarg el cierre de tick del replay re-liberaría los fills que el camino caliente
    ya liberó y drenaría la cola VIVA de una orden parcialmente llenada. Los números del
    artefacto ``v2.87`` se midieron ANTES de esta guarda: la evidencia declara que exigen
    re-ejecución.
    """

    class _Recorder:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []
            # OBS-14.b — la costura pasa la PROPIEDAD de la sesión al cierre de tick.
            self._v2_owned_reservations = {"RES-propia"}

        async def _v2_reconcile_reservations(
            self,
            *,
            startup: bool,
            attribute_fills: bool = True,
            only_ids: frozenset[str] | None = None,
        ) -> None:
            self.calls.append(
                {
                    "startup": startup,
                    "attribute_fills": attribute_fills,
                    "only_ids": only_ids,
                }
            )

    recorder = _Recorder()
    assert await close_tick(recorder) is True
    assert recorder.calls == [
        {
            "startup": False,
            "attribute_fills": False,
            "only_ids": frozenset({"RES-propia"}),
        }
    ]


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

    async def _only_startup(
        *,
        startup: bool,
        attribute_fills: bool = True,
        only_ids: frozenset[str] | None = None,
    ) -> None:
        if startup:
            await original(startup=startup, attribute_fills=attribute_fills, only_ids=only_ids)

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
    # La reserva en vuelo es de ESTA sesión: así el test sigue midiendo la guarda
    # ``in_flight`` (y no el acotado por propiedad, que tiene su propio test).
    worker._v2_owned_reservations.add("RES-inflight-AAA")  # noqa: SLF001

    await _real_turn(worker, exec_store=exec_store, store=store, contexts=contexts)

    rows = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert rows["RES-inflight-AAA"].is_live, "el capital capturado y no aplicado NO se libera"
    live_ids = {row.reservation_id for row in await store.list_live(_ACCOUNT)}
    assert live_ids == {"RES-inflight-AAA"}
    # El resto de reservas del turno (sin traza en vuelo) SÍ se retira por cancelación.
    released = [row for key, row in rows.items() if key != "RES-inflight-AAA"]
    assert released, "el turno debe comprometer otras reservas"
    assert {row.status for row in released} == {"RELEASED_BY_CANCEL"}


@pytest.mark.asyncio
async def test_closing_reconcile_keeps_the_live_tail_of_a_partially_filled_order(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14 · FAIL-OPEN: el cierre de turno NO re-atribuye fills NI drena una cola EN VUELO.

    Regresión medida en el tag ``v2.88-beta`` (job ``lifecycle-pg``, crash/recovery): la
    regla 1 de la reconciliación reparte el histórico COMPLETO de fills ≥ ``created_at``
    (``consumed`` se reinicia en cada llamada), así que invocarla en cada turno re-liberaba
    lo que el camino caliente ya liberó y DRENABA el ``remaining_qty`` de una orden
    parcialmente llenada: la cola VIVA, capital comprometido de verdad. El cierre de turno
    corre con ``attribute_fills=False``.

    Re-anclado en ``OBS-18``: el discriminante que CONSERVA esa cola ya no es el agregado
    ``filled == 0`` (que conservaba también lo que nunca materializó, hasta agotar el
    presupuesto del replay multianual) sino la traza del INTENT **sin aplicar**: mientras el
    instrumento tenga capital en vuelo, la orden sigue trabajando y su cola puede
    materializar todavía. Con la guardia de ``in_flight`` activa no se toca ni un lote.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    exec_store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    store = InMemoryReservationStore()
    await store.save(
        build_reservation(
            reservation_id="RES-partial-AAA",
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
    # Fills DURABLES ya aplicados para AAA (buy): 4 unidades.
    for index in (1, 2, 3, 4):
        execution_id = await _applied_event(exec_store, index)
        await _save_context(contexts, execution_id)
    # Y la COLA de la orden sigue EN VUELO: traza capturada y NO aplicada del mismo
    # instrumento (es el contrato del fill parcial: ``fill_unapplied`` = capital en vuelo).
    pending_id = "exec-partial-tail"
    await exec_store.capture(
        ExecutionEvent(
            execution_id=pending_id,
            order_id="order-partial-tail",
            venue="paper",
            qty=Decimal("6"),
            account_id=_ACCOUNT,
        )
    )
    await _save_context(contexts, pending_id)
    worker = _worker(reservation_store=store, exec_store=exec_store, context_store=contexts)
    worker._decider = _buy_only("BBB")  # noqa: SLF001 — AAA queda intocado por el plan.
    # La reserva parcial es de ESTA sesión: así el test mide la guardia de capital en vuelo
    # (``in_flight``) y no el acotado por propiedad.
    worker._v2_owned_reservations.add("RES-partial-AAA")  # noqa: SLF001
    # Se aísla el CIERRE de turno: el bloque durable ya está readoptado por el proceso.
    worker._v2_reservations = tuple(await store.list_live(_ACCOUNT))  # noqa: SLF001
    worker._v2_reservations_reconciled = True  # noqa: SLF001

    await _real_turn(worker, exec_store=exec_store, store=store, contexts=contexts)

    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    partial = after["RES-partial-AAA"]
    assert partial.is_live, "la cola viva del fill parcial NO se retira con capital en vuelo"
    assert float(partial.remaining_qty) == 10.0, "el cierre NO re-atribuye fills ya liberados"
    assert float(partial.released_qty) == 0.0, "el fill lo libera el camino caliente, no el cierre"


@pytest.mark.asyncio
async def test_closing_reconcile_retires_a_dead_order_whose_release_was_lost(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-18 · DECLARACIÓN del cambio: con la orden MUERTA, el cierre retira la reserva.

    Es la cara opuesta del test anterior, y la que el replay multianual midió como goteo: si
    el instrumento NO tiene capital en vuelo, la orden ya no puede materializar nada. Antes
    el cierre se abstenía cuando el agregado veía fills (``filled != 0``) y dejaba la decisión
    al PRÓXIMO ARRANQUE: en un proceso que no reinicia (el replay, o un motor vivo durante
    días) esa abstención es una retención indefinida de capital que acaba agotando el
    presupuesto. El sesgo sigue siendo fail-closed — nada en vuelo + lecturas medibles — y la
    liberación no supera la cantidad viva ni cuenta el fill como propio (``released_qty`` de
    la fila queda como evidencia de lo materializado).
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    exec_store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    store = InMemoryReservationStore()
    await store.save(
        build_reservation(
            reservation_id="RES-orphan-dead",
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
    # Fills DURABLES del instrumento (de OTRAS órdenes del mismo instrumento+lado): con la
    # regla anterior bastaban para que esta reserva nunca se retirase.
    for index in (5, 6, 7, 8):
        execution_id = await _applied_event(exec_store, index)
        await _save_context(contexts, execution_id)
    worker = _worker(reservation_store=store, exec_store=exec_store, context_store=contexts)
    worker._decider = _buy_only("BBB")  # noqa: SLF001
    worker._v2_owned_reservations.add("RES-orphan-dead")  # noqa: SLF001
    worker._v2_reservations = tuple(await store.list_live(_ACCOUNT))  # noqa: SLF001
    worker._v2_reservations_reconciled = True  # noqa: SLF001

    await _real_turn(worker, exec_store=exec_store, store=store, contexts=contexts)

    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    orphan = after["RES-orphan-dead"]
    assert not orphan.is_live, "sin capital en vuelo la orden está muerta: se retira"
    assert orphan.status == "RELEASED_BY_CANCEL"
    assert orphan.release_reason == "cancel", "no materializó nada: NO es una cola muerta"
    assert float(orphan.remaining_qty) == 0.0, "no queda cantidad viva que comprometa capital"
    assert float(orphan.released_qty) <= 10.0, "la liberación nunca supera la cantidad viva"


# ── OBS-14.b · VENTANA DE GRACIA POR EDAD: el barrido deja de ser indiscriminado ──
#
# ``v2.88.2`` acotó el CIERRE de turno a las reservas PROPIAS (``only_ids``, OBS-14) y el
# barrido de ARRANQUE (``only_ids=None``: el proceso nace sin memoria y nada es suyo) quedó
# como estaba: retiraba TODA reserva viva sin fill y sin traza en vuelo. En un reinicio
# rodante, un motor que arranca ve la reserva ACTIVA de otra sesión a mitad de turno
# —indistinguible de una orden muerta— y le devuelve al mercado un capital que sí se
# materializa (el MISMO fail-OPEN de carrera de ``v2.88.1``, ahora por la puerta del
# arranque). Sin identidad de sesión en la evidencia durable, el discriminador disponible es
# la EDAD: en el motor AUTO la orden liquida DENTRO del tick, así que una reserva que superó
# un turno completo sin fill ni traza está muerta por construcción (su dueño, sea quien sea,
# ya cerró su turno); una AJENA y JOVEN puede ser una orden que la otra sesión aún no emitió.
#
# Los tests de abajo fijan las CUATRO esquinas (propia/ajena × joven/envejecida) del cierre
# y del arranque, más el sesgo de reloj (fecha futura ⇒ se conserva) y la pata de SALIDA.
# Cada fixture fecha la reserva ajena RELATIVA al reloj de la sesión (``_GRACE``), no con un
# literal: el literal de ``09:00:00Z`` que usaban estos tests caía justo en el borde de la
# ventana y pasaba por el ``>`` estricto, no por la propiedad.

#: Ventana declarada: ``V2_RESERVATION_GRACE_TURNS`` turnos de la cadencia real del loop.
_GRACE = reservation_grace_window()


def _stamp(base: datetime, offset: timedelta) -> str:
    """Instante ISO ``Z`` desplazado respecto a ``base`` (el reloj de la sesión)."""
    return (base + offset).strftime("%Y-%m-%dT%H:%M:%SZ")


def _age(now: datetime, stamp: str) -> timedelta:
    """Edad de una reserva fechada con ``_stamp``, medida contra el reloj de la sesión."""
    return now - datetime.fromisoformat(stamp.replace("Z", "+00:00"))


async def _seed_foreign(
    store: InMemoryReservationStore,
    *,
    created_at: str,
    reservation_id: str = "RES-ajena-AAA",
) -> None:
    """Reserva viva de OTRA sesión: sin fill y sin traza en vuelo ⇒ la regla 2 la ve candidata.

    La regla 2 solo la mira como "orden muerta sin llenar": la lectura medible (sin fills) y
    la ausencia de traza en vuelo están garantizadas por los stores en memoria vacíos. Lo que
    decide si se retira es la PROPIEDAD (aquí: ajena) y la EDAD (la que fije la fixture).
    """
    await store.save(
        build_reservation(
            reservation_id=reservation_id,
            account_id=_ACCOUNT,
            tick_id="2026-09-17T09:00:00Z",
            instrument_id="AAA",
            side="buy",
            sector="tech",
            quantity=10,
            entry=100.0,
            reserved_risk=50.0,
            created_at=created_at,
        )
    )


@pytest.mark.asyncio
async def test_closing_reconcile_does_not_touch_a_young_foreign_reservation(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14.b · FAIL-OPEN de CARRERA: el cierre de turno no retira reservas AJENAS y JOVENES.

    Regresión medida en el tag ``v2.88.1-beta`` (``lifecycle-pg``, ``test_concurrent_auto_pg``):
    tres sesiones concurrentes sobre la MISMA cuenta y señal, una gana el ``save_claim`` y
    reserva; la perdedora cierra su turno y ve la reserva viva de la ganadora —cuya orden
    todavía no se ha emitido ni liquidado— con las DOS lecturas medibles y SIN fill. La regla
    2 la declaraba "orden muerta sin llenar" y liberaba la cantidad COMPLETA
    (``released=200`` frente a ``materializado=147``): la ganadora materializaba su fill
    después y su liberación por fill ya no tenía fila viva, así que el capital comprometido
    volvía al mercado (fail-OPEN). La evidencia durable no puede distinguir "orden muerta" de
    "orden que otra sesión aún no ha emitido": el primer discriminador es la PROPIEDAD
    (``only_ids``) y el segundo (OBS-14.b) la EDAD — el hermano
    ``..._retires_a_foreign_reservation_once_it_aged`` certifica la retirada diferida.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    # La ajena nace DENTRO de la ventana contada desde el reloj de esta sesión: un turno
    # antes del cierre ⇒ joven al cerrar (su dueño puede estar emitiéndola ahora mismo).
    young = _stamp(worker._time, _GRACE)  # noqa: SLF001
    await _seed_foreign(store, created_at=young)
    worker._decider = _buy_only("BBB")  # noqa: SLF001 — AAA queda intocado por el plan.
    # Se aísla el CIERRE de turno (el bloque durable ya está readoptado por el proceso): el
    # barrido de arranque se prueba aparte, con los tests ``test_startup_sweep_*``.
    worker._v2_reservations = tuple(await store.list_live(_ACCOUNT))  # noqa: SLF001
    worker._v2_reservations_reconciled = True  # noqa: SLF001

    await _real_turn(worker, exec_store=exec_store, store=store)

    # Guarda de la fixture: si la cadencia cambiara, el test debe caer por la EDAD declarada
    # (mensaje explícito) y no por una comparación accidental.
    assert _age(worker._time, young) <= _GRACE, (  # noqa: SLF001
        "la ajena debe seguir DENTRO de la ventana de gracia al cerrar el turno"
    )
    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    foreign = after["RES-ajena-AAA"]
    assert foreign.is_live, "el cierre de turno NO puede retirar la reserva JOVEN de otra sesión"
    assert float(foreign.released_qty) == 0.0, "no se libera ni un lote de una identidad ajena"
    assert "RES-ajena-AAA" in {
        row.reservation_id
        for row in worker._v2_reservations  # noqa: SLF001
    }, "su capital sigue comprometido para esta sesión"
    assert "RES-ajena-AAA" not in worker._v2_owned_reservations, (  # noqa: SLF001
        "conservarla NO la adopta: la propiedad no se puede inventar"
    )
    # Y las SUYAS del turno sí se retiran (el acotado no desactiva el cierre).
    propias = [row for key, row in after.items() if key != "RES-ajena-AAA"]
    assert propias, "el turno debe comprometer reservas propias"
    assert {row.status for row in propias} == {"RELEASED_BY_CANCEL"}


@pytest.mark.asyncio
async def test_closing_reconcile_retires_a_foreign_reservation_once_it_aged(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14.b · RETIRADA DIFERIDA: la ajena que superó la ventana SÍ se retira al cerrar.

    Es la cara que evita que la retención fail-closed sea un goteo eterno: la huérfana de un
    crash que no envejeció en el barrido de arranque no espera a OTRO reinicio, se retira en
    el primer cierre de turno posterior a la ventana (a lo sumo un turno más tarde).
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    # Nace DOS ventanas antes del reloj de alta: sigue envejecida aunque el turno no avanzara
    # el reloj, así que la EDAD es el único discriminador que puede retirarla.
    aged = _stamp(worker._time, -2 * _GRACE)  # noqa: SLF001
    await _seed_foreign(store, created_at=aged)
    worker._decider = _buy_only("BBB")  # noqa: SLF001
    worker._v2_reservations = tuple(await store.list_live(_ACCOUNT))  # noqa: SLF001
    worker._v2_reservations_reconciled = True  # noqa: SLF001

    await _real_turn(worker, exec_store=exec_store, store=store)

    assert _age(worker._time, aged) > _GRACE, (  # noqa: SLF001
        "la ajena debe haber superado la ventana de gracia al cerrar el turno"
    )
    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    foreign = after["RES-ajena-AAA"]
    assert not foreign.is_live, "la ajena ENVEJECIDA se retira (su dueño ya cerró su turno)"
    assert foreign.status == "RELEASED_BY_CANCEL", "no murió por reinicio: murió al cerrar"
    assert foreign.release_reason == "cancel"
    assert "RES-ajena-AAA" not in {
        row.reservation_id
        for row in worker._v2_reservations  # noqa: SLF001
    }


@pytest.mark.asyncio
async def test_startup_sweep_retains_a_young_foreign_reservation(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14.b · ARRANQUE: el barrido ya NO es indiscriminado — la ajena JOVEN se conserva.

    Es el reinicio RODANTE: el motor que arranca no tiene memoria de la reserva ajena, la ve
    candidata y antes la retiraba entera. Retirarla devolvería al mercado el capital de una
    orden que la sesión dueña está emitiendo en ese mismo tick (fail-OPEN). Sin identidad de
    sesión, la EDAD es lo único que separa "activa" de "huérfana": dentro de la ventana se
    conserva (fail-closed) y su capital queda comprometido para esta sesión hasta que envejezca.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    # Recién creada contra el reloj de arranque: edad 0 ⇒ dentro de la ventana.
    await _seed_foreign(store, created_at=_stamp(worker._time, timedelta(0)))  # noqa: SLF001

    await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001

    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    foreign = after["RES-ajena-AAA"]
    assert foreign.is_live, "el arranque NO puede retirar una reserva DENTRO de la ventana"
    assert float(foreign.released_qty) == 0.0
    assert foreign.status == "OPEN", "no se le inventa un cierre a una identidad ajena"
    assert {row.reservation_id for row in worker._v2_reservations} == {"RES-ajena-AAA"}  # noqa: SLF001
    assert worker._v2_owned_reservations == set(), (  # noqa: SLF001
        "conservar la ajena no la convierte en propia: el arranque no reclama lo que no creó"
    )
    assert not worker._v2_kill_switch_halted(), (  # noqa: SLF001
        "conservar no es un fallo de medición: no hay HALT"
    )


@pytest.mark.asyncio
async def test_startup_sweep_retires_an_aged_foreign_reservation(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14.b · ARRANQUE: la ajena ENVEJECIDA sí se barre, y como ``RELEASED_BY_RESTART``.

    Es la huérfana de un crash: nadie la va a emitir ni a liquidar (su dueño murió, o ya
    cerró su turno hace más de un turno), así que el arranque es exactamente quien debe
    retirarla. El estado delata la CAUSA (reinicio) y no la de un cierre de turno.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    aged = _stamp(worker._time, -2 * _GRACE)  # noqa: SLF001
    await _seed_foreign(store, created_at=aged)

    await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001

    assert _age(worker._time, aged) > _GRACE  # noqa: SLF001
    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    foreign = after["RES-ajena-AAA"]
    assert not foreign.is_live, "la huérfana envejecida se barre al arrancar, sea de quien sea"
    assert foreign.status == "RELEASED_BY_RESTART"
    assert foreign.release_reason == "restart"
    assert worker._v2_reservations == ()  # noqa: SLF001


@pytest.mark.asyncio
async def test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14.b · RELOJES NO COMPARABLES: una fecha FUTURA no autoriza a retirar.

    Dos procesos cuyos relojes no son comparables no pueden ordenar "esta reserva es más
    vieja que un turno" — la aritmética da negativo y el ``>`` estricto diría "no envejeció",
    pero un ``created_at`` adelantado tampoco es evidencia de vida. El sesgo declarado es
    conservador: sin edad AFIRMABLE la reserva se conserva (fail-closed, el mismo criterio
    que una fecha ilegible). Retirar de más es fail-OPEN; conservar de más solo compromete
    presupuesto, que es la dirección segura del error.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    ahead = _stamp(worker._time, 2 * _GRACE)  # noqa: SLF001 — reloj adelantado (skew)
    await _seed_foreign(store, created_at=ahead)

    await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001

    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert after["RES-ajena-AAA"].is_live, "una fecha futura no es prueba de muerte"
    assert worker._v2_reservations, "sigue comprometida para esta sesión"  # noqa: SLF001


@pytest.mark.asyncio
async def test_grace_window_boundary_is_strict_at_exactly_one_turn(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14.b · BORDE: la edad tiene que SUPERAR la ventana; ``==`` todavía no autoriza.

    El borde no es un detalle de redondeo. En el mismo instante en que se cumple un turno el
    dueño puede estar cerrando su turno (``auto_sim_loop`` hace ``run_tick()`` y luego
    ``sleep(interval)``, así que su evidencia aún no es terminal), y retirar ahí es fail-OPEN
    por un instante; conservar ahí cuesta, a lo sumo, un turno más de capital comprometido
    (fail-closed). El contrato se fija con ``>`` y aquí se mide con DOS reservas idénticas
    separadas por UN segundo: la del borde exacto y la que acaba de superarlo.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    worker = _worker(reservation_store=store, exec_store=exec_store)
    anchor = worker._time  # noqa: SLF001 — reloj de alta de ESTA sesión
    at_edge = _stamp(anchor, -_GRACE)  # edad == ventana
    past_edge = _stamp(anchor, -_GRACE - timedelta(seconds=1))  # edad == ventana + 1 s
    await _seed_foreign(store, created_at=at_edge, reservation_id="RES-borde")
    await _seed_foreign(store, created_at=past_edge, reservation_id="RES-pasado")

    await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001

    assert _age(worker._time, at_edge) == _GRACE, "la fixture debe caer en el borde EXACTO"  # noqa: SLF001
    assert _age(worker._time, past_edge) > _GRACE  # noqa: SLF001
    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert after["RES-borde"].is_live, "edad == ventana todavía NO autoriza a retirar"
    assert not after["RES-pasado"].is_live, "un segundo más allá de la ventana sí autoriza"
    assert after["RES-pasado"].status == "RELEASED_BY_RESTART"
    assert {row.reservation_id for row in worker._v2_reservations} == {"RES-borde"}  # noqa: SLF001


@pytest.mark.asyncio
async def test_closing_reconcile_does_not_abandon_a_young_foreign_exit_intent(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-14.b · PATA DE SALIDA: conservar la ajena no debe abandonar su INTENT (V2.43.3).

    ``_v2_sync_exit_orders`` lee ``outcomes`` para decidir qué INTENT de salida queda
    ``ABANDONED``. La reserva ajena y joven NO se publica ahí (no hay entrada ⇒ ``(0.0,
    None)`` ⇒ no se toca), así que su INTENT sigue ``INTENT``/abierto: se conserva la reserva
    **sin** cerrarle la salida al dueño. Si la gracia fuera del cierre correcto pero el INTENT
    ajeno se abandonara, el fail-OPEN volvería por la puerta de la salida.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exit_store = InMemoryExitOrderStore()
    exec_store = InMemoryExecutionEventStore()

    # Sesión A: reserva de SALIDA con INTENT durable, fechada DENTRO de la ventana.
    session_a = _worker(reservation_store=store, exec_store=exec_store, exit_order_store=exit_store)
    exit_order_id = await session_a._v2_reserve_exit(  # noqa: SLF001
        symbol="AAA",
        qty=Decimal("10"),
        price=Decimal("100"),
        sector="tech",
        at=_stamp(session_a._time, _GRACE),  # noqa: SLF001 — joven al cerrar la otra sesión
    )
    assert exit_order_id, "la salida debe tener identidad durable"
    res_id = f"exit:{exit_order_id}"

    # Sesión B (sin memoria de A): su CIERRE ve la reserva viva y ajena ⇒ la conserva entera.
    session_b = _worker(reservation_store=store, exec_store=exec_store, exit_order_store=exit_store)
    await session_b._v2_reconcile_reservations(  # noqa: SLF001
        startup=False,
        attribute_fills=False,
        only_ids=frozenset(session_b._v2_owned_reservations),  # noqa: SLF001
    )

    after = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert after[res_id].is_live, "B no puede liberar la reserva de SALIDA joven de A"
    assert float(after[res_id].released_qty) == 0.0
    open_intents = {row.exit_order_id: row for row in await exit_store.list_open(_ACCOUNT)}
    assert exit_order_id in open_intents, "el INTENT de salida de A sigue abierto"
    intent = open_intents[exit_order_id]
    assert intent.state != "ABANDONED", "no se abandonó la salida ajena"
    assert intent.is_open
    assert intent.reservation_id == res_id, "el vínculo INTENT↔reserva sigue intacto"


# ── OBS-17: simetría del ownership en la pata de SALIDA (``_v2_reserve_exit``) ────
#
# La pata de ENTRADA tiene prueba de propiedad (``_v2_persist_tick_reservations``, mordida
# por ``M252``). La de SALIDA (``_v2_reserve_exit``) NO tenía ni test ni mutación: ningún
# test la ejercía (solo un docstring la mencionaba). Sin esa propiedad, el cierre de turno
# de una sesión perdedora retiraría la reserva de SALIDA viva de otra sesión — el MISMO
# fail-OPEN de carrera de ``v2.88.1``, pero por la pata que estaba sin guardar por prueba.


@pytest.mark.asyncio
async def test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-17: la reserva de SALIDA también es de ESTA sesión; otra no puede liberarla.

    Dos caras de la misma simetría: (a) la sesión B, que no la dio de alta, **no** la
    retira al cerrar su turno; (b) la sesión A, que sí la dio de alta, **sí** la retira.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    store = InMemoryReservationStore()
    exit_store = InMemoryExitOrderStore()
    exec_store = InMemoryExecutionEventStore()
    at = "2026-09-17T09:00:00Z"

    # Sesión A: reserva de SALIDA con identidad durable (INTENT persistido + reserva viva).
    session_a = _worker(reservation_store=store, exec_store=exec_store, exit_order_store=exit_store)
    exit_order_id = await session_a._v2_reserve_exit(  # noqa: SLF001
        symbol="AAA", qty=Decimal("10"), price=Decimal("100"), sector="tech", at=at
    )
    assert exit_order_id, "la salida debe tener identidad durable"
    res_id = f"exit:{exit_order_id}"
    assert res_id in session_a._v2_owned_reservations, (  # noqa: SLF001
        "la pata de SALIDA debe registrar la propiedad (simetría con la de ENTRADA)"
    )
    live = {row.reservation_id: row for row in await store.list_live(_ACCOUNT)}
    assert set(live) == {res_id}, "la reserva de salida queda viva y comprometida"
    assert live[res_id].side == "sell"

    # Sesión B (proceso distinto, sin memoria de A): su CIERRE de turno no toca la ajena.
    session_b = _worker(reservation_store=store, exec_store=exec_store, exit_order_store=exit_store)
    assert session_b._v2_owned_reservations == set()  # noqa: SLF001
    await session_b._v2_reconcile_reservations(  # noqa: SLF001
        startup=False,
        attribute_fills=False,
        only_ids=frozenset(session_b._v2_owned_reservations),  # noqa: SLF001
    )
    after_b = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert after_b[res_id].is_live, "B NO puede liberar la reserva de SALIDA de A"
    assert float(after_b[res_id].released_qty) == 0.0

    # Sesión A: su propio cierre SÍ retira su reserva de salida (misma sesión y propiedad).
    await session_a._v2_reconcile_reservations(  # noqa: SLF001
        startup=False,
        attribute_fills=False,
        only_ids=frozenset(session_a._v2_owned_reservations),  # noqa: SLF001
    )
    after_a = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert not after_a[res_id].is_live, "A SÍ puede liberar su propia reserva de salida"
    assert after_a[res_id].status == "RELEASED_BY_CANCEL"
    assert after_a[res_id].release_reason == "cancel"
    assert session_a._v2_owned_reservations == set(), (  # noqa: SLF001
        "la propiedad se poda al liberar la reserva"
    )


@pytest.mark.asyncio
async def test_reserve_exit_without_a_durable_intent_does_not_claim_ownership(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OBS-17 · CONTROL: si la reserva de salida NO es durable, no hay propiedad que reclamar.

    Con el store de reservas ausente ``_v2_reserve_exit`` devuelve ``None`` sin comprometer
    nada (fail-closed del libro): no debe quedar ninguna reserva viva ni propiedad huérfana
    que el cierre de turno pudiera usar para retirar capital de otra sesión.
    """
    monkeypatch.setattr(worker_module, "submit_simulated_order", _ZeroFillSettlement())
    exit_store = InMemoryExitOrderStore()
    session = _worker(reservation_store=None, exit_order_store=exit_store)

    exit_order_id = await session._v2_reserve_exit(  # noqa: SLF001
        symbol="AAA",
        qty=Decimal("10"),
        price=Decimal("100"),
        sector="tech",
        at="2026-09-17T09:00:00Z",
    )
    assert exit_order_id is None, "sin store de reservas la salida no se materializa"
    assert session._v2_owned_reservations == set()  # noqa: SLF001
    assert session._v2_reservations == ()  # noqa: SLF001


# ── OBS-18: la regla 2 decide por la EVIDENCIA DE LA RESERVA ─────────────────────
#
# Reproducción del goteo medido con el motor SELLADO en el replay multianual (§ artefacto
# ``replay-oos-ciclo-durable-resello``): 16 reservas vivas, riesgo comprometido ``6000``
# sobre un presupuesto de ``6000`` y la actividad congelada tras ``2022-05``. El
# discriminante que las conservaba no era ni la propiedad (``owned=16``), ni la guardia de
# ``in_flight`` (``unapplied=0``, ``inFlight=[]``), ni la medición (``COMPLETE``): era
# ``filled == 0.0`` — un AGREGADO del instrumento+lado. Si cualquier OTRA reserva del mismo
# instrumento+lado materializó, la que **nunca** materializó quedaba viva para siempre.


async def _applied_fill(
    store: Any,
    contexts: Any,
    *,
    index: int,
    instrument: str = "AAA",
    side: str = "buy",
    cycle_id: str | None = None,
) -> str:
    """Fill APLICADO del libro (evento + contexto): es la fuente de ``read_applied_fill_facts``.

    ``cycle_id`` reproduce la cadena real (V2.47): el fill hereda el ciclo del intent que lo
    emitió, que es el MISMO que la reserva que lo comprometió declara. Es la identidad exacta
    con la que OBS-20 ata un hecho aplicado a SU reserva — sin ella, "fill sin ciclo" es
    desconocido, nunca una pista para atribuirlo a una reserva concreta.
    """
    execution_id = f"exec-obs18-{index:03d}"
    await store.capture(
        ExecutionEvent(
            execution_id=execution_id,
            order_id=f"order-obs18-{index}",
            venue="paper",
            qty=Decimal("1"),
            account_id=_ACCOUNT,
        )
    )
    assert await store.start_apply(execution_id, owner="test") is True
    assert await store.mark_applied(execution_id) is True
    await contexts.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id=instrument,
            side=side,
            quantity=Decimal("1"),
            price=Decimal("100"),
            account_id=_ACCOUNT,
            cycle_id=cycle_id,
        )
    )
    return execution_id


#: OBS-20 — ciclos de las reservas hermanas de la fixture. El fill se ata al ciclo de la
#: reserva que lo originó (la más reciente), que es lo que permite distinguirlas sin
#: heurísticas de instrumento+lado: dos órdenes del mismo símbolo y lado son ciclos distintos.
_CYCLE_OLD = "cyc-obs18-vieja"
_CYCLE_NEW = "cyc-obs18-nueva"


async def _seed_sibling_reservations(
    store: InMemoryReservationStore,
    worker: AutoSimulationWorker,
    *,
    quantity: float = 10.0,
) -> tuple[str, str]:
    """Dos reservas vivas del MISMO instrumento+lado; la VIEJA nace antes que la nueva.

    Devuelve ``(vieja, nueva)``. La vieja queda sin materializar (``released_qty == 0``) y la
    nueva es la que el camino caliente acredita con el fill (``released_qty > 0``), que es
    exactamente la asimetría que el agregado mezclaba. Cada una declara su PROPIO ciclo
    (``cyc-``), como en el motor real: sin él, la evidencia del fill aplicado no se puede atar
    a una reserva concreta (OBS-20).
    """
    old_id = "RES-obs18-vieja"
    new_id = "RES-obs18-nueva"
    for reservation_id, cycle_id, offset in (
        (old_id, _CYCLE_OLD, timedelta(minutes=-5)),
        (new_id, _CYCLE_NEW, timedelta(minutes=-4)),
    ):
        await store.save(
            build_reservation(
                reservation_id=reservation_id,
                account_id=_ACCOUNT,
                tick_id="2026-09-17T09:00:00Z",
                instrument_id="AAA",
                side="buy",
                sector="tech",
                quantity=quantity,
                entry=100.0,
                reserved_cash=quantity * 100.0,
                reserved_risk=50.0,
                created_at=_stamp(worker._time, offset),  # noqa: SLF001
                cycle_id=cycle_id,
            )
        )
    return old_id, new_id


@pytest.mark.asyncio
async def test_never_materialized_reservation_is_retired_even_if_a_sibling_filled(
    v2_env: None,
) -> None:
    """OBS-18 · la reserva que NUNCA materializó se retira aunque su hermano sí materializara.

    Con la regla 2 del motor sellado, la vieja quedaba VIVA para siempre: ``filled`` (el
    agregado instrumento+lado posterior a su alta) era ``1 > 0`` por el fill de la nueva, así
    que la condición ``filled == 0.0`` no se cumplía — aunque la evidencia de la PROPIA
    reserva dijera lo contrario (``releasedQty == 0``, sin traza en vuelo, lecturas medibles).
    El resultado medido en el replay es un libro que no gotea: se AGOTA (riesgo comprometido
    ``5999.9998`` sobre ``6000``) y el motor deja de abrir.
    """
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    worker = _worker(reservation_store=store, exec_store=exec_store, context_store=contexts)
    old_id, new_id = await _seed_sibling_reservations(store, worker)
    # El fill APLICADO del instrumento+lado es posterior al alta de las DOS (el camino
    # caliente lo atribuye a la más reciente: es de SU ciclo).
    await _applied_fill(exec_store, contexts, index=1, cycle_id=_CYCLE_NEW)
    released = await store.release(
        new_id,
        status="RELEASED_BY_FILL",
        reason="fill",
        released_qty=1.0,
        at="2026-09-17T09:00:30Z",
    )
    assert released is not None and released.is_live, "la nueva sobrevive con su cola viva"

    worker._v2_owned_reservations = {old_id, new_id}  # noqa: SLF001 — ambas SON de la sesión.
    worker._v2_reservations = tuple(await store.list_live(_ACCOUNT))  # noqa: SLF001
    worker._v2_reservations_reconciled = True  # noqa: SLF001

    await worker._v2_reconcile_reservations(  # noqa: SLF001
        startup=False,
        attribute_fills=False,
        only_ids=frozenset(worker._v2_owned_reservations),  # noqa: SLF001
    )

    rows = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    vieja = rows[old_id]
    assert not vieja.is_live, (
        "la reserva que NUNCA materializó debe retirarse: su evidencia propia dice que nada "
        "la va a consumir, y el agregado del instrumento no es evidencia sobre ELLA"
    )
    assert vieja.status == "RELEASED_BY_CANCEL"
    assert vieja.release_reason == "cancel", "no materializó: se cancela, no se cierra por fill"
    assert float(vieja.remaining_qty) == 0.0
    assert worker._v2_reservations == ()  # noqa: SLF001
    shelf = snapshot_book(
        "2026-09-17",
        reservations=[row for row in await store.list_live(_ACCOUNT)],
        measurement="COMPLETE",
    )
    assert shelf.reserved_risk == 0.0, "el riesgo de la reserva muerta no sigue comprometido"


@pytest.mark.asyncio
async def test_dead_tail_of_a_partially_filled_reservation_is_cancelled(
    v2_env: None,
) -> None:
    """OBS-18 · la COLA de un fill parcial sin traza en vuelo deja de comprometer capital.

    Un fill parcial deja ``released_qty > 0`` y ``remaining_qty > 0``. Si su orden ya no está
    en vuelo (todas sus trazas aplicadas o inexistentes), ninguna orden va a consumir esa
    cola: hoy no la retira NADIE (la regla 1 solo libera lo materializado y la regla 2 exigía
    ``filled == 0``). El capital queda comprometido hasta el infinito. Se retira como
    cancelación con motivo DECLARADO (``tail_dead``), para que el libro sepa distinguir "murió
    sin llenar" de "se llenó a medias y su cola murió".
    """
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    worker = _worker(reservation_store=store, exec_store=exec_store, context_store=contexts)
    _old_id, new_id = await _seed_sibling_reservations(store, worker)
    await _applied_fill(exec_store, contexts, index=2, cycle_id=_CYCLE_NEW)
    released = await store.release(
        new_id,
        status="RELEASED_BY_FILL",
        reason="fill",
        released_qty=4.0,
        at="2026-09-17T09:00:30Z",
    )
    assert released is not None
    assert released.is_live and float(released.remaining_qty) == 6.0

    worker._v2_owned_reservations = {new_id}  # noqa: SLF001
    worker._v2_reservations = (released,)  # noqa: SLF001

    await worker._v2_reconcile_reservations(  # noqa: SLF001
        startup=False,
        attribute_fills=False,
        only_ids=frozenset({new_id}),
    )

    rows = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    nueva = rows[new_id]
    assert not nueva.is_live, "la cola sin traza en vuelo se retira: nada la va a consumir"
    assert float(nueva.remaining_qty) == 0.0
    assert float(nueva.released_qty) == 10.0, "lo materializado (4) sigue declarado en la fila"
    assert nueva.status == "RELEASED_BY_CANCEL"
    assert nueva.release_reason == "tail_dead", (
        "el motivo declara la causa: la cola de un fill parcial murió, no la orden entera"
    )
    assert worker._v2_reservations == ()  # noqa: SLF001


@pytest.mark.asyncio
async def test_a_cancel_is_never_declared_while_an_applied_fill_waits_in_the_ledger(
    v2_env: None,
) -> None:
    """OBS-20 · una retirada NO puede declarar ``cancel`` si su fill YA está en el ledger.

    Carrera medida en ``test_concurrent_auto_pg.py[5]`` (1 de cada ~9 corridas): el fill ya
    está APPLIED —por eso la guardia de ``in_flight`` no lo ve en vuelo— pero la liberación
    del camino caliente todavía no ha persistido el ``released_qty`` de la fila, y el cierre
    de turno de OTRA sesión decide con lo que dice la fila (``0``) ⇒ retira declarando
    ``cancel`` ("nunca materializó") una reserva que SÍ materializó, con el ledger en
    contradicción (Σ APPLIED del instrumento > 0). Antes de OBS-18 esa ventana era inocua
    porque la regla 2 exigía el AGREGADO de fills del instrumento+lado en ``0``.

    Qué DEBE cumplirse, sin prescribir todavía la forma del arreglo: o la reserva se CONSERVA
    (fail-closed: hay materialización sin asentar) o se retira declarando la causa real
    (``tail_dead``). Nunca ``cancel``.
    """
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    worker = _worker(reservation_store=store, exec_store=exec_store, context_store=contexts)
    _old_id, new_id = await _seed_sibling_reservations(store, worker)
    # El fill YA está aplicado (la reserva materializó) y la fila todavía no lo registra.
    await _applied_fill(exec_store, contexts, index=2, cycle_id=_CYCLE_NEW)
    before = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert before[new_id].is_live and float(before[new_id].released_qty) == 0.0, (
        "la fixture debe caer en la VENTANA: fill aplicado y fila sin registrar"
    )

    worker._v2_owned_reservations = {new_id}  # noqa: SLF001
    worker._v2_reservations = tuple(await store.list_live(_ACCOUNT))  # noqa: SLF001

    await worker._v2_reconcile_reservations(  # noqa: SLF001
        startup=False,
        attribute_fills=False,
        only_ids=frozenset({new_id}),
    )

    nueva = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}[new_id]
    if nueva.is_live:
        assert float(nueva.remaining_qty or 0) > 0, (
            "conservarla significa dejar su capital comprometido (no un cierre a medias)"
        )
    else:
        assert nueva.release_reason == "tail_dead", (
            "la fila tiene un fill aplicado en el ledger: la retirada no puede declarar "
            f"'cancel' (motivo={nueva.release_reason!r}, released={nueva.released_qty})"
        )


@pytest.mark.asyncio
async def test_a_tail_with_capital_in_flight_is_conserved(
    v2_env: None,
) -> None:
    """OBS-18 · CONTROL fail-closed: si la cola SIGUE en vuelo, no se toca ni un lote.

    Es la mitad que impide que el arreglo sea fail-OPEN: una traza NO aplicada del mismo
    instrumento (capital en vuelo) significa que la orden sigue trabajando — su cola puede
    materializar todavía. La guardia de ``in_flight`` manda sobre la evidencia de la reserva.
    """
    store = InMemoryReservationStore()
    exec_store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    worker = _worker(reservation_store=store, exec_store=exec_store, context_store=contexts)
    _old_id, new_id = await _seed_sibling_reservations(store, worker)
    await _applied_fill(exec_store, contexts, index=3, cycle_id=_CYCLE_NEW)
    released = await store.release(
        new_id,
        status="RELEASED_BY_FILL",
        reason="fill",
        released_qty=4.0,
        at="2026-09-17T09:00:30Z",
    )
    assert released is not None
    # Traza NO aplicada del mismo instrumento: la orden sigue en vuelo.
    pending_id = "exec-obs18-pending"
    await exec_store.capture(
        ExecutionEvent(
            execution_id=pending_id,
            order_id="order-obs18-pending",
            venue="paper",
            qty=Decimal("6"),
            account_id=_ACCOUNT,
        )
    )
    await contexts.save(
        SimFillFinanceContext(
            execution_id=pending_id,
            instrument_id="AAA",
            side="buy",
            quantity=Decimal("6"),
            price=Decimal("100"),
            account_id=_ACCOUNT,
        )
    )

    worker._v2_owned_reservations = {new_id}  # noqa: SLF001
    worker._v2_reservations = (released,)  # noqa: SLF001

    await worker._v2_reconcile_reservations(  # noqa: SLF001
        startup=False,
        attribute_fills=False,
        only_ids=frozenset({new_id}),
    )

    assert new_id in {row.reservation_id for row in worker._v2_reservations}  # noqa: SLF001
    rows = {row.reservation_id: row for row in await store.list_all(_ACCOUNT)}
    assert rows[new_id].is_live, "con capital en vuelo la cola sigue comprometida (fail-closed)"
    assert float(rows[new_id].remaining_qty) == 6.0
