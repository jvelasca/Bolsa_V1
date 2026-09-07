"""V2.14 E1 — ExecutionEvent idempotencia financiera (P1-01) GATED.

Semántica que el audit pide (no contador): la idempotencia es la key
``execution_id``; un fill duplicado no materializa dinero dos veces; y la
materialización real (Position/Ledger) NO se abre por defecto (H4/H3 honesto:
captura sin apply hasta go explícito).
"""

from __future__ import annotations

import pytest

from bolsa_application.execution_event import (
    ExecutionEvent,
    InMemoryExecutionEventStore,
    apply_fill_idempotent,
)


def _exec(event_id: str = "ev-1", *, qty: str = "40") -> ExecutionEvent:
    from decimal import Decimal

    return ExecutionEvent(
        execution_id=event_id,
        order_id="lo-fill-1",
        venue="LIVE",
        venue_order_id="xtb-11",
        fill_seq=1,
        qty=Decimal(qty),
        account_id="acc-1",
    )


@pytest.mark.asyncio
async def test_duplicate_execution_id_skips_finance_apply() -> None:
    """El MISMO execution_id insertado dos veces → el 2º NO vuelve a materializar."""
    store = InMemoryExecutionEventStore()
    apply_calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        apply_calls.append(execution.execution_id)
        return True

    ev = _exec()
    first = await apply_fill_idempotent(
        store, execution=ev, permit=True, apply_finance=applier
    )
    assert first == "applied"
    second = await apply_fill_idempotent(
        store, execution=ev, permit=True, apply_finance=applier
    )
    # El duplicado se descarta: aunque permit=True y haya applier, NO se aplica 2×.
    assert second == "duplicate_skipped"
    assert apply_calls == ["ev-1"]  # una sola materialización


@pytest.mark.asyncio
async def test_permit_false_captures_but_never_materializes() -> None:
    """Sin go → la fila se captura pero Position/Ledger NO se tocan (default)."""
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        raise AssertionError("apply_finance no debe invocarse sin permit")

    ev = _exec()
    decision = await apply_fill_idempotent(
        store, execution=ev, permit=False, apply_finance=applier
    )
    assert decision == "captured_pending_operator_consent"
    assert await store.get(ev.execution_id) is not None  # traza persistida


@pytest.mark.asyncio
async def test_applier_false_returns_captured_not_applied() -> None:
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        return False

    ev = _exec()
    decision = await apply_fill_idempotent(
        store, execution=ev, permit=True, apply_finance=applier
    )
    assert decision == "captured_not_applied"


@pytest.mark.asyncio
async def test_default_no_applier_never_materializes() -> None:
    """Incluso llamando sin applier ni permit: solo captura (fail-closed)."""
    store = InMemoryExecutionEventStore()
    ev = _exec()
    assert (
        await apply_fill_idempotent(store, execution=ev)
        == "captured_pending_operator_consent"
    )


def test_event_requires_execution_id() -> None:
    from decimal import Decimal

    with pytest.raises(ValueError):
        ExecutionEvent(
            execution_id="",
            order_id="o",
            venue="LIVE",
            qty=Decimal("1"),
        )
