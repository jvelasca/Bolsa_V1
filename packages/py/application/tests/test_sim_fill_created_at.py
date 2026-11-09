"""v2.101 — el fill NUEVO sella el instante del tick (auditoría externa 2026-11-08).

El hueco medido: 1.045 fills del artefacto de evidencia no tenían día, así que la curva de
equity los dejaba fuera (``day`` como motivo de exclusión). El escritor durable no recibía el
instante y el doble hermético no lo inventaba — correcto —, pero el worker SÍ lo conoce: su
reloj de tick. Este test fija las dos mitades:

* con ``created_at`` declarado, la fila lo guarda (el fill es situable en su día);
* sin él, sigue siendo ``None`` (hueco declarado, NUNCA ``now()`` del proceso).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore
from bolsa_application.simulated_broker import SimulatedFill, SimulatedOrderResult
from bolsa_application.simulated_settlement import apply_simulated_order_once

_AT = datetime(2024, 3, 5, 14, 30, tzinfo=UTC)


def _result() -> SimulatedOrderResult:
    fill = SimulatedFill(
        fill_seq=1,
        qty_delta=Decimal("10"),
        price=Decimal("100.25"),
        occurred_after_seconds=0.1,
        venue_order_id="venue-1",
    )
    return SimulatedOrderResult(
        venue_order_id="venue-1",
        status="filled",
        reason=None,
        scheduled_gap_seconds=0.0,
        fills=(fill,),
        queue_event="ok",
        cumulative_filled_quantity=Decimal("10"),
    )


async def _settle(store: InMemorySimFillFinanceContextStore, **kwargs: object) -> None:
    await apply_simulated_order_once(
        InMemoryExecutionEventStore(),
        result=_result(),
        instrument_id="AAA",
        account_id="acc-1",
        venue="simulated",
        side="buy",
        context_store=store,
        **kwargs,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_a_new_fill_persists_the_tick_instant() -> None:
    store = InMemorySimFillFinanceContextStore()

    await _settle(store, created_at=_AT)

    row = await store.get("venue-1#1")
    assert row is not None
    assert row.created_at == _AT


@pytest.mark.asyncio
async def test_without_a_declared_instant_the_gap_is_declared_not_filled() -> None:
    store = InMemorySimFillFinanceContextStore()

    await _settle(store)

    row = await store.get("venue-1#1")
    assert row is not None
    assert row.created_at is None
