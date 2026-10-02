"""AUTO v2.88.25 — la FUENTE de precio por fill y los hechos durables de ENTRADA/LIQUIDACIÓN.

Suite hermética (sin PG) que certifica, de punta a punta y sin cambiar ninguna decisión:

1. ``submit_simulated_order`` propaga la ``price_source`` al contexto financiero durable del
   fill (migración 047): la fuente deja de ser una propiedad de la CONFIGURACIÓN.
2. El worker la sella por sí solo (``SYNTHETIC`` con el script hermético, ``SCRIPT`` con un
   script inyectado, ``kind`` de una ``PriceSource`` si la hay) y la hace viajar al fill.
3. Con el sumidero de auditoría se emiten ``auto_entry_order`` (entrada con fill aplicado) y
   ``auto_cycle_settlement`` (al cerrar el ciclo); **sin** sumidero no se emite nada y el
   motor produce exactamente lo mismo (Δ = 0).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.auto_simulation_worker as worker_module
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    flat_price_script,
    step_minute_clock,
)
from bolsa_application.applied_fills import (
    DEFAULT_APPLIED_LIMIT,
    build_canonical_positions,
    read_applied_fill_facts,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import ExecutionEvent, InMemoryExecutionEventStore
from bolsa_application.price_source_kind import (
    PRICE_SOURCE_MARKET_CLOSE,
    PRICE_SOURCE_SCRIPT,
    PRICE_SOURCE_SYNTHETIC,
)
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimFillFinanceContextStore,
)
from bolsa_application.simulated_broker import SimulatedFill, SimulatedOrderResult
from bolsa_application.simulated_settlement import (
    apply_simulated_order_once,
    auto_venue_order_id,
    submit_simulated_order,
)

_ACCOUNT = "acc-v88"
_SYMBOL = "AAA"
_PRICE = Decimal("100")


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", _SYMBOL)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


class _Collector:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def __call__(self, entry: Any) -> None:
        self.entries.append(entry)


class _MoneyApplier:
    def __init__(self) -> None:
        self.applied: list[str] = []

    async def __call__(self, execution: ExecutionEvent) -> bool:
        self.applied.append(execution.execution_id)
        return True


class _OrderedContexts(InMemorySimFillFinanceContextStore):
    """El doble hermético ordena por ``execution_id``; aquí importa el orden de INSERCIÓN.

    El store PG ordena por ``created_at`` (orden real de ejecución), del que el
    ``cycles_from_fills`` del settlement depende para emparejar la compra antes que la venta.
    El doble no conoce ``created_at``; se preserva el orden de inserción (que en este test es el
    orden temporal) para no invertir el FIFO.
    """

    async def list_by_cycle_ids(
        self, account_id: str | None, cycle_ids: Any, *, limit: int = 500
    ) -> list[Any]:
        wanted = {str(c).strip() for c in cycle_ids if str(c).strip()}
        if not wanted:
            return []
        rows = [
            row
            for row in self._rows.values()
            if str(row.cycle_id or "").strip() in wanted
            and (account_id is None or row.account_id == account_id)
        ]
        return rows[:limit] if limit is not None and limit > 0 else rows


class _FullSettlement:
    """Seam hermético: un fill COMPLETO por orden y con la ``price_source`` propuesta."""

    def __init__(self) -> None:
        self.sides: list[str] = []

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
            logical_order_id=kwargs.get("logical_order_id") or "ord",
        )
        self.sides.append(side)
        fills = (
            SimulatedFill(
                fill_seq=1,
                qty_delta=quantity,
                price=_PRICE,
                occurred_after_seconds=0.1,
                venue_order_id=vid,
            ),
        )
        outcomes = await apply_simulated_order_once(
            store,
            result=SimulatedOrderResult(
                venue_order_id=vid,
                status="filled",
                reason="ok",
                scheduled_gap_seconds=0.1,
                fills=fills,
                queue_event="ok",
                cumulative_filled_quantity=quantity,
            ),
            instrument_id=instrument_id,
            account_id=account_id,
            venue=venue,
            side=side,
            context_store=kwargs.get("context_store"),
            apply_finance=kwargs.get("apply_finance"),
            owner=str(kwargs.get("owner", "auto-sim")),
            strategy_version_id=kwargs.get("strategy_version_id"),
            cycle_id=kwargs.get("cycle_id"),
            reference_mid=kwargs.get("base_mid"),
            price_source=kwargs.get("price_source"),
        )
        return (
            SimulatedOrderResult(
                venue_order_id=vid,
                status="filled",
                reason="ok",
                scheduled_gap_seconds=0.1,
                fills=fills,
                queue_event="ok",
                cumulative_filled_quantity=quantity,
            ),
            outcomes,
        )


def _buy() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _d


def _hold() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _edge_source(value: float = 0.9) -> Any:
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


def _ledger_reader(store: Any, contexts: Any) -> Any:
    async def _read(account_id: str) -> Any:
        read = await read_applied_fill_facts(
            store, contexts, account_id, limit=DEFAULT_APPLIED_LIMIT
        )
        if not read.is_complete:
            return None
        return build_canonical_positions(read)

    return _read


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
    worker._v2_tunables = replace(worker._v2_tunables, regime_override="UNKNOWN")  # noqa: SLF001


# ── 1. La fuente viaja al contexto financiero durable ────────────────────────────────


@pytest.mark.asyncio
async def test_submit_simulated_order_persists_the_price_source() -> None:
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    result, _outcomes = await submit_simulated_order(
        store,
        instrument_id="AAA",
        side="buy",
        quantity=Decimal("10"),
        account_id=_ACCOUNT,
        venue="paper",
        seed=1,
        base_mid=100.0,
        fill_chunks=1,
        context_store=contexts,
        cycle_id="cyc-1",
        price_source="market_close",  # se normaliza a mayúsculas
    )
    assert result.fills
    fills = await contexts.list_by_cycle_ids(_ACCOUNT, ["cyc-1"])
    assert fills and all(fill.price_source == PRICE_SOURCE_MARKET_CLOSE for fill in fills)


# ── 2. El worker declara la fuente que de verdad usó ─────────────────────────────────


def test_worker_price_source_kind_is_honest_about_the_source() -> None:
    worker = object.__new__(AutoSimulationWorker)
    worker._price_source = None
    worker._price_script = flat_price_script
    assert worker._v2_price_source_kind() == PRICE_SOURCE_SYNTHETIC

    worker._price_script = lambda _symbol, _tick: 42.0
    assert worker._v2_price_source_kind() == PRICE_SOURCE_SCRIPT

    worker._price_source = SimpleNamespace(kind=PRICE_SOURCE_MARKET_CLOSE)
    assert worker._v2_price_source_kind() == PRICE_SOURCE_MARKET_CLOSE

    worker._price_source = SimpleNamespace(kind="NONSENSE")
    assert worker._v2_price_source_kind() is None, "una fuente ajena se declara no medida"


# ── 3. Hechos durables: ENTRADA con fill aplicado y LIQUIDACIÓN al cerrar ─────────────


async def _entry_turn(
    monkeypatch: pytest.MonkeyPatch,
    *,
    seam: _FullSettlement,
    sink: Any | None,
    store: Any,
    contexts: Any,
    positions: Any,
) -> AutoSimulationWorker:
    monkeypatch.setattr(worker_module, "submit_simulated_order", seam)
    worker = _worker(
        exec_store=store,
        context_store=contexts,
        position_store=positions,
        account_id=_ACCOUNT,
        finance_applier=_MoneyApplier(),
        canonical_positions_reader=_ledger_reader(store, contexts),
        operational_audit_sink=sink,
    )
    worker._decider = _buy()  # noqa: SLF001
    await worker.auto_turn()
    return worker


@pytest.mark.asyncio
async def test_entry_order_and_settlement_are_journaled_durably(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemoryExecutionEventStore()
    contexts = _OrderedContexts()
    positions = InMemorySimAutoPositionStore()
    sink = _Collector()
    worker = await _entry_turn(
        monkeypatch, seam=_FullSettlement(), sink=sink, store=store, contexts=contexts, positions=positions
    )

    entry_events = [e for e in sink.entries if e.event_type == "auto_entry_order"]
    assert len(entry_events) == 1
    payload = entry_events[0].payload
    # El fill es COMPLETO: pedido y materializado coinciden (el sizing V2 fija la cantidad).
    assert payload["appliedQty"] > 0
    assert payload["appliedQty"] == payload["requestedQty"]
    assert payload["partial"] is False
    assert payload["priceSource"] == PRICE_SOURCE_SYNTHETIC  # script hermético → SYNTHETIC
    cycle_id = payload["cycleId"]

    # El fill durable también declara la fuente (migración 047).
    fills = await contexts.list_by_cycle_ids(_ACCOUNT, [cycle_id])
    assert fills and all(fill.price_source == PRICE_SOURCE_SYNTHETIC for fill in fills)

    # Cierre del ciclo: exit-only + HOLD hasta quedar plano.
    _exit_only(worker)
    worker._decider = _hold()  # noqa: SLF001
    for _ in range(10):
        await worker.auto_turn()
        if not worker.open_symbols:
            break
    assert worker.open_symbols == ()

    settlements = [e for e in sink.entries if e.event_type == "auto_cycle_settlement"]
    assert len(settlements) == 1
    settled = settlements[0].payload
    assert settled["cycleId"] == cycle_id
    assert settled["closedQty"] == payload["appliedQty"]
    # Compra y venta al mismo precio: 0 es un PnL MEDIDO (no un hueco).
    assert settled["pnl"] == 0.0
    assert settled["pnlMeasurement"] == "COMPLETE"


@pytest.mark.asyncio
async def test_without_a_sink_the_engine_produces_exactly_the_same(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Δ = 0: sin sumidero no hay eventos y el motor abre igual; la fuente sigue siendo durable."""
    store = InMemoryExecutionEventStore()
    contexts = InMemorySimFillFinanceContextStore()
    positions = InMemorySimAutoPositionStore()
    worker = await _entry_turn(
        monkeypatch,
        seam=_FullSettlement(),
        sink=None,
        store=store,
        contexts=contexts,
        positions=positions,
    )
    assert worker._operational_audit_sink is None  # noqa: SLF001
    assert worker._open[_SYMBOL] > 0  # noqa: SLF001 — el motor abre igual sin sumidero
    # La columna ``price_source`` NO depende del flag de auditoría: se sella igual.
    fills = await contexts.list_by_cycle_ids(_ACCOUNT, [worker._v2_cycle_for(_SYMBOL)])
    assert fills and all(fill.price_source == PRICE_SOURCE_SYNTHETIC for fill in fills)
