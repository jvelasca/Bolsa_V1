"""V2.12 — LiveOrderStore contract (InMemory + PG mapping stub, sin DB).

Verifica el mapeo 1:1 dominio↔fila física de ``PostgresLiveOrderStore``
(account_id incluida tras la faena XL-3 durable) y la semántica fail-closed de
``list_unknown``/integro, con sesión AsyncMock (patrón test_submit_intent_store_pg).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_analytics.cognitive.live_order import (
    LiveOrder,
    build_live_order,
    transition_live_order,
)
from sqlalchemy.exc import IntegrityError

from bolsa_application.live_order_store import (
    InMemoryLiveOrderStore,
    PostgresLiveOrderStore,
)


def _make_order(*, order_id: str = "lo-1", account_id: str = "acc-1") -> LiveOrder:
    order = build_live_order(
        order_id=order_id,
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
        account_id=account_id,
    )
    return transition_live_order(
        transition_live_order(order, "SUBMITTING"),
        "SUBMITTED",
        venue_order_id="xtb-1",
    )


def _row_from(order: LiveOrder) -> MagicMock:
    row = MagicMock()
    row.order_id = order.order_id
    row.account_id = order.account_id
    row.status = order.status
    row.venue = order.venue
    row.instrument_id = order.instrument_id
    row.side = order.side
    row.quantity = order.quantity
    row.filled_quantity = order.filled_quantity
    row.remaining_quantity = order.remaining_quantity
    row.venue_order_id = order.venue_order_id
    row.intent_id = order.intent_id
    row.financial_apply_count = order.financial_apply_count
    return row


@pytest.mark.asyncio
async def test_inmemory_put_get_delete_roundtrip() -> None:
    store = InMemoryLiveOrderStore()
    order = _make_order(order_id="lo-im", account_id="acc-1")
    await store.put(order)
    got = await store.get("lo-im")
    assert got is not None
    assert got.status == "SUBMITTED"
    assert got.venue_order_id == "xtb-1"
    assert got.account_id == "acc-1"
    await store.delete("lo-im")
    assert await store.get("lo-im") is None


@pytest.mark.asyncio
async def test_inmemory_list_unknown_filters_only_unknown() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-sub", account_id="acc-1"))
    unknown = _make_order(order_id="lo-unk", account_id="acc-1")
    await store.put(transition_live_order(unknown, "UNKNOWN"))
    await store.put(_make_order(order_id="lo-other", account_id="acc-2"))

    rows = await store.list_unknown(limit=50)
    assert [r.order_id for r in rows] == ["lo-unk"]


@pytest.mark.asyncio
async def test_postgres_put_fresh_insert_maps_domain_to_row_and_commits() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    # get() en put() → None (no existing); segundo get() consulta la fila nueva.
    session.execute = AsyncMock(return_value=empty)

    order = _make_order(order_id="lo-pg", account_id="acc-9")
    store = PostgresLiveOrderStore(session)
    await store.put(order)

    session.add.assert_called_once()
    session.commit.assert_awaited()
    added = session.add.call_args.args[0]
    assert added.order_id == "lo-pg"
    assert added.account_id == "acc-9"
    assert added.status == "SUBMITTED"
    assert added.side == "buy"
    assert added.quantity == 100.0
    assert added.filled_quantity == 0.0
    assert added.remaining_quantity == 100.0
    assert added.venue_order_id == "xtb-1"


@pytest.mark.asyncio
async def test_postgres_get_maps_row_to_domain_with_account() -> None:
    session = AsyncMock()
    target = _make_order(order_id="lo-get", account_id="acc-3")
    row = _row_from(target)
    found = MagicMock()
    found.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=found)

    store = PostgresLiveOrderStore(session)
    got = await store.get("lo-get")
    assert got is not None
    assert got.order_id == "lo-get"
    assert got.status == "SUBMITTED"
    assert got.account_id == "acc-3"
    assert got.venue_order_id == "xtb-1"


@pytest.mark.asyncio
async def test_postgres_put_updates_existing_row_keeps_account() -> None:
    """put sobre fila existente re-usa account_id e itera status."""
    existing = _make_order(order_id="lo-up", account_id="acc-4")
    existing_row = _row_from(existing)
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    # get() en put() devuelve lo existente dos veces (get + _load_row).
    found = MagicMock()
    found.scalar_one_or_none.return_value = existing_row
    session.execute = AsyncMock(return_value=found)

    store = PostgresLiveOrderStore(session)
    unknown = transition_live_order(existing, "UNKNOWN")
    await store.put(unknown, account_id="acc-4")

    assert existing_row.status == "UNKNOWN"
    assert existing_row.account_id == "acc-4"
    assert existing_row.venue_order_id == "xtb-1"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_postgres_unique_violation_rolls_back() -> None:
    session = AsyncMock()
    session.commit = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("dup")))
    session.rollback = AsyncMock()
    session.add = MagicMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty)

    store = PostgresLiveOrderStore(session)
    with pytest.raises(IntegrityError):
        await store.put(_make_order(order_id="lo-dup", account_id="acc-1"))
    session.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_postgres_list_unknown_maps_filtered_rows() -> None:
    target = _make_order(order_id="lo-unkq", account_id="acc-1")
    target = transition_live_order(target, "UNKNOWN")
    rows_model = [_row_from(target)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows_model
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    store = PostgresLiveOrderStore(session)
    got = await store.list_unknown(limit=10)
    assert len(got) == 1
    assert got[0].order_id == "lo-unkq"
    assert got[0].status == "UNKNOWN"
    assert got[0].account_id == "acc-1"
    session.execute.assert_awaited()


def test_migration_020_chains_to_live_order_head() -> None:
    """Asegura que la migración 020 cuelga de la cabeza real (019_outbox_position_fifo).

    Si un futuro bump renumera la cadena, este guard falla antes de tocarla.
    """
    from pathlib import Path

    from bolsa_infrastructure.database.models.tables import LiveOrderRow

    migration_path = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "py"
        / "infrastructure"
        / "alembic"
        / "versions"
        / "020_live_orders.py"
    )
    assert migration_path.exists()
    src = migration_path.read_text(encoding="utf-8")
    assert 'down_revision = "019_outbox_position_fifo"' in src
    assert 'revision = "020_live_orders"' in src

    # Paridad de columnas: la fila física del modelo expone las columnas que la
    # migración crea (order_id/account_id/status/venue/instrument_id/side/
    # quantity/filled_quantity/remaining_quantity/venue_order_id/intent_id/
    # financial_apply_count/created_at/updated_at).
    cols = {c.name for c in LiveOrderRow.__table__.columns}
    expecting = {
        "order_id",
        "account_id",
        "status",
        "venue",
        "instrument_id",
        "side",
        "quantity",
        "filled_quantity",
        "remaining_quantity",
        "venue_order_id",
        "intent_id",
        "financial_apply_count",
        "created_at",
        "updated_at",
    }
    assert expecting <= cols
