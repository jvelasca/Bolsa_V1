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
    can_transition_live_order,
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


# ---------------------------------------------------------------------------
# V2.12 — list_open_orders (no-terminal) + cancel_order (persist-only honest).
# ---------------------------------------------------------------------------


def _to_unknown(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "UNKNOWN")
    return transition_live_order(order, "UNKNOWN")


def _to_filled(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "WORKING")
    working = transition_live_order(order, "WORKING", venue_order_id="xtb-1")
    return transition_live_order(working, "FILLED", filled_quantity=100.0)


def _to_rejected(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "REJECTED")
    return transition_live_order(order, "REJECTED")


def _to_cancelled(order: LiveOrder) -> LiveOrder:
    assert can_transition_live_order(order.status, "CANCELLED")
    return transition_live_order(order, "CANCELLED")


@pytest.mark.asyncio
async def test_inmemory_list_open_orders_only_non_terminal() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-open-sub", account_id="acc-1"))  # SUBMITTED
    await store.put(_to_unknown(_make_order(order_id="lo-open-unk", account_id="acc-1")))
    await store.put(_to_filled(_make_order(order_id="lo-open-fill", account_id="acc-1")))
    await store.put(_to_rejected(_make_order(order_id="lo-open-rej", account_id="acc-1")))
    await store.put(_to_cancelled(_make_order(order_id="lo-open-cx", account_id="acc-1")))

    rows = await store.list_open_orders(limit=50)
    got = {r.order_id for r in rows}
    # SUBMITTED + UNKNOWN son no-terminales (open); FILLED/REJECTED/CANCELLED no.
    assert got == {"lo-open-sub", "lo-open-unk"}


@pytest.mark.asyncio
async def test_inmemory_list_open_orders_respects_limit_and_counts() -> None:
    store = InMemoryLiveOrderStore()
    for i in range(5):
        await store.put(_make_order(order_id=f"lo-n{i}", account_id="acc-1"))
    limited = await store.list_open_orders(limit=3)
    assert len(limited) == 3


@pytest.mark.asyncio
async def test_postgres_list_open_orders_includes_only_non_terminal() -> None:
    """Barrena la consulta PG (AsyncMock): assert del filtro .in_ y del orden."""
    from bolsa_analytics.cognitive.live_order import NON_TERMINAL_LIVE_STATUSES

    open_row = _row_from(_make_order(order_id="lo-openpg", account_id="acc-1"))
    result = MagicMock()
    result.scalars.return_value.all.return_value = [open_row]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    store = PostgresLiveOrderStore(session)
    got = await store.list_open_orders(limit=10)
    assert [r.order_id for r in got] == ["lo-openpg"]

    stmt = session.execute.await_args.args[0]
    rendered = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    for orphan in NON_TERMINAL_LIVE_STATUSES:
        assert f"'{orphan}'" in rendered
    for terminal in ("FILLED", "REJECTED", "CANCELLED"):
        assert f"'{terminal}'" not in rendered
    assert "UPDATED_AT" in rendered  # orden asc presente (guard de breakage)


@pytest.mark.asyncio
async def test_inmemory_cancel_roundtrip_is_idempotent_single_state() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_make_order(order_id="lo-cx", account_id="acc-1"))

    cancelled = await store.cancel_order("lo-cx", reason="usuario")
    assert cancelled is not None
    assert cancelled.status == "CANCELLED"

    stored = await store.get("lo-cx")
    assert stored is not None and stored.status == "CANCELLED"
    # Estado terminal único: ya no es "open" ni aparece duplicado.
    assert await store.list_open_orders(limit=50) == []
    assert len(store._by_order) == 1

    # Re-cancel: idempotente → devuelve la orden CANCELLED sin duplicar estado.
    again = await store.cancel_order("lo-cx", reason="otra vez")
    assert again is not None and again.status == "CANCELLED"
    assert await store.get("lo-cx") is not None
    assert len(store._by_order) == 1


@pytest.mark.asyncio
async def test_inmemory_cancel_filled_or_rejected_refused() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_to_rejected(_make_order(order_id="lo-rej", account_id="acc-1")))
    await store.put(_to_filled(_make_order(order_id="lo-filled", account_id="acc-1")))

    refused_rej = await store.cancel_order("lo-rej")
    assert refused_rej is not None and refused_rej.status == "REJECTED"

    refused_fill = await store.cancel_order("lo-filled")
    assert refused_fill is not None and refused_fill.status == "FILLED"

    # Siguen terminales en el store: no cancelados, no resucitados.
    rejected_after = await store.get("lo-rej")
    assert rejected_after is not None and rejected_after.status == "REJECTED"
    filled_after = await store.get("lo-filled")
    assert filled_after is not None and filled_after.status == "FILLED"


@pytest.mark.asyncio
async def test_inmemory_cancel_unknown_order_id_returns_none() -> None:
    store = InMemoryLiveOrderStore()
    assert await store.cancel_order("no-such-order") is None
    assert await store.cancel_order("") is None


@pytest.mark.asyncio
async def test_inmemory_cancel_from_unknown_state_is_legal() -> None:
    store = InMemoryLiveOrderStore()
    await store.put(_to_unknown(_make_order(order_id="lo-cxu", account_id="acc-1")))
    result = await store.cancel_order("lo-cxu")
    assert result is not None and result.status == "CANCELLED"
    stored = await store.get("lo-cxu")
    assert stored is not None and stored.status == "CANCELLED"


@pytest.mark.asyncio
async def test_postgres_cancel_persists_cancelled_and_idempotent() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    existing_row = _row_from(_make_order(order_id="lo-cxpg", account_id="acc-9"))
    found = MagicMock()
    found.scalar_one_or_none.return_value = existing_row
    session.execute = AsyncMock(return_value=found)

    store = PostgresLiveOrderStore(session)
    cancelled = await store.cancel_order("lo-cxpg")
    assert cancelled is not None and cancelled.status == "CANCELLED"
    assert existing_row.status == "CANCELLED"
    session.commit.assert_awaited()

    # Re-cancel (fila ya CANCELLED persistida) → devuelve CANCELLED sin transicionar.
    existing_row.status = "CANCELLED"
    again = await store.cancel_order("lo-cxpg")
    assert again is not None and again.status == "CANCELLED"


def test_postgres_cancel_and_list_open_are_exported_on_protocol() -> None:
    """Duck-typing parity: InMemory y Postgres exponen la misma superficie."""
    for store_type in (InMemoryLiveOrderStore, PostgresLiveOrderStore):
        assert hasattr(store_type, "list_open_orders")
        assert hasattr(store_type, "cancel_order")


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
