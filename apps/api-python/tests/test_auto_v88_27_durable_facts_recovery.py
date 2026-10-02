"""AUTO v2.88.27 — recuperación del ``SETTLEMENT`` que un crash dejó sin publicar (hermético).

Qué certifica este fichero, sin I/O:

1. **El settlement se reconstruye SÓLO de lo que los fills demuestran.** ``settlement_snapshot_from_fills``
   deriva instrumento, cantidad liquidada (Σ ventas) y fuente de precio del fill de cierre; sin
   ventas o sin dato utilizable devuelve ``None`` (jamás un hecho a medias).
2. **La recuperación sella el hueco.** Un ciclo cerrado por los fills durables pero sin
   ``auto_cycle_settlement`` en el spine se reemite al arrancar, con el MISMO FIFO
   (``cycles_from_fills``) y un ``exitReason=None`` DECLARADO (no se inventa el motivo).
3. **El reenvío es idempotente.** La identidad determinista (``dedupe_key``) hace que dos procesos
   que recuperen el mismo ciclo produzcan UNA fila; y un ciclo que YA tiene settlement no se toca.
4. **Fail-open declarado.** Sin lector, con la ventana truncada o con el ciclo aún abierto NO se
   afirma nada (se registra), nunca se inventa una liquidación.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    settlement_snapshot_from_fills,
    step_minute_clock,
)
from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)

_ACCOUNT = "acc-rec"
_SYMBOL = "AAA"
_ENGINE = "auto-sim"
_CYCLE = "cyc-rec-1"


class _Collector:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def __call__(self, entry: Any) -> None:
        self.entries.append(entry)


class _DedupingSink:
    """Sumidero con la MISMA semántica del ``append`` idempotente: una fila por ``dedupe_key``."""

    def __init__(self) -> None:
        self.by_key: dict[str, Any] = {}

    async def __call__(self, entry: Any) -> None:
        key = getattr(entry, "dedupe_key", None)
        assert key, "un hecho M2 recuperado debe declarar identidad determinista"
        self.by_key.setdefault(key, entry)


def _reader(settled: frozenset[str] = frozenset()) -> Any:
    async def _read(_event_type: str) -> frozenset[str]:
        return settled

    return _read


async def _seed_closed_cycle(
    contexts: InMemorySimFillFinanceContextStore,
    *,
    cycle_id: str = _CYCLE,
    sell_price: str = "110",
) -> None:
    await contexts.save(
        SimFillFinanceContext(
            execution_id=f"{cycle_id}-buy",
            instrument_id=_SYMBOL,
            side="buy",
            quantity=Decimal("10"),
            price=Decimal("100"),
            account_id=_ACCOUNT,
            cycle_id=cycle_id,
            price_source="SYNTHETIC",
        )
    )
    await contexts.save(
        SimFillFinanceContext(
            execution_id=f"{cycle_id}-sell",
            instrument_id=_SYMBOL,
            side="sell",
            quantity=Decimal("10"),
            price=Decimal(sell_price),
            account_id=_ACCOUNT,
            cycle_id=cycle_id,
            price_source="SYNTHETIC",
        )
    )


def _recovery_worker(
    *,
    contexts: InMemorySimFillFinanceContextStore,
    sink: Any,
    reader: Any | None,
) -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 10, 2, 9, 0, tzinfo=UTC))[1],
        context_store=contexts,
        account_id=_ACCOUNT,
        operational_audit_sink=sink,
        durable_fact_cycle_reader=reader,
    )


# ── 1. La instantánea del settlement sólo deriva lo que los fills declaran ────────────


def test_snapshot_from_fills_derives_instrument_qty_and_closing_source() -> None:
    fills = [
        SimpleNamespace(
            side="buy",
            instrument_id=_SYMBOL,
            quantity=Decimal("10"),
            price=Decimal("100"),
            price_source="SYNTHETIC",
        ),
        SimpleNamespace(
            side="sell",
            instrument_id=_SYMBOL,
            quantity=Decimal("10"),
            price=Decimal("110"),
            price_source="SCRIPT",
        ),
    ]
    assert settlement_snapshot_from_fills(fills) == {
        "instrument_id": _SYMBOL,
        "closed_qty": Decimal("10"),
        "price_source": "SCRIPT",
    }


def test_snapshot_from_fills_without_sales_or_usable_qty_is_none() -> None:
    buy_only = [
        SimpleNamespace(
            side="buy",
            instrument_id=_SYMBOL,
            quantity=Decimal("10"),
            price=Decimal("100"),
            price_source="SYNTHETIC",
        )
    ]
    assert settlement_snapshot_from_fills(buy_only) is None
    zero_sell = [
        SimpleNamespace(
            side="sell",
            instrument_id=_SYMBOL,
            quantity=Decimal("0"),
            price=Decimal("110"),
            price_source="SYNTHETIC",
        )
    ]
    assert settlement_snapshot_from_fills(zero_sell) is None
    no_instrument = [
        SimpleNamespace(
            side="sell",
            instrument_id="",
            quantity=Decimal("10"),
            price=Decimal("110"),
            price_source="SYNTHETIC",
        )
    ]
    assert settlement_snapshot_from_fills(no_instrument) is None


# ── 2. La recuperación sella el hueco de un crash ─────────────────────────────────────


@pytest.mark.asyncio
async def test_recovery_emits_the_settlement_a_crash_left_unpublished() -> None:
    contexts = InMemorySimFillFinanceContextStore()
    await _seed_closed_cycle(contexts)
    sink = _Collector()
    worker = _recovery_worker(contexts=contexts, sink=sink, reader=_reader())

    await worker._v2_recover_durable_facts()  # noqa: SLF001 — método bajo prueba.

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.event_type == "auto_cycle_settlement"
    assert entry.dedupe_key == f"auto_cycle_settlement:{_ACCOUNT}:{_ENGINE}:{_CYCLE}"
    payload = entry.payload
    assert payload["cycleId"] == _CYCLE
    assert payload["closedQty"] == 10
    # Compra a 100 y venta a 110 de 10 títulos: 100 es un PnL MEDIDO por el FIFO durable.
    assert payload["pnl"] == 100.0
    assert payload["pnlMeasurement"] == "COMPLETE"
    assert payload["priceSource"] == "SYNTHETIC"
    # El motivo de salida NO viaja en el fill: se declara ausente, nunca se inventa.
    assert payload["exitReason"] is None


@pytest.mark.asyncio
async def test_recovery_is_idempotent_across_processes() -> None:
    """Dos procesos que recuperan el MISMO ciclo producen UNA fila (identidad determinista)."""
    contexts = InMemorySimFillFinanceContextStore()
    await _seed_closed_cycle(contexts)
    sink = _DedupingSink()

    for _ in range(2):
        worker = _recovery_worker(contexts=contexts, sink=sink, reader=_reader())
        await worker._v2_recover_durable_facts()  # noqa: SLF001

    assert len(sink.by_key) == 1
    assert f"auto_cycle_settlement:{_ACCOUNT}:{_ENGINE}:{_CYCLE}" in sink.by_key


@pytest.mark.asyncio
async def test_recovery_does_not_touch_a_cycle_that_already_has_settlement() -> None:
    contexts = InMemorySimFillFinanceContextStore()
    await _seed_closed_cycle(contexts)
    sink = _Collector()
    worker = _recovery_worker(
        contexts=contexts, sink=sink, reader=_reader(frozenset({_CYCLE}))
    )

    await worker._v2_recover_durable_facts()  # noqa: SLF001

    assert sink.entries == []


@pytest.mark.asyncio
async def test_recovery_runs_once_per_process() -> None:
    contexts = InMemorySimFillFinanceContextStore()
    await _seed_closed_cycle(contexts)
    sink = _Collector()
    worker = _recovery_worker(contexts=contexts, sink=sink, reader=_reader())

    await worker._v2_recover_durable_facts()  # noqa: SLF001
    await worker._v2_recover_durable_facts()  # noqa: SLF001 — el flag lo corta.

    assert len(sink.entries) == 1


# ── 3. Fail-open declarado: lo que no se puede demostrar no se afirma ─────────────────


@pytest.mark.asyncio
async def test_recovery_without_a_reader_does_not_emit_anything() -> None:
    contexts = InMemorySimFillFinanceContextStore()
    await _seed_closed_cycle(contexts)
    sink = _Collector()
    worker = _recovery_worker(contexts=contexts, sink=sink, reader=None)

    await worker._v2_recover_durable_facts()  # noqa: SLF001

    assert sink.entries == []


@pytest.mark.asyncio
async def test_an_open_cycle_is_not_a_settlement() -> None:
    contexts = InMemorySimFillFinanceContextStore()
    await contexts.save(
        SimFillFinanceContext(
            execution_id=f"{_CYCLE}-buy",
            instrument_id=_SYMBOL,
            side="buy",
            quantity=Decimal("10"),
            price=Decimal("100"),
            account_id=_ACCOUNT,
            cycle_id=_CYCLE,
            price_source="SYNTHETIC",
        )
    )
    sink = _Collector()
    worker = _recovery_worker(contexts=contexts, sink=sink, reader=_reader())

    await worker._v2_recover_durable_facts()  # noqa: SLF001

    assert sink.entries == []
