"""V1.90/V1.91 — unit tests for lifecycle outbox drain / repair / atomicity."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from bolsa_application.confirm.position_sync import PositionSyncCoordinator
from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    InMemoryLifecycleEventStore,
)
from bolsa_application.lifecycle_outbox import (
    InMemoryLifecycleOutboxStore,
    drain_lifecycle_outbox,
)


class _FailOnceAppend:
    """Wraps AppendLifecycleEvent; first execute fails, then delegates."""

    def __init__(self, inner: AppendLifecycleEvent) -> None:
        self._inner = inner
        self.calls = 0

    @property
    def store(self):
        return self._inner.store

    async def execute(self, input_event):
        self.calls += 1
        if self.calls == 1:
            from bolsa_application.lifecycle_event_store import AppendLifecycleResult
            from bolsa_domain.lifecycle import LifecycleAppendError

            return AppendLifecycleResult(
                ok=False,
                error=LifecycleAppendError(code="invalid_payload", message="injected"),
            )
        return await self._inner.execute(input_event)


def _clear_backoff(outbox: InMemoryLifecycleOutboxStore) -> None:
    """Unit-test helper: make pending rows immediately claimable."""
    for oid, row in list(outbox._by_id.items()):
        if row.status == "pending":
            outbox._by_id[oid] = replace(row, next_attempt_at=None)


@pytest.mark.asyncio
async def test_outbox_repair_after_append_failure() -> None:
    store = InMemoryLifecycleEventStore()
    real_append = AppendLifecycleEvent(store)
    outbox = InMemoryLifecycleOutboxStore()
    fail_append = _FailOnceAppend(real_append)

    await outbox.enqueue(
        position_id="pos-ob-1",
        account_id="acc-1",
        transaction_id="tx-ob-1",
        kind="POSITION_OPENED",
        payload={
            "action": "recommend_long",
            "instrument_id": "inst-a",
            "quantity": 10.0,
            "price": 100.0,
            "filled_at": "2026-09-02T10:00:00.000Z",
            "decision_id": "dec-1",
            "trade_plan_dict": {"id": "tp-1", "symbol": "AAPL"},
            "ledger_positions": [{"id": "pos-ob-1", "instrument_id": "inst-a"}],
        },
    )

    first = await drain_lifecycle_outbox(outbox, fail_append)
    assert first["errors"] == 1
    _clear_backoff(outbox)
    pending = await outbox.list_pending()
    assert len(pending) == 1

    second = await drain_lifecycle_outbox(outbox, fail_append)
    assert second["applied"] == 1
    assert await outbox.list_pending() == []

    snap = await GetLifecycleSnapshot(store).execute("pos-ob-1")
    assert snap["stage"] == "open"
    assert snap["events"][0]["eventId"] == "tx-ob-1"


@pytest.mark.asyncio
async def test_position_sync_enqueues_outbox_drain_post() -> None:
    """V1.91: sync only enqueues; drain is separate (post-COMMIT)."""
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    outbox = InMemoryLifecycleOutboxStore()

    class _Fill:
        async def persist(self, inp):
            return {"id": "pos-ps-1"}

    sync = PositionSyncCoordinator(
        position_from_fill=_Fill(),
        lifecycle_append=append,
        lifecycle_outbox=outbox,
    )
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-ps-1", instrument_id="inst-a")]
        ),
        transaction=SimpleNamespace(executed_at="2026-09-02T10:00:00.000Z"),
    )
    rec = SimpleNamespace(action="recommend_long", decision_id="dec-1")
    intent = SimpleNamespace(quantity=10.0, instrument_id="inst-a")
    result = await sync.sync_after_fill(
        rec=rec,
        intent=intent,
        price=100.0,
        account_id="acc-1",
        trade=trade,
        trade_plan_dict={"id": "tp-1", "symbol": "AAPL", "instrumentId": "inst-a"},
        tx_id="tx-ps-1",
    )
    assert result["status"] == "applied"
    assert result["lifecycle"]["status"] == "pending"
    assert len(await outbox.list_pending()) == 1

    drain = await drain_lifecycle_outbox(outbox, append)
    assert drain["applied"] == 1
    snap = await GetLifecycleSnapshot(store).execute("pos-ps-1")
    assert snap["stage"] == "open"
    assert await outbox.list_pending() == []


@pytest.mark.asyncio
async def test_enqueue_failure_propagates_no_swallow() -> None:
    """V1.91 P1-02: enqueue exception must not be swallowed by PositionSync."""

    class _BoomOutbox:
        async def enqueue(self, **kwargs):
            raise RuntimeError("enqueue_down")

    class _Fill:
        async def persist(self, inp):
            return {"id": "pos-boom"}

    sync = PositionSyncCoordinator(
        position_from_fill=_Fill(),
        lifecycle_outbox=_BoomOutbox(),
    )
    trade = SimpleNamespace(
        summary=SimpleNamespace(
            positions=[SimpleNamespace(id="pos-boom", instrument_id="inst-a")]
        ),
        transaction=SimpleNamespace(executed_at="2026-09-02T10:00:00.000Z"),
    )
    with pytest.raises(RuntimeError, match="enqueue_down"):
        await sync.sync_after_fill(
            rec=SimpleNamespace(action="recommend_long", decision_id="dec-1"),
            intent=SimpleNamespace(quantity=10.0, instrument_id="inst-a"),
            price=100.0,
            account_id="acc-1",
            trade=trade,
            trade_plan_dict={"id": "tp-1", "symbol": "AAPL"},
            tx_id="tx-boom",
        )


@pytest.mark.asyncio
async def test_requeue_dead_to_pending() -> None:
    outbox = InMemoryLifecycleOutboxStore()
    row = await outbox.enqueue(
        position_id="pos-rq",
        account_id="acc-1",
        transaction_id="tx-rq",
        kind="POSITION_OPENED",
        payload={"action": "recommend_long"},
    )
    await outbox.mark_attempt(row.id, error="temp", dead=True)
    assert outbox._by_id[row.id].status == "dead"
    revived = await outbox.requeue(row.id)
    assert revived is not None
    assert revived.status == "pending"
    assert revived.attempts == 0


@pytest.mark.asyncio
async def test_claim_batch_marks_processing() -> None:
    outbox = InMemoryLifecycleOutboxStore()
    await outbox.enqueue(
        position_id="pos-c",
        account_id="acc-1",
        transaction_id="tx-c",
        kind="POSITION_OPENED",
        payload={},
    )
    claimed = await outbox.claim_batch(limit=10)
    assert len(claimed) == 1
    assert claimed[0].status == "processing"
    assert await outbox.list_pending() == []


@pytest.mark.asyncio
async def test_claim_batch_fifo_one_per_position() -> None:
    """V1.92: same position → only oldest pending is claimable."""
    outbox = InMemoryLifecycleOutboxStore()
    first = await outbox.enqueue(
        position_id="pos-fifo",
        account_id="acc-1",
        transaction_id="tx-open",
        kind="POSITION_OPENED",
        payload={},
    )
    await outbox.enqueue(
        position_id="pos-fifo",
        account_id="acc-1",
        transaction_id="tx-t1",
        kind="T1_EXECUTED",
        payload={},
    )
    claimed = await outbox.claim_batch(limit=10)
    assert len(claimed) == 1
    assert claimed[0].id == first.id
    assert claimed[0].transaction_id == "tx-open"


@pytest.mark.asyncio
async def test_claim_batch_blocks_while_head_processing() -> None:
    outbox = InMemoryLifecycleOutboxStore()
    head = await outbox.enqueue(
        position_id="pos-proc",
        account_id="acc-1",
        transaction_id="tx-h",
        kind="POSITION_OPENED",
        payload={},
    )
    await outbox.enqueue(
        position_id="pos-proc",
        account_id="acc-1",
        transaction_id="tx-n",
        kind="T1_EXECUTED",
        payload={},
    )
    first = await outbox.claim_batch(limit=10)
    assert len(first) == 1 and first[0].id == head.id
    second = await outbox.claim_batch(limit=10)
    assert second == []


@pytest.mark.asyncio
async def test_claim_batch_next_after_applied() -> None:
    outbox = InMemoryLifecycleOutboxStore()
    head = await outbox.enqueue(
        position_id="pos-next",
        account_id="acc-1",
        transaction_id="tx-a",
        kind="POSITION_OPENED",
        payload={},
    )
    nxt = await outbox.enqueue(
        position_id="pos-next",
        account_id="acc-1",
        transaction_id="tx-b",
        kind="T1_EXECUTED",
        payload={},
    )
    claimed = await outbox.claim_batch(limit=10)
    assert claimed[0].id == head.id
    await outbox.mark_applied(head.id)
    claimed2 = await outbox.claim_batch(limit=10)
    assert len(claimed2) == 1
    assert claimed2[0].id == nxt.id


@pytest.mark.asyncio
async def test_claim_batch_dead_blocks_queue() -> None:
    outbox = InMemoryLifecycleOutboxStore()
    head = await outbox.enqueue(
        position_id="pos-dead",
        account_id="acc-1",
        transaction_id="tx-d1",
        kind="POSITION_OPENED",
        payload={},
    )
    await outbox.enqueue(
        position_id="pos-dead",
        account_id="acc-1",
        transaction_id="tx-d2",
        kind="POSITION_CLOSED",
        payload={},
    )
    await outbox.mark_attempt(head.id, error="boom", dead=True)
    assert await outbox.claim_batch(limit=10) == []


@pytest.mark.asyncio
async def test_claim_batch_distinct_positions_parallel() -> None:
    outbox = InMemoryLifecycleOutboxStore()
    a = await outbox.enqueue(
        position_id="pos-a",
        account_id="acc-1",
        transaction_id="tx-pa",
        kind="POSITION_OPENED",
        payload={},
    )
    b = await outbox.enqueue(
        position_id="pos-b",
        account_id="acc-1",
        transaction_id="tx-pb",
        kind="POSITION_OPENED",
        payload={},
    )
    claimed = await outbox.claim_batch(limit=10)
    assert {c.id for c in claimed} == {a.id, b.id}
