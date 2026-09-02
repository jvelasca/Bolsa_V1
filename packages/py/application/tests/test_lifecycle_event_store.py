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
    store_b._seq = dict(store_a._seq)
    store_b._account = dict(store_a._account)
    snap2 = await GetLifecycleSnapshot(store_b).execute(pos)
    assert snap2 == snap1
    assert [e["sequenceNo"] for e in snap1["events"]] == [1, 2, 3, 4, 5]


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


@pytest.mark.asyncio
async def test_inmemory_concurrent_t1_one_wins() -> None:
    import asyncio

    store = InMemoryLifecycleEventStore()
    uc = AppendLifecycleEvent(store)
    pos = "pos-race-mem"
    opened = await uc.execute(
        LifecycleEventInput(kind="POSITION_OPENED", position_id=pos)  # type: ignore[arg-type]
    )
    assert opened.ok

    async def _worker(fill_id: str, event_id: str):
        return await uc.execute(
            LifecycleEventInput(
                kind="T1_EXECUTED",
                position_id=pos,
                fill_id=fill_id,
                event_id=event_id,
                quantity=5,
                price=105,
            )
        )

    r1, r2 = await asyncio.gather(
        _worker("fill-race-a", "evt-race-a"),
        _worker("fill-race-b", "evt-race-b"),
    )
    oks = [r1.ok, r2.ok]
    assert oks.count(True) == 1
    assert oks.count(False) == 1
    loser = r1 if not r1.ok else r2
    assert loser.error is not None
    assert loser.error.code == "illegal_transition"
    snap = await GetLifecycleSnapshot(store).execute(pos)
    assert [e["sequenceNo"] for e in snap["events"]] == [1, 2]
    assert snap["events"][1]["kind"] == "T1_EXECUTED"


def test_classify_fill_id_not_event_id_conflict() -> None:
    from sqlalchemy.exc import IntegrityError

    from bolsa_application.lifecycle_event_store import (
        classify_lifecycle_integrity_error,
    )

    fill_exc = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate key lifecycle_events_fill_id_uidx"),
    )
    assert classify_lifecycle_integrity_error(fill_exc) == "duplicate_fill_id"
    event_exc = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate key lifecycle_events_event_id_key"),
    )
    assert classify_lifecycle_integrity_error(event_exc) == "event_id_conflict"
    seq_exc = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate key lifecycle_events_position_seq_uidx"),
    )
    assert classify_lifecycle_integrity_error(seq_exc) == "sequence_conflict"
