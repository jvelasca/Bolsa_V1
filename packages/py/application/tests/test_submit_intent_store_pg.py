"""DEX-1 — SubmitIntentStore contract (InMemory + PG mapping stub)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from bolsa_analytics.cognitive.submit_intent import (
    mark_send_attempted,
    record_submit_intent,
)
from bolsa_application.broker_adapter import XtbBrokerAdapter
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.submit_intent_store import (
    InMemorySubmitIntentStore,
    PostgresSubmitIntentStore,
)
from bolsa_market.providers import XtbBridgeOrderResult


@pytest.mark.asyncio
async def test_inmemory_put_get_delete_roundtrip() -> None:
    store = InMemorySubmitIntentStore()
    intent = mark_send_attempted(
        record_submit_intent(
            decision_id="DEC-STORE-1",
            intent_id="INT-DEC-STORE-1",
            order_id="ORD-DEC-STORE-1",
            account_id="acc-1",
            venue="paper",
        )
    )
    await store.put(intent)
    got = await store.get("DEC-STORE-1")
    assert got is not None
    assert got.phase == "send_attempted"
    assert got.send_attempted_at is not None
    await store.delete("DEC-STORE-1")
    assert await store.get("DEC-STORE-1") is None


@pytest.mark.asyncio
async def test_postgres_store_put_commits_and_get_maps_row() -> None:
    """Contract without live DB: session stub + row mapping (DEX-1 DoD)."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty_result)

    store = PostgresSubmitIntentStore(session)
    intent = mark_send_attempted(
        record_submit_intent(
            decision_id="DEC-PG-1",
            intent_id="INT-DEC-PG-1",
            order_id="ORD-DEC-PG-1",
            account_id="acc-1",
            venue="live",
        )
    )
    await store.put(intent)
    session.add.assert_called_once()
    session.commit.assert_awaited()
    added = session.add.call_args.args[0]
    assert added.decision_id == "DEC-PG-1"
    assert added.phase == "send_attempted"
    assert added.venue == "live"
    assert added.send_attempted_at is not None

    row = MagicMock()
    row.decision_id = "DEC-PG-1"
    row.intent_id = "INT-DEC-PG-1"
    row.order_id = "ORD-DEC-PG-1"
    row.account_id = "acc-1"
    row.venue = "live"
    row.phase = "send_attempted"
    row.venue_order_id = None
    row.reason = "crash_before_venue_ack"
    row.send_attempted_at = intent.send_attempted_at
    found = MagicMock()
    found.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=found)
    got = await store.get("DEC-PG-1")
    assert got is not None
    assert got.phase == "send_attempted"
    assert got.venue == "live"
    assert got.decision_id == "DEC-PG-1"


@pytest.mark.asyncio
async def test_postgres_store_unique_violation_fail_closed() -> None:
    session = AsyncMock()
    session.commit = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("dup")))
    session.rollback = AsyncMock()
    session.add = MagicMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty)

    store = PostgresSubmitIntentStore(session)
    intent = record_submit_intent(
        decision_id="DEC-DUP",
        intent_id="INT-DEC-DUP",
        order_id="ORD-DEC-DUP",
        account_id="acc-1",
    )
    with pytest.raises(IntegrityError):
        await store.put(intent)
    session.rollback.assert_awaited()


class _RecordingStore(InMemorySubmitIntentStore):
    def __init__(self) -> None:
        super().__init__()
        self.phases: list[str] = []

    async def put(self, intent: Any) -> None:  # type: ignore[override]
        self.phases.append(intent.phase)
        await super().put(intent)


class _FakeXtb:
    def __init__(self) -> None:
        self.calls = 0
        self.phases_at_submit: list[str] = []

    async def submit_order(self, **kwargs: Any) -> XtbBridgeOrderResult:
        _ = kwargs
        self.calls += 1
        return XtbBridgeOrderResult(status="submitted", venue_order_id="xtb-dex1")


@pytest.mark.asyncio
async def test_confirm_marks_send_attempted_before_adapter() -> None:
    """Confirm: put recorded → put send_attempted → adapter.submit."""
    store = _RecordingStore()
    xtb = _FakeXtb()
    adapter = XtbBrokerAdapter(client=xtb)
    uc = ConfirmRecommendationIntent(
        broker_adapter=adapter,
        submit_intent_store=store,
    )
    raw = {
        "decisionId": "DEC-DEX1-MARK",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 10.0,
        "suggestedPrice": 100.0,
        "tradePlan": {
            "decisionId": "DEC-DEX1-MARK",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 100.0,
            "structuralStop": 95.0,
            "riskAmount": 50.0,
        },
    }
    result = await uc.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    assert xtb.calls == 1
    assert store.phases[:2] == ["recorded", "send_attempted"]
    assert result["trade"]["status"] == "unknown"
    assert result["submitIntent"]["phase"] == "venue_bound"
    assert result["submitIntent"]["sendAttemptedAt"] is not None
