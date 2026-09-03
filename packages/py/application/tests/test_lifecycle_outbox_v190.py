"""V1.90 — unit tests for lifecycle outbox drain / repair."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    InMemoryLifecycleEventStore,
)
from bolsa_application.lifecycle_outbox import (
    InMemoryLifecycleOutboxStore,
    drain_lifecycle_outbox,
)
from bolsa_application.confirm.position_sync import PositionSyncCoordinator


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


@pytest.mark.asyncio
async def test_outbox_repair_after_append_failure() -> None:
    store = InMemoryLifecycleEventStore()
    real_append = AppendLifecycleEvent(store)
    # Seed OPEN so later drain of a reduce isn't needed — test open path.
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
    pending = await outbox.list_pending()
    assert len(pending) == 1

    second = await drain_lifecycle_outbox(outbox, fail_append)
    assert second["applied"] == 1
    assert await outbox.list_pending() == []

    snap = await GetLifecycleSnapshot(store).execute("pos-ob-1")
    assert snap["stage"] == "open"
    assert snap["events"][0]["eventId"] == "tx-ob-1"


@pytest.mark.asyncio
async def test_position_sync_enqueues_outbox() -> None:
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
    assert result["lifecycle"]["status"] == "applied"
    snap = await GetLifecycleSnapshot(store).execute("pos-ps-1")
    assert snap["stage"] == "open"
    assert await outbox.list_pending() == []
