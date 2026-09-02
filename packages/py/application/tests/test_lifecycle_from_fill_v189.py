"""V1.89 — Confirm fill → lifecycle sidecar mapping (unit)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    InMemoryLifecycleEventStore,
)
from bolsa_application.lifecycle_from_fill import (
    append_lifecycle_from_confirm_fill,
    build_lifecycle_fill_mapping,
    map_confirm_fill_action,
)


def test_map_confirm_fill_action() -> None:
    assert map_confirm_fill_action("recommend_long") == "open"
    assert map_confirm_fill_action("recommend_short") == "open"
    assert map_confirm_fill_action("reduce") == "reduce"
    assert map_confirm_fill_action("exit_hint") == "exit"
    assert map_confirm_fill_action("protect") == "skip"


def test_build_mapping_open_uses_tx_as_fill_id() -> None:
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-ledger-1", instrument_id="inst-a")]
        )
    )
    mapping = build_lifecycle_fill_mapping(
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=2.0,
        price=101.5,
        tx_id="tx-open-1",
        trade=trade,
        trade_plan_dict={"id": "tp-1", "symbol": "AAPL"},
        decision_id="dec-1",
    )
    assert mapping is not None
    assert mapping.kind == "POSITION_OPENED"
    assert mapping.position_id == "pos-ledger-1"
    assert mapping.fill_id == "tx-open-1"
    assert mapping.event_id == "tx-open-1"
    assert mapping.quantity == 2.0
    assert mapping.price == 101.5


@pytest.mark.asyncio
async def test_append_open_then_exit_from_open_closes() -> None:
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-u-1", instrument_id="inst-a")]
        )
    )
    opened = await append_lifecycle_from_confirm_fill(
        append,
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-o-1",
        trade=trade,
        decision_id="dec-1",
        trade_plan_dict={"id": "tp-1", "symbol": "AAPL"},
        filled_at="2026-09-02T10:00:00.000Z",
    )
    assert opened["status"] == "applied"
    assert opened["stage"] == "open"

    closed = await append_lifecycle_from_confirm_fill(
        append,
        action="exit_hint",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=105.0,
        tx_id="tx-x-1",
        trade=trade,
        open_position_id="pos-u-1",
        filled_at="2026-09-02T15:00:00.000Z",
    )
    assert closed["status"] == "applied"
    assert closed["stage"] == "closed"

    snap = await GetLifecycleSnapshot(store).execute("pos-u-1")
    assert snap["stage"] == "closed"
    assert [e["kind"] for e in snap["events"]] == [
        "POSITION_OPENED",
        "POSITION_CLOSED",
    ]


@pytest.mark.asyncio
async def test_append_idempotent_on_same_tx() -> None:
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-idem", instrument_id="inst-a")]
        )
    )
    kwargs = dict(
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-same",
        trade=trade,
        filled_at="2026-09-02T10:00:00.000Z",
        decision_id="dec-1",
        trade_plan_dict={"id": "tp-1", "symbol": "AAPL"},
    )
    first = await append_lifecycle_from_confirm_fill(append, **kwargs)
    second = await append_lifecycle_from_confirm_fill(append, **kwargs)
    assert first["status"] == "applied"
    assert second["status"] == "applied"
    assert second["idempotent"] is True
