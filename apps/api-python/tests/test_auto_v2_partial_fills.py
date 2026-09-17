"""AUTO-1A — fills PARCIALES: la posición es Σ fills APLICADOS (P0 de la auditoría).

Suite hermética (sin PG) que certifica la cadena entera del hallazgo P0 de
v2.40.4-beta:

    una orden de 200 puede llenarse 50 + 23,5 y dejar la cola en RETRY
    ⇒ la posición es 73,5 (no 200), el exit se dimensiona contra 73,5,
      la cola pendiente es CAPITAL (no posición) y un reinicio readopta 73,5.

El llenado parcial NO depende del ``mid_cut`` aleatorio del broker: se inyecta un seam
determinista de settlement que emite un schedule parcial FIJO y, para los chunks que sí
se materializan, ejecuta el camino REAL de liquidación
(``apply_simulated_order_once`` → ``execution_events`` + contexto financiero) con el
mismo applier de dinero del worker. Los chunks de cola se capturan con
``apply_finance=None`` (quedan ``RETRY``: dinero NO movido), exactamente como el broker
real los deja.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

import bolsa_api.background.auto_simulation_worker as worker_module
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.applied_fills import (
    DEFAULT_APPLIED_LIMIT,
    build_canonical_positions,
    read_applied_fill_facts,
)
from bolsa_application.auto_daily_journal import build_auto_daily_report
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import ExecutionEvent, InMemoryExecutionEventStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimFillFinanceContextStore,
)
from bolsa_application.simulated_broker import SimulatedFill, SimulatedOrderResult
from bolsa_application.simulated_settlement import (
    apply_simulated_order_once,
    auto_venue_order_id,
)

_ACCOUNT = "acc-auto-1a"
_SYMBOL = "AAA"
# Llenado parcial canónico del hallazgo: 50 + 23,5 de una orden de 200.
_APPLIED_BUY_DELTAS = (Decimal("50"), Decimal("23.5"))
_MATERIALIZED = sum(_APPLIED_BUY_DELTAS, Decimal("0"))  # 73,5
_PRICE = Decimal("100")


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", _SYMBOL)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


class PartialSettlement:
    """Seam determinista: parcial fijo de compra (y cola en ``RETRY``).

    Para la VENTA materializa lo pedido (el worker ya lo clampa a la posición
    materializada): lo que se certifica aquí es el DIMENSIONADO del exit, no el broker.
    ``sell_inflate`` permite además simular un venue que devolviera de más, para
    certificar la defensa en profundidad del invariante.
    """

    def __init__(self, *, sell_inflate: Decimal = Decimal("0")) -> None:
        self.requests: list[tuple[str, Decimal]] = []
        self.tail_execution_ids: list[str] = []
        self.sell_inflate = sell_inflate

    async def __call__(
        self, store: Any, **kwargs: Any
    ) -> tuple[SimulatedOrderResult, dict[str, str]]:
        side = str(kwargs["side"])
        quantity = Decimal(str(kwargs["quantity"]))
        instrument_id = str(kwargs["instrument_id"])
        venue = str(kwargs["venue"])
        account_id = kwargs.get("account_id")
        vid = auto_venue_order_id(
            engine_id=kwargs.get("engine_id") or "engine",
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
            logical_order_id=kwargs.get("logical_order_id") or f"{kwargs.get('seed')}",
        )
        self.requests.append((side, quantity))

        if side == "buy":
            tail = quantity - _MATERIALIZED
            assert tail > 0, f"el request de compra ({quantity}) debe superar {_MATERIALIZED}"
            deltas = [*_APPLIED_BUY_DELTAS, tail]
        else:
            deltas = [quantity + self.sell_inflate]

        fills = tuple(
            SimulatedFill(
                fill_seq=index + 1,
                qty_delta=delta,
                price=_PRICE,
                occurred_after_seconds=0.1 * (index + 1),
                venue_order_id=vid,
            )
            for index, delta in enumerate(deltas)
        )
        applied_fills = fills[:-1] if side == "buy" else fills
        tail_fills = fills[len(applied_fills) :]

        outcomes: dict[str, str] = {}
        if applied_fills:
            outcomes.update(
                await apply_simulated_order_once(
                    store,
                    result=SimulatedOrderResult(
                        venue_order_id=vid,
                        status="partial",
                        reason="market_out",
                        scheduled_gap_seconds=0.3,
                        fills=applied_fills,
                        queue_event="ok",
                        cumulative_filled_quantity=_MATERIALIZED,
                    ),
                    instrument_id=instrument_id,
                    account_id=account_id,
                    venue=venue,
                    side=side,
                    context_store=kwargs.get("context_store"),
                    apply_finance=kwargs.get("apply_finance"),
                    owner=str(kwargs.get("owner", "auto-sim")),
                    strategy_version_id=kwargs.get("strategy_version_id"),
                )
            )
        if tail_fills:
            # Sin applier: el chunk queda CAPTURED→RETRY (dinero NO movido) con su
            # contexto financiero ya persistido, igual que en el broker real.
            outcomes.update(
                await apply_simulated_order_once(
                    store,
                    result=SimulatedOrderResult(
                        venue_order_id=vid,
                        status="partial",
                        reason="market_out",
                        scheduled_gap_seconds=0.3,
                        fills=tail_fills,
                        queue_event="ok",
                        cumulative_filled_quantity=_MATERIALIZED,
                    ),
                    instrument_id=instrument_id,
                    account_id=account_id,
                    venue=venue,
                    side=side,
                    context_store=kwargs.get("context_store"),
                    apply_finance=None,
                    owner=str(kwargs.get("owner", "auto-sim")),
                    strategy_version_id=kwargs.get("strategy_version_id"),
                )
            )
            self.tail_execution_ids = [f.execution_id for f in tail_fills]

        return (
            SimulatedOrderResult(
                venue_order_id=vid,
                status="partial",
                reason="market_out",
                scheduled_gap_seconds=0.3,
                fills=fills,
                queue_event="ok",
                cumulative_filled_quantity=sum(
                    (f.qty_delta for f in applied_fills), Decimal("0")
                ),
            ),
            outcomes,
        )


class _MoneyApplier:
    """Applier hermético del modo DINERO: confirma cada fill una sola vez."""

    def __init__(self) -> None:
        self.applied: list[str] = []

    async def __call__(self, execution: ExecutionEvent) -> bool:
        self.applied.append(execution.execution_id)
        return True


def _buy() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _d


def _hold() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _ledger_reader(store: Any, contexts: Any) -> Any:
    """Lector canónico hermético: Σ fills aplicados (mismo criterio que el de PG)."""

    async def _read(account_id: str) -> Any:
        read = await read_applied_fill_facts(
            store, contexts, account_id, limit=DEFAULT_APPLIED_LIMIT
        )
        if not read.is_complete:
            return None
        return build_canonical_positions(read)

    return _read


def _edge_source(value: float = 0.9) -> Any:
    """``EdgeReportSource`` fake: edge persistido por versión (sin PG)."""
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


def _worker(**kwargs: Any) -> AutoSimulationWorker:
    defaults: dict[str, Any] = {
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": _edge_source(),
    }
    defaults.update(kwargs)
    defaults.setdefault("exec_store", InMemoryExecutionEventStore())
    return AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 17, 9, 0, tzinfo=UTC))[1],
        **defaults,
    )


def _exit_only(worker: AutoSimulationWorker) -> None:
    """Pasa el régimen a UNKNOWN (exit-only) sin tocar el resto de tunables."""
    worker._v2_tunables = replace(worker._v2_tunables, regime_override="UNKNOWN")  # noqa: SLF001


async def _entry_turn(
    monkeypatch: pytest.MonkeyPatch,
    *,
    seam: PartialSettlement,
    store: Any,
    contexts: Any,
    positions: Any,
    reader: Any,
) -> tuple[AutoSimulationWorker, _MoneyApplier, Any]:
    applier = _MoneyApplier()
    monkeypatch.setattr(worker_module, "submit_simulated_order", seam)
    worker = _worker(
        exec_store=store,
        context_store=contexts,
        position_store=positions,
        account_id=_ACCOUNT,
        finance_applier=applier,
        canonical_positions_reader=reader,
    )
    worker._decider = _buy()  # noqa: SLF001
    report = await worker.auto_turn()
    return worker, applier, report


@pytest.mark.asyncio
async def test_partial_entry_accounts_applied_qty_not_requested(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """200 pedidos / 73,5 aplicados ⇒ la posición es 73,5 (P0 de la auditoría)."""
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    positions = InMemorySimAutoPositionStore()
    seam = PartialSettlement()
    worker, applier, report = await _entry_turn(
        monkeypatch,
        seam=seam,
        store=store,
        contexts=contexts,
        positions=positions,
        reader=_ledger_reader(store, contexts),
    )

    requested = seam.requests[0][1]
    assert requested > _MATERIALIZED, "el llenado debe ser PARCIAL"
    assert worker._open[_SYMBOL] == _MATERIALIZED, (  # noqa: SLF001
        "la posición contabiliza la cantidad APLICADA, no la pedida"
    )
    assert report.orders == 1
    assert report.fills == 2, "solo los dos chunks materializados son fills"
    assert report.opened == 1
    # El journal declara la orden con la cantidad PEDIDA y los fills con la aplicada.
    kinds = [(row.kind, row.qty) for row in worker.journal_pairs()]
    assert ("order", requested) in kinds
    assert ("position_open", _MATERIALIZED) in kinds
    # El PositionState (T1/stop/trailing) se ancla a la cantidad materializada.
    assert worker._v2_positions[_SYMBOL].remaining_quantity == float(_MATERIALIZED)  # noqa: SLF001
    # El dinero se movió una sola vez por chunk aplicado.
    assert len(applier.applied) == 2


@pytest.mark.asyncio
async def test_partial_entry_ledger_and_pending_tail_stay_separate(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El libro de posición es Σ APPLIED; la cola en ``RETRY`` es CAPITAL pendiente."""
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    positions = InMemorySimAutoPositionStore()
    seam = PartialSettlement()
    worker, _applier, _report = await _entry_turn(
        monkeypatch,
        seam=seam,
        store=store,
        contexts=contexts,
        positions=positions,
        reader=_ledger_reader(store, contexts),
    )

    read = await read_applied_fill_facts(store, contexts, _ACCOUNT)
    assert read.measurement == "COMPLETE"
    assert read.quantities() == {_SYMBOL: float(_MATERIALIZED)}
    position = read.position(_SYMBOL)
    assert position is not None
    assert position.average_entry == 100.0
    assert "fill_partially_materialized" in worker._last_gate_reason  # noqa: SLF001

    tail_ids = seam.tail_execution_ids
    assert tail_ids, "el seam debe dejar cola pendiente"
    applied_ids = {fact.execution_id for fact in read.facts}
    assert all(execution_id not in applied_ids for execution_id in tail_ids)
    pending = {row.execution_id for row in await store.list_unapplied(_ACCOUNT)}
    assert pending == set(tail_ids), "la cola no aplicada sigue siendo capital en vuelo"
    journal_kinds = [row.kind for row in worker.journal_pairs()]
    assert journal_kinds.count("fill_unapplied") == len(tail_ids)
    # Y en el siguiente tick aparece como capital comprometido (no como posición).
    worker._decider = _hold()  # noqa: SLF001
    await worker.auto_turn()
    assert {order.execution_id for order in worker._v2_open_orders} == set(tail_ids)  # noqa: SLF001
    assert worker._open[_SYMBOL] == _MATERIALIZED  # noqa: SLF001


@pytest.mark.asyncio
async def test_exit_is_sized_by_materialized_position_not_requested(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El exit vende 73,5 (materializado), nunca los 200 pedidos."""
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    positions = InMemorySimAutoPositionStore()
    seam = PartialSettlement()
    worker, _applier, _report = await _entry_turn(
        monkeypatch,
        seam=seam,
        store=store,
        contexts=contexts,
        positions=positions,
        reader=_ledger_reader(store, contexts),
    )
    requested = seam.requests[0][1]

    _exit_only(worker)
    worker._decider = _hold()  # noqa: SLF001
    for _ in range(10):
        await worker.auto_turn()
        if not worker.open_symbols:
            break

    sell_requests = [qty for side, qty in seam.requests if side == "sell"]
    assert sell_requests, "el exit-only debe emitir una venta"
    assert sell_requests[0] == _MATERIALIZED, (
        f"el exit se dimensiona por la posición materializada ({_MATERIALIZED}), "
        f"no por lo pedido ({requested})"
    )
    assert worker.open_symbols == ()
    assert worker._open.get(_SYMBOL, Decimal("0")) == 0  # noqa: SLF001

    read = await read_applied_fill_facts(store, contexts, _ACCOUNT)
    assert read.quantities() == {}, "libro plano: la posición cerrada no reaparece"
    closed = read.position(_SYMBOL)
    assert closed is not None
    assert closed.realized_qty == _MATERIALIZED
    assert closed.realized_pnl == 0.0, "compra y venta al mismo precio"

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert report.exits == 1
    assert report.healthy, report.errors


@pytest.mark.asyncio
async def test_protective_exit_never_exceeds_the_applied_position(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defensa en profundidad: un fill de venta de más aplana, nunca deja posición negativa."""
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    positions = InMemorySimAutoPositionStore()
    seam = PartialSettlement(sell_inflate=Decimal("1000"))
    worker, _applier, _report = await _entry_turn(
        monkeypatch,
        seam=seam,
        store=store,
        contexts=contexts,
        positions=positions,
        reader=_ledger_reader(store, contexts),
    )

    _exit_only(worker)
    worker._decider = _hold()  # noqa: SLF001
    await worker.auto_turn()

    assert worker._open.get(_SYMBOL, Decimal("0")) == 0, "jamás una posición negativa"  # noqa: SLF001
    assert "exit_qty_over_position" in worker._last_gate_reason  # noqa: SLF001


@pytest.mark.asyncio
async def test_restart_rebuilds_inflated_projection_from_applied_ledger(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tras un crash, la proyección se reconstruye desde Σ APPLIED (no se hereda el 200)."""
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    positions = InMemorySimAutoPositionStore()
    seam = PartialSettlement()
    worker, _applier, _report = await _entry_turn(
        monkeypatch,
        seam=seam,
        store=store,
        contexts=contexts,
        positions=positions,
        reader=_ledger_reader(store, contexts),
    )
    assert worker._open[_SYMBOL] == _MATERIALIZED  # noqa: SLF001

    # Simula una proyección INFLADA (la que escribía el código anterior con la cantidad
    # pedida, o cualquier espejo corrupto) y un reinicio con la RAM vacía.
    await positions.upsert(
        _ACCOUNT, worker._engine_id, _SYMBOL, Decimal("200"), entry_price=Decimal("100")
    )
    restarted = _worker(
        exec_store=store,
        context_store=contexts,
        position_store=positions,
        account_id=_ACCOUNT,
        finance_applier=_MoneyApplier(),
        canonical_positions_reader=_ledger_reader(store, contexts),
    )
    assert getattr(restarted, "_applied_execution_events", []) == [], "RAM vacía tras el reinicio"

    await restarted.readopt_positions()

    assert restarted._reconciliation[_SYMBOL] == "REBUILT", (  # noqa: SLF001
        "la proyección divergente debe reconstruirse desde el libro aplicado"
    )
    assert restarted._open[_SYMBOL] == _MATERIALIZED, "se readopta la posición MATERIALIZADA"  # noqa: SLF001
    projection = await positions.read_open(_ACCOUNT, restarted._engine_id)
    assert Decimal(str(projection[_SYMBOL])) == _MATERIALIZED
    assert restarted._openings_vetoed(_SYMBOL) is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_unreadable_ledger_vetoes_openings_and_keeps_position(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Libro no legible: aperturas vetadas (fail-closed) y la posición NO se pierde."""

    async def _unreadable(_account_id: str) -> Any:
        return None

    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    positions = InMemorySimAutoPositionStore()
    seam = PartialSettlement()
    worker, _applier, _report = await _entry_turn(
        monkeypatch,
        seam=seam,
        store=store,
        contexts=contexts,
        positions=positions,
        reader=_ledger_reader(store, contexts),
    )
    assert worker._open[_SYMBOL] == _MATERIALIZED  # noqa: SLF001

    restarted = _worker(
        exec_store=store,
        context_store=contexts,
        position_store=positions,
        account_id=_ACCOUNT,
        finance_applier=_MoneyApplier(),
        canonical_positions_reader=_unreadable,
    )
    await restarted.readopt_positions()

    assert restarted._open[_SYMBOL] == _MATERIALIZED, (  # noqa: SLF001
        "el espejo no se pierde por no poder auditar"
    )
    assert restarted._openings_vetoed(_SYMBOL) is True, "sin libro legible no se abre"  # noqa: SLF001
