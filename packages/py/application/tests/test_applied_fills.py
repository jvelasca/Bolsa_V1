"""AUTO-1A — libro de posición desde fills APLICADOS (``applied_fills``).

Certifica la identidad canónica ``POSITION = Σ APPLIED`` y, sobre todo, que los modos de
fallo (contexto ausente, lectura truncada, descuadre de cantidad) se DECLARAN en lugar de
producir una posición plausible.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.applied_fills import (
    read_applied_fill_facts,
    read_position_ledger,
)
from bolsa_application.execution_event import (
    ExecutionEvent,
    InMemoryExecutionEventStore,
)
from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

ACC = "acc-auto-1"


class _BoomManyContextStore(InMemorySimFillFinanceContextStore):
    async def get_many(self, execution_ids):  # type: ignore[no-untyped-def]
        raise RuntimeError("context read exploded")


class _NoListAppliedStore(InMemoryExecutionEventStore):
    list_applied = None  # type: ignore[assignment]


async def _apply(
    store: InMemoryExecutionEventStore,
    execution_id: str,
    *,
    qty: str,
    account_id: str | None = ACC,
) -> None:
    event = ExecutionEvent(
        execution_id=execution_id,
        order_id=f"ord-{execution_id}",
        venue="SIMULATED",
        venue_order_id=f"sim-{execution_id}",
        fill_seq=1,
        qty=Decimal(qty),
        account_id=account_id,
    )
    await store.capture(event)
    assert await store.start_apply(execution_id, owner="w") is True
    assert await store.mark_applied(execution_id, lease_owner="w") is True


async def _context(
    store: InMemorySimFillFinanceContextStore,
    execution_id: str,
    *,
    side: str,
    quantity: str,
    price: str,
    instrument_id: str = "AAA",
) -> None:
    from bolsa_application.sim_durable_store import SimFillFinanceContext

    await store.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id=instrument_id,
            side=side,
            quantity=Decimal(quantity),
            price=Decimal(price),
            account_id=ACC,
        )
    )


@pytest.mark.asyncio
async def test_partial_entry_materializes_only_applied_fills() -> None:
    """Caso auditoría: BUY 100 con fills aplicados 50 + 23,5 ⇒ posición 73,5."""
    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    for execution_id, qty in (("e1", "50"), ("e2", "23.5")):
        await _apply(exec_store, execution_id, qty=qty)
        await _context(context_store, execution_id, side="buy", quantity=qty, price="100")

    read = await read_applied_fill_facts(exec_store, context_store, ACC)
    assert read.measurement == MEASUREMENT_COMPLETE
    assert read.is_complete is True
    assert read.quantities() == {"AAA": 73.5}
    position = read.position("AAA")
    assert position is not None
    assert position.quantity == 73.5
    assert position.average_entry == 100.0
    assert read.rejected == 0
    assert read.mismatched == 0
    assert read.truncated is False


@pytest.mark.asyncio
async def test_retry_fills_are_pending_capital_not_position() -> None:
    """Un chunk en ``RETRY`` nunca es posición: reserva capital, no materializa."""
    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    await _apply(exec_store, "e1", qty="50")
    await _context(context_store, "e1", side="buy", quantity="50", price="100")
    # Chunk de cola: contexto persistido ANTES de mover dinero, apply no efectivo.
    await exec_store.capture(
        ExecutionEvent(
            execution_id="e2",
            order_id="ord-e2",
            venue="SIMULATED",
            venue_order_id="sim-e2",
            fill_seq=2,
            qty=Decimal("50"),
            account_id=ACC,
        )
    )
    assert await exec_store.start_apply("e2", owner="w") is True
    assert await exec_store.mark_retry("e2", error="venue busy", lease_owner="w") is True
    await _context(context_store, "e2", side="buy", quantity="50", price="100")

    read = await read_applied_fill_facts(exec_store, context_store, ACC)
    assert read.quantities() == {"AAA": 50.0}
    assert read.facts_applied == 1
    # Y sigue siendo visible como capital comprometido (no desaparece del sistema).
    pending = await exec_store.list_unapplied(ACC)
    assert [row.execution_id for row in pending] == ["e2"]


@pytest.mark.asyncio
async def test_applied_without_context_is_declared_not_dropped() -> None:
    """Un ``APPLIED`` cuyo contexto falta no se omite en silencio: baja el measurement."""
    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    await _apply(exec_store, "e1", qty="50")
    await _context(context_store, "e1", side="buy", quantity="50", price="100")
    await _apply(exec_store, "e2", qty="23.5")

    read = await read_applied_fill_facts(exec_store, context_store, ACC)
    assert read.rejected == 1
    assert read.measurement == MEASUREMENT_PARTIAL
    assert read.is_complete is False
    assert read.quantities() == {"AAA": 50.0}


@pytest.mark.asyncio
async def test_quantity_mismatch_between_event_and_context_is_declared() -> None:
    """La identidad financiera manda en cantidad; el descuadre se declara, no se oculta."""
    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    await _apply(exec_store, "e1", qty="50")
    await _context(context_store, "e1", side="buy", quantity="80", price="100")

    read = await read_applied_fill_facts(exec_store, context_store, ACC)
    assert read.mismatched == 1
    assert read.measurement == MEASUREMENT_PARTIAL
    assert read.quantities() == {"AAA": 50.0}


@pytest.mark.asyncio
async def test_full_exit_leaves_flat_book_and_realized_pnl() -> None:
    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    await _apply(exec_store, "e1", qty="73.5")
    await _context(context_store, "e1", side="buy", quantity="73.5", price="100")
    await _apply(exec_store, "e2", qty="73.5")
    await _context(context_store, "e2", side="sell", quantity="73.5", price="104")

    read = await read_applied_fill_facts(exec_store, context_store, ACC)
    assert read.measurement == MEASUREMENT_COMPLETE
    assert read.quantities() == {}
    position = read.position("AAA")
    assert position is not None
    assert position.remaining_qty == 0.0
    assert position.realized_pnl == 294.0


@pytest.mark.asyncio
async def test_truncated_read_is_unknown_not_a_smaller_book() -> None:
    """Ver ``limit`` filas NO es ver el libro: se declara ``UNKNOWN``."""
    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    for index in range(3):
        execution_id = f"e{index}"
        await _apply(exec_store, execution_id, qty="10")
        await _context(context_store, execution_id, side="buy", quantity="10", price="100")

    read = await read_applied_fill_facts(exec_store, context_store, ACC, limit=3)
    assert read.truncated is True
    assert read.measurement == MEASUREMENT_UNKNOWN
    assert read.is_complete is False


@pytest.mark.asyncio
async def test_unreadable_sources_are_unknown_never_empty() -> None:
    """Sin store, sin soporte de listado, con excepción o sin contexto ⇒ UNKNOWN."""
    assert (await read_applied_fill_facts(None, None, ACC)).measurement == MEASUREMENT_UNKNOWN

    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    await _apply(exec_store, "e1", qty="10")

    no_lister = await read_applied_fill_facts(
        _NoListAppliedStore(), context_store, ACC
    )
    assert no_lister.measurement == MEASUREMENT_UNKNOWN
    assert no_lister.error == "store_without_list_applied"

    no_context = await read_applied_fill_facts(exec_store, None, ACC)
    assert no_context.measurement == MEASUREMENT_UNKNOWN
    assert no_context.rejected == 1

    boom = await read_applied_fill_facts(exec_store, _BoomManyContextStore(), ACC)
    assert boom.measurement == MEASUREMENT_UNKNOWN
    assert boom.error is not None and boom.error.startswith("get_many_failed")

    await _context(context_store, "e1", side="buy", quantity="10", price="100")
    zero_limit = await read_applied_fill_facts(exec_store, context_store, ACC, limit=0)
    assert zero_limit.measurement == MEASUREMENT_UNKNOWN
    assert zero_limit.error == "non_positive_limit"


@pytest.mark.asyncio
async def test_empty_book_is_complete_and_flat() -> None:
    read = await read_applied_fill_facts(
        InMemoryExecutionEventStore(), InMemorySimFillFinanceContextStore(), ACC
    )
    assert read.measurement == MEASUREMENT_COMPLETE
    assert read.quantities() == {}


@pytest.mark.asyncio
async def test_read_position_ledger_shortcut_matches_full_read() -> None:
    exec_store = InMemoryExecutionEventStore()
    context_store = InMemorySimFillFinanceContextStore()
    await _apply(exec_store, "e1", qty="23.5")
    await _context(context_store, "e1", side="buy", quantity="23.5", price="100")

    read = await read_applied_fill_facts(exec_store, context_store, ACC)
    ledger = await read_position_ledger(exec_store, context_store, ACC)
    assert ledger.to_dict() == read.ledger.to_dict()
