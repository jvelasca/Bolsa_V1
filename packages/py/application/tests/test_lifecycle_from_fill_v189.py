"""V1.89/V1.90 — Confirm fill → lifecycle sidecar mapping (unit)."""

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
    assert map_confirm_fill_action("recommend_short") == "reject_short"
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
        filled_at="2026-09-02T10:00:00.000Z",
    )
    assert mapping is not None
    assert mapping.kind == "POSITION_OPENED"
    assert mapping.position_id == "pos-ledger-1"
    assert mapping.fill_id == "tx-open-1"
    assert mapping.event_id == "tx-open-1"
    assert mapping.quantity == 2.0
    assert mapping.price == 101.5
    assert mapping.at == "2026-09-02T10:00:00.000Z"


def test_build_mapping_without_timestamp_returns_none() -> None:
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
    )
    assert mapping is None


def test_recommend_short_does_not_build_mapping() -> None:
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-s", instrument_id="inst-a")]
        )
    )
    mapping = build_lifecycle_fill_mapping(
        action="recommend_short",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=2.0,
        price=101.5,
        tx_id="tx-short-1",
        trade=trade,
        filled_at="2026-09-02T10:00:00.000Z",
    )
    assert mapping is None


def test_build_mapping_reduce_default_is_t1() -> None:
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-ledger-1", instrument_id="inst-a")]
        )
    )
    mapping = build_lifecycle_fill_mapping(
        action="reduce",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=5.0,
        price=10.5,
        tx_id="tx-t1",
        trade=trade,
        filled_at="2026-09-02T11:30:00.000Z",
        reason_code="TARGET_1",
    )
    assert mapping is not None
    assert mapping.kind == "T1_EXECUTED"


def test_build_mapping_reduce_target2_is_t2() -> None:
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-ledger-1", instrument_id="inst-a")]
        )
    )
    mapping = build_lifecycle_fill_mapping(
        action="reduce",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=3.0,
        price=11.0,
        tx_id="tx-t2",
        trade=trade,
        filled_at="2026-09-02T12:45:00.000Z",
        reason_code="TARGET_2",
    )
    assert mapping is not None
    assert mapping.kind == "T2_EXECUTED"
    assert mapping.reason == "TARGET_2"


@pytest.mark.asyncio
async def test_append_open_then_t1_t2_exit() -> None:
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-t2", instrument_id="inst-a")]
        )
    )
    opened = await append_lifecycle_from_confirm_fill(
        append,
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-o-t2",
        trade=trade,
        decision_id="dec-t2",
        trade_plan_dict={"id": "tp-t2", "symbol": "AAPL"},
        filled_at="2026-09-02T10:00:00.000Z",
    )
    assert opened["status"] == "applied"

    t1 = await append_lifecycle_from_confirm_fill(
        append,
        action="reduce",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=5.0,
        price=105.0,
        tx_id="tx-t1",
        trade=trade,
        open_position_id="pos-t2",
        filled_at="2026-09-02T11:30:00.000Z",
        reason_code="TARGET_1",
    )
    assert t1["status"] == "applied"
    assert t1["kind"] == "T1_EXECUTED"

    t2 = await append_lifecycle_from_confirm_fill(
        append,
        action="reduce",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=3.0,
        price=110.0,
        tx_id="tx-t2",
        trade=trade,
        open_position_id="pos-t2",
        filled_at="2026-09-02T12:45:00.000Z",
        reason_code="TARGET_2",
    )
    assert t2["status"] == "applied", t2
    assert t2["kind"] == "T2_EXECUTED"
    assert t2["stage"] == "t2_executed"

    closed = await append_lifecycle_from_confirm_fill(
        append,
        action="exit_hint",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=2.0,
        price=111.0,
        tx_id="tx-x-t2",
        trade=trade,
        open_position_id="pos-t2",
        filled_at="2026-09-02T15:00:00.000Z",
    )
    assert closed["status"] == "applied"
    assert closed["stage"] == "closed"

    snap = await GetLifecycleSnapshot(store).execute("pos-t2")
    assert [e["kind"] for e in snap["events"]] == [
        "POSITION_OPENED",
        "T1_EXECUTED",
        "T2_TRIGGERED",
        "T2_EXECUTED",
        "POSITION_CLOSED",
    ]


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


@pytest.mark.asyncio
async def test_append_idempotent_via_trade_executed_at_without_filled_at() -> None:
    """V1.90 — replay without filled_at uses trade.transaction.executed_at (stable)."""
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-ts", instrument_id="inst-a")]
        ),
        transaction=SimpleNamespace(executed_at="2026-09-02T10:00:00.000Z"),
    )
    kwargs = dict(
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-ts-same",
        trade=trade,
        decision_id="dec-1",
        trade_plan_dict={"id": "tp-1", "symbol": "AAPL"},
    )
    first = await append_lifecycle_from_confirm_fill(append, **kwargs)
    second = await append_lifecycle_from_confirm_fill(append, **kwargs)
    assert first["status"] == "applied"
    assert second["status"] == "applied"
    assert second["idempotent"] is True


@pytest.mark.asyncio
async def test_append_missing_timestamp_errors_not_conflicts() -> None:
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-miss", instrument_id="inst-a")]
        )
    )
    result = await append_lifecycle_from_confirm_fill(
        append,
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-miss",
        trade=trade,
        decision_id="dec-1",
        trade_plan_dict={"id": "tp-1", "symbol": "AAPL"},
    )
    assert result["status"] == "error"
    assert result["reason"] == "missing_execution_timestamp"
    snap = await GetLifecycleSnapshot(store).execute("pos-miss")
    assert snap["events"] == []


@pytest.mark.asyncio
async def test_append_recommend_short_skipped() -> None:
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-short", instrument_id="inst-a")]
        )
    )
    result = await append_lifecycle_from_confirm_fill(
        append,
        action="recommend_short",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-short",
        trade=trade,
        filled_at="2026-09-02T10:00:00.000Z",
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "recommend_short_rejected"


@pytest.mark.asyncio
async def test_append_idempotent_via_timestamp_lookup() -> None:
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-lookup", instrument_id="inst-a")]
        )
    )

    class _Lookup:
        async def executed_at_for_transaction(self, transaction_id: str) -> str | None:
            assert transaction_id == "tx-lookup"
            return "2026-09-02T11:00:00.000Z"

    kwargs = dict(
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-lookup",
        trade=trade,
        decision_id="dec-1",
        trade_plan_dict={"id": "tp-1", "symbol": "AAPL"},
        timestamp_lookup=_Lookup(),
    )
    first = await append_lifecycle_from_confirm_fill(append, **kwargs)
    second = await append_lifecycle_from_confirm_fill(append, **kwargs)
    assert first["status"] == "applied"
    assert second["idempotent"] is True


def test_confirm_t2_idempotency_key_distinct_from_t1() -> None:
    from bolsa_application.confirm_recommendation import confirm_leg_idempotency_key

    t1 = confirm_leg_idempotency_key("dec-1", "reduce", "sell", reason_code="TARGET_1")
    t2 = confirm_leg_idempotency_key("dec-1", "reduce", "sell", reason_code="TARGET_2")
    assert t1 != t2
    assert t1 == confirm_leg_idempotency_key("dec-1", "reduce", "sell")
