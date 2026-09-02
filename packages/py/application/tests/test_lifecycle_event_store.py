"""V1.86 — in-memory lifecycle store use-case (no PG)."""

from __future__ import annotations

import pytest

from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    InMemoryLifecycleEventStore,
)
from bolsa_domain.lifecycle import LifecycleEventInput, assert_equity_invariant


@pytest.mark.asyncio
async def test_append_open_t1_close_and_fresh_store_snapshot() -> None:
    store_a = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store_a)
    pos = "pos-mem-1"

    for kind in (
        "POSITION_OPENED",
        "T1_EXECUTED",
        "TRAIL_APPLIED",
        "EXIT_REQUIRED",
        "POSITION_CLOSED",
    ):
        result = await append.execute(
            LifecycleEventInput(kind=kind, position_id=pos)  # type: ignore[arg-type]
        )
        assert result.ok, result.error

    snap1 = await GetLifecycleSnapshot(store_a).execute(pos)
    assert snap1["stage"] == "closed"
    assert snap1["accounting"]["cash"] == 100_055
    assert snap1["accounting"]["totalEquity"] == 100_055

    # Simulate "new session" by reading via a second store handle sharing memory
    # (InMemory is process-local; for PG we use a fresh session — here we clone read path)
    store_b = InMemoryLifecycleEventStore()
    store_b._by_position = dict(store_a._by_position)
    store_b._by_event_id = dict(store_a._by_event_id)
    snap2 = await GetLifecycleSnapshot(store_b).execute(pos)
    assert snap2 == snap1


@pytest.mark.asyncio
async def test_event_id_conflict_via_use_case() -> None:
    store = InMemoryLifecycleEventStore()
    uc = AppendLifecycleEvent(store)
    pos = "pos-conflict"
    r1 = await uc.execute(
        LifecycleEventInput(kind="POSITION_OPENED", position_id=pos)  # type: ignore[arg-type]
    )
    assert r1.ok
    r2 = await uc.execute(
        LifecycleEventInput(
            kind="T1_EXECUTED",
            position_id=pos,
            event_id="evt-123",
            quantity=5,
            price=105,
        )
    )
    assert r2.ok
    conflict = await uc.execute(
        LifecycleEventInput(
            kind="T1_EXECUTED",
            position_id=pos,
            event_id="evt-123",
            quantity=8,
            price=130,
        )
    )
    assert not conflict.ok
    assert conflict.error is not None
    assert conflict.error.code == "event_id_conflict"
    assert len(conflict.log) == 2


@pytest.mark.asyncio
async def test_idempotent_replay() -> None:
    store = InMemoryLifecycleEventStore()
    uc = AppendLifecycleEvent(store)
    pos = "pos-idem"
    await uc.execute(
        LifecycleEventInput(kind="POSITION_OPENED", position_id=pos)  # type: ignore[arg-type]
    )
    body = LifecycleEventInput(
        kind="T1_EXECUTED", position_id=pos, event_id="evt-fixed"
    )
    first = await uc.execute(body)
    second = await uc.execute(body)
    assert first.ok and second.ok
    assert second.idempotent is True
    assert len(second.log) == 2
    if second.accounting:
        assert_equity_invariant(second.accounting)
