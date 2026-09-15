"""AUTO 2.0 · P4 — durabilidad del estado V2 (plan de posición + señales consumidas).

Test hermético de los stores en memoria que implementan los mismos Protocols que los
Postgres: ``SimPositionProjection.position_state`` (el plan operativo sobrevive) y
``SimConsumedSignalStore`` (la deduplicación por barra sobrevive). No toca PostgreSQL:
el objetivo es fijar la SEMÁNTICA que el worker necesita del espejo durable.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimConsumedSignalStore,
    rebuild_sim_position_projection,
)

_PLAN: dict[str, object] = {
    "positionId": "pos-1",
    "tradePlanId": "dec-1",
    "instrumentId": "AAA",
    "direction": "long",
    "status": "OPEN",
    "currentStop": 97.0,
    "remainingQuantity": 100.0,
    "quantity": 100.0,
}


@pytest.mark.asyncio
async def test_position_state_survives_upsert_and_read() -> None:
    """El plan V2 viaja íntegro: ``upsert`` → ``read_projection`` devuelve el blob."""
    store = InMemorySimAutoPositionStore()
    await store.upsert(
        "acc-1",
        "auto-sim",
        "AAA",
        Decimal("100"),
        entry_price=Decimal("100"),
        high_watermark=Decimal("100"),
        position_state=_PLAN,
    )
    row = (await store.read_projection("acc-1", "auto-sim"))["AAA"]
    assert row.position_state == _PLAN
    assert row.entry_price == Decimal("100")


@pytest.mark.asyncio
async def test_upsert_without_plan_does_not_resurrect_old_plan() -> None:
    """Un upsert sin plan deja el espejo SIN plan (la verdad: no hay plan vivo).

    Nunca se conserva un plan viejo por omisión: el espejo refleja lo que el motor
    está siguiendo de verdad, no lo que siguió alguna vez.
    """
    store = InMemorySimAutoPositionStore()
    await store.upsert("acc-1", "auto-sim", "AAA", Decimal("100"), position_state=_PLAN)
    await store.upsert("acc-1", "auto-sim", "AAA", Decimal("50"))
    row = (await store.read_projection("acc-1", "auto-sim"))["AAA"]
    assert row.position_state is None
    assert row.quantity == Decimal("50")


@pytest.mark.asyncio
async def test_rebuild_keeps_plan_and_adjusts_only_quantity() -> None:
    """Reconstruir contra el canónico ajusta la CANTIDAD, jamás el plan operativo."""

    async def canonical(_account_id: str) -> dict[str, Decimal]:
        return {"AAA": Decimal("80")}

    store = InMemorySimAutoPositionStore()
    await store.upsert(
        "acc-1",
        "auto-sim",
        "AAA",
        Decimal("100"),
        entry_price=Decimal("100"),
        high_watermark=Decimal("105"),
        position_state=_PLAN,
    )
    rebuilt = await rebuild_sim_position_projection(
        account_id="acc-1",
        engine_id="auto-sim",
        position_store=store,
        canonical_reader=canonical,
    )
    assert rebuilt == {"AAA": Decimal("80")}
    row = (await store.read_projection("acc-1", "auto-sim"))["AAA"]
    assert row.quantity == Decimal("80")
    assert row.position_state == _PLAN, "el plan sobrevive a la reconstrucción"
    assert row.high_watermark == Decimal("105")


@pytest.mark.asyncio
async def test_consumed_signal_mark_is_idempotent_and_scoped_by_bar() -> None:
    """Marcar dos veces la misma señal no duplica; la lectura va acotada por barra."""
    store = InMemorySimConsumedSignalStore()
    bar_a = "2026-09-15T09:00:00+00:00"
    bar_b = "2026-09-15T09:01:00+00:00"
    for _ in range(2):
        await store.mark("acc-1", "auto-sim", "sig-1", instrument_id="AAA", bar_timestamp=bar_a)
    await store.mark("acc-1", "auto-sim", "sig-2", instrument_id="BBB", bar_timestamp=bar_b)
    assert await store.list_bar("acc-1", "auto-sim", bar_a) == ["sig-1"]
    assert await store.list_bar("acc-1", "auto-sim", bar_b) == ["sig-2"]
    # Otra cuenta (o engine) no ve nada: el dedupe no se filtra entre espejos.
    assert await store.list_bar("acc-2", "auto-sim", bar_a) == []
    assert await store.list_bar("acc-1", "auto-other", bar_a) == []


@pytest.mark.asyncio
async def test_consumed_signal_prune_drops_previous_bars() -> None:
    """La poda solo conserva la barra corriente: la tabla no crece sin límite."""
    store = InMemorySimConsumedSignalStore()
    old_bar = "2026-09-15T09:00:00+00:00"
    now_bar = "2026-09-15T09:01:00+00:00"
    await store.mark("acc-1", "auto-sim", "sig-old", instrument_id="AAA", bar_timestamp=old_bar)
    await store.mark("acc-1", "auto-sim", "sig-now", instrument_id="AAA", bar_timestamp=now_bar)
    removed = await store.prune_before("acc-1", "auto-sim", now_bar)
    assert removed == 1
    assert await store.list_bar("acc-1", "auto-sim", old_bar) == []
    assert await store.list_bar("acc-1", "auto-sim", now_bar) == ["sig-now"]
