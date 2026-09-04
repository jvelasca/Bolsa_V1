"""V1.97 — T2 pair atomicity + crash mid-pair / replay (unit, in-memory)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    InMemoryLifecycleEventStore,
)
from bolsa_application.lifecycle_from_fill import append_lifecycle_from_confirm_fill
from bolsa_application.lifecycle_t2_bridge import (
    build_t2_triggered_input,
    needs_atomic_t2_pair,
)
from bolsa_domain.lifecycle import LifecycleEventInput


async def _seed_open_t1(store: InMemoryLifecycleEventStore, pos: str = "pos-t2-atom") -> None:
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id=pos, instrument_id="inst-a")]
        )
    )
    opened = await append_lifecycle_from_confirm_fill(
        append,
        action="recommend_long",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=10.0,
        price=100.0,
        tx_id="tx-o-atom",
        trade=trade,
        decision_id="dec-atom",
        trade_plan_dict={"id": "tp-atom", "symbol": "AAPL"},
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
        tx_id="tx-t1-atom",
        trade=trade,
        open_position_id=pos,
        filled_at="2026-09-02T11:30:00.000Z",
        reason_code="TARGET_1",
    )
    assert t1["status"] == "applied"


@pytest.mark.asyncio
async def test_t2_pair_happy_path_one_trigger_one_execute() -> None:
    store = InMemoryLifecycleEventStore()
    await _seed_open_t1(store)
    append = AppendLifecycleEvent(store)
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-t2-atom", instrument_id="inst-a")]
        )
    )
    t2 = await append_lifecycle_from_confirm_fill(
        append,
        action="reduce",
        account_id="acc-1",
        instrument_id="inst-a",
        quantity=3.0,
        price=110.0,
        tx_id="tx-t2-atom",
        trade=trade,
        open_position_id="pos-t2-atom",
        filled_at="2026-09-02T12:45:00.000Z",
        reason_code="TARGET_2",
    )
    assert t2["status"] == "applied"
    snap = await GetLifecycleSnapshot(store).execute("pos-t2-atom")
    kinds = [e["kind"] for e in snap["events"]]
    assert kinds.count("T2_TRIGGERED") == 1
    assert kinds.count("T2_EXECUTED") == 1
    assert kinds == [
        "POSITION_OPENED",
        "T1_EXECUTED",
        "T2_TRIGGERED",
        "T2_EXECUTED",
    ]


@pytest.mark.asyncio
async def test_crash_mid_pair_rolls_back_then_retry_exactly_once() -> None:
    """V1.97 crash mid T2 pair · **V1.99 Golden 7** (exactly-once after retry)."""
    boom = {"n": 0}

    async def _crash_after_trigger(index: int, _event: object) -> None:
        if index == 0:
            boom["n"] += 1
            if boom["n"] == 1:
                raise RuntimeError("injected crash after T2_TRIGGERED")

    store = InMemoryLifecycleEventStore()
    await _seed_open_t1(store, pos="pos-crash")
    # Arm inject only for the T2 pair (index 0 = T2_TRIGGERED inside append_many).
    store.on_after_append_index = _crash_after_trigger
    append = AppendLifecycleEvent(store)

    execute = LifecycleEventInput(
        kind="T2_EXECUTED",
        at="2026-09-02T12:45:00.000Z",
        event_id="tx-t2-crash",
        position_id="pos-crash",
        account_id="acc-1",
        instrument_id="inst-a",
        decision_id="dec-atom",
        trade_plan_id="tp-atom",
        symbol="AAPL",
        fill_id="tx-t2-crash",
        quantity=3.0,
        price=110.0,
        fees=0,
        venue="PAPER",
        reason="TARGET_2",
    )
    with pytest.raises(RuntimeError, match="injected crash"):
        await append.execute(execute)

    snap_mid = await GetLifecycleSnapshot(store).execute("pos-crash")
    kinds_mid = [e["kind"] for e in snap_mid["events"]]
    assert "T2_TRIGGERED" not in kinds_mid
    assert "T2_EXECUTED" not in kinds_mid
    assert kinds_mid == ["POSITION_OPENED", "T1_EXECUTED"]

    # Clear inject for retry.
    store.on_after_append_index = None
    result = await append.execute(execute)
    assert result.ok, getattr(result.error, "message", None)
    snap = await GetLifecycleSnapshot(store).execute("pos-crash")
    kinds = [e["kind"] for e in snap["events"]]
    assert kinds.count("T2_TRIGGERED") == 1
    assert kinds.count("T2_EXECUTED") == 1

    # Idempotent replay.
    again = await append.execute(execute)
    assert again.ok
    assert again.idempotent is True
    snap2 = await GetLifecycleSnapshot(store).execute("pos-crash")
    assert [e["kind"] for e in snap2["events"]].count("T2_TRIGGERED") == 1
    assert [e["kind"] for e in snap2["events"]].count("T2_EXECUTED") == 1


@pytest.mark.asyncio
async def test_recovery_from_t2_ready_appends_execute_only() -> None:
    store = InMemoryLifecycleEventStore()
    await _seed_open_t1(store, pos="pos-ready")
    append = AppendLifecycleEvent(store)
    # Seed leftover T2_TRIGGERED (legacy V1.96 mid-failure shape).
    trigger = await append.execute(
        LifecycleEventInput(
            kind="T2_TRIGGERED",
            at="2026-09-02T12:44:59.999Z",
            event_id="tx-t2-ready:t2_trigger",
            position_id="pos-ready",
            account_id="acc-1",
            instrument_id="inst-a",
            decision_id="dec-atom",
            trade_plan_id="tp-atom",
            symbol="AAPL",
            reason="TARGET_2",
        )
    )
    assert trigger.ok
    assert trigger.stage == "t2_ready"

    execute = LifecycleEventInput(
        kind="T2_EXECUTED",
        at="2026-09-02T12:45:00.000Z",
        event_id="tx-t2-ready",
        position_id="pos-ready",
        account_id="acc-1",
        instrument_id="inst-a",
        decision_id="dec-atom",
        trade_plan_id="tp-atom",
        symbol="AAPL",
        fill_id="tx-t2-ready",
        quantity=3.0,
        price=110.0,
        fees=0,
        venue="PAPER",
        reason="TARGET_2",
    )
    existing = await store.list_by_position("pos-ready")
    assert needs_atomic_t2_pair(existing, execute) is False

    result = await append.execute(execute)
    assert result.ok
    snap = await GetLifecycleSnapshot(store).execute("pos-ready")
    kinds = [e["kind"] for e in snap["events"]]
    assert kinds.count("T2_TRIGGERED") == 1
    assert kinds.count("T2_EXECUTED") == 1


@pytest.mark.asyncio
async def test_needs_atomic_t2_pair_from_trailing_v198() -> None:
    """V1.98: T2 after TRAIL_APPLIED still gets atomic trigger+execute."""
    store = InMemoryLifecycleEventStore()
    await _seed_open_t1(store, pos="pos-trail-t2")
    append = AppendLifecycleEvent(store)
    log = await store.list_by_position("pos-trail-t2")
    anchor = log[0]
    trail = await append.execute(
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            at="2026-09-02T12:00:00.000Z",
            event_id="evt-trail-pre-t2",
            position_id="pos-trail-t2",
            account_id=anchor.account_id,
            instrument_id=anchor.instrument_id,
            decision_id=anchor.decision_id,
            trade_plan_id=anchor.trade_plan_id,
            symbol=anchor.symbol,
            side=anchor.side,
            previous_stop=95,
            new_stop=98,
            reason="TRAIL",
        )
    )
    assert trail.ok, trail.error
    existing = await store.list_by_position("pos-trail-t2")
    execute = LifecycleEventInput(
        kind="T2_EXECUTED",
        at="2026-09-02T12:45:00.000Z",
        event_id="tx-t2-after-trail",
        position_id="pos-trail-t2",
        account_id=anchor.account_id,
        instrument_id=anchor.instrument_id,
        decision_id=anchor.decision_id,
        trade_plan_id=anchor.trade_plan_id,
        symbol=anchor.symbol,
        fill_id="tx-t2-after-trail",
        quantity=3.0,
        price=110.0,
        fees=0,
        venue="PAPER",
        reason="TARGET_2",
    )
    assert needs_atomic_t2_pair(existing, execute) is True
    result = await append.execute(execute)
    assert result.ok, result.error
    snap = await GetLifecycleSnapshot(store).execute("pos-trail-t2")
    kinds = [e["kind"] for e in snap["events"]]
    assert kinds.count("TRAIL_APPLIED") == 1
    assert kinds.count("T2_TRIGGERED") == 1
    assert kinds.count("T2_EXECUTED") == 1
    assert snap["stage"] == "t2_executed"


def test_build_t2_triggered_input_event_id_suffix() -> None:
    exe = LifecycleEventInput(
        kind="T2_EXECUTED",
        at="2026-09-02T12:45:00.000Z",
        event_id="tx-1",
        position_id="pos-1",
    )
    trig = build_t2_triggered_input(exe)
    assert trig.kind == "T2_TRIGGERED"
    assert trig.event_id == "tx-1:t2_trigger"
    assert trig.at == "2026-09-02T12:44:59.999Z"


def test_t2_trigger_at_before_accepts_offset_and_str_datetime() -> None:
    from bolsa_application.lifecycle_t2_bridge import t2_trigger_at_before

    assert (
        t2_trigger_at_before("2026-09-02T12:45:00.000+00:00")
        == "2026-09-02T12:44:59.999Z"
    )
    assert (
        t2_trigger_at_before("2026-09-02 12:45:00.000000+00:00")
        == "2026-09-02T12:44:59.999Z"
    )


@pytest.mark.asyncio
async def test_append_many_integrity_rolls_back_first() -> None:
    from bolsa_domain.lifecycle import AppendOk, append_validated_lifecycle_event

    store = InMemoryLifecycleEventStore()
    await _seed_open_t1(store, pos="pos-int")
    log = await store.list_by_position("pos-int")
    anchor = log[0]
    trigger = build_t2_triggered_input(
        LifecycleEventInput(
            kind="T2_EXECUTED",
            at="2026-09-02T12:45:00.000Z",
            event_id="tx-dup",
            position_id="pos-int",
            account_id=anchor.account_id,
            instrument_id=anchor.instrument_id,
            decision_id=anchor.decision_id,
            trade_plan_id=anchor.trade_plan_id,
            symbol=anchor.symbol,
            fill_id="tx-dup",
            quantity=3,
            price=110,
            fees=0,
            reason="TARGET_2",
        )
    )
    t_ok = append_validated_lifecycle_event(log, trigger)
    assert isinstance(t_ok, AppendOk)

    # Force second insert to fail by reusing trigger event_id.
    with pytest.raises(IntegrityError):
        await store.append_many([t_ok.event, t_ok.event])

    snap = await GetLifecycleSnapshot(store).execute("pos-int")
    assert [e["kind"] for e in snap["events"]] == ["POSITION_OPENED", "T1_EXECUTED"]
