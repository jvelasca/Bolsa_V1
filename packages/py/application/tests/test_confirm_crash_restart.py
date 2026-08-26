"""OR-2 — Confirm crash/restart: UNKNOWN reconstruible, no re-POST (ADR-035)."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision
from bolsa_analytics.cognitive.paper_order import stable_order_id_from_decision
from bolsa_analytics.cognitive.submit_intent import (
    bind_venue_order,
    record_submit_intent,
)
from bolsa_application.broker_adapter import XtbBrokerAdapter
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.submit_intent_store import InMemorySubmitIntentStore
from bolsa_market.providers import XtbBridgeOrderResult


class _CountingAdapter:
    def __init__(self) -> None:
        self.submit_calls = 0

    async def submit(self, **kwargs: Any) -> Any:
        self.submit_calls += 1
        raise AssertionError("adapter.submit must not run on OR-2 recovery")


class _OkExecute:
    def __init__(self) -> None:
        self.execute_calls = 0
        self._by_key: dict[str, Any] = {}

    async def find_existing_by_idempotency(self, **kwargs: Any) -> Any | None:
        return self._by_key.get(str(kwargs.get("idempotency_key") or ""))

    async def execute(self, **kwargs: Any) -> Any:
        self.execute_calls += 1
        key = str(kwargs.get("idempotency_key") or "")
        trade = type("Trade", (), {"transaction_id": "tx-ok"})()
        self._by_key[key] = trade
        return trade


class _FakeXtb:
    def __init__(self, result: XtbBridgeOrderResult) -> None:
        self.result = result
        self.calls = 0

    async def submit_order(self, **kwargs: Any) -> XtbBridgeOrderResult:
        _ = kwargs
        self.calls += 1
        return self.result


def _triggered(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "DEC-OR2",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "quantity": 10.0,
        "entry": 100.0,
        "structuralStop": 95.0,
        "riskAmount": 50.0,
    }
    base.update(overrides)
    return base


def _raw(*, decision_id: str = "DEC-OR2", plan: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 10.0,
        "suggestedPrice": 100.0,
        "tradePlan": plan if plan is not None else _triggered(decisionId=decision_id),
    }


@pytest.mark.asyncio
async def test_or2_crash_after_record_reconstructs_unknown_without_submit() -> None:
    """Crash post-recorded (antes de venue) → UNKNOWN + mismos ids · 0 submit."""
    store = InMemorySubmitIntentStore()
    decision_id = "DEC-OR2-CRASH"
    recorded = record_submit_intent(
        decision_id=decision_id,
        intent_id=stable_intent_id_from_decision(decision_id),
        order_id=stable_order_id_from_decision(decision_id),
        account_id="acc-1",
    )
    await store.put(recorded)
    adapter = _CountingAdapter()
    uc = ConfirmRecommendationIntent(
        execute_trade=_OkExecute(),
        broker_adapter=adapter,  # type: ignore[arg-type]
        submit_intent_store=store,
    )
    result = await uc.execute(
        recommendation_raw=_raw(decision_id=decision_id),
        account_id="acc-1",
        execute=True,
    )
    assert adapter.submit_calls == 0
    assert result["trade"]["status"] == "unknown"
    assert result["trade"]["crashRecovery"] is True
    assert result["trade"]["reason"] == "crash_before_venue_ack"
    assert result["executionRecord"]["outcome"] == "unknown"
    assert result["executionRecord"]["sendAttempted"] is True
    assert result["intent"]["intentId"] == stable_intent_id_from_decision(decision_id)
    assert result["submitIntent"]["orderId"] == stable_order_id_from_decision(decision_id)
    assert result["paperOrder"]["status"] == "UNKNOWN"
    assert result["paperOrder"]["orderId"] == stable_order_id_from_decision(decision_id)


@pytest.mark.asyncio
async def test_or2_crash_after_venue_bind_preserves_mapping_without_repost() -> None:
    """Crash post-venue_order_id → UNKNOWN + mapeo · 0 re-POST."""
    store = InMemorySubmitIntentStore()
    decision_id = "DEC-OR2-VENUE"
    recorded = record_submit_intent(
        decision_id=decision_id,
        intent_id=stable_intent_id_from_decision(decision_id),
        order_id=stable_order_id_from_decision(decision_id),
        account_id="acc-1",
    )
    await store.put(bind_venue_order(recorded, venue_order_id="xtb-crash-1"))
    adapter = _CountingAdapter()
    uc = ConfirmRecommendationIntent(
        broker_adapter=adapter,  # type: ignore[arg-type]
        submit_intent_store=store,
    )
    result = await uc.execute(
        recommendation_raw=_raw(decision_id=decision_id),
        account_id="acc-1",
        execute=True,
    )
    assert adapter.submit_calls == 0
    assert result["trade"]["status"] == "unknown"
    assert result["trade"]["venueOrderId"] == "xtb-crash-1"
    assert result["trade"]["crashRecovery"] is True
    assert result["submitIntent"]["phase"] == "venue_bound"
    assert result["submitIntent"]["venueOrderId"] == "xtb-crash-1"
    assert "paperOrder" not in result


@pytest.mark.asyncio
async def test_or2_live_submitted_retry_single_submit() -> None:
    """Retry Confirm live submitted (mismo store) → 1 submit + mismo venue_order_id."""
    store = InMemorySubmitIntentStore()
    xtb = _FakeXtb(XtbBridgeOrderResult(status="submitted", venue_order_id="xtb-1"))
    adapter = XtbBrokerAdapter(client=xtb)
    uc = ConfirmRecommendationIntent(
        broker_adapter=adapter,
        submit_intent_store=store,
    )
    raw = _raw(decision_id="DEC-OR2-LIVE")
    first = await uc.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    second = await uc.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    assert xtb.calls == 1
    assert first["trade"]["status"] == "unknown"
    assert first["trade"]["venueOrderId"] == "xtb-1"
    assert second["trade"]["status"] == "unknown"
    assert second["trade"]["venueOrderId"] == "xtb-1"
    assert second["trade"]["crashRecovery"] is True
    assert second["executionRecord"]["outcome"] == "unknown"


@pytest.mark.asyncio
async def test_or2_local_fill_still_wins_over_in_flight() -> None:
    """OR-1 intacto: fill local gana al intento durable (replay executed)."""
    store = InMemorySubmitIntentStore()
    decision_id = "DEC-OR2-FILL"
    execute = _OkExecute()
    await execute.execute(idempotency_key=decision_id)
    recorded = record_submit_intent(
        decision_id=decision_id,
        intent_id=stable_intent_id_from_decision(decision_id),
        order_id=stable_order_id_from_decision(decision_id),
        account_id="acc-1",
    )
    await store.put(recorded)
    adapter = _CountingAdapter()
    uc = ConfirmRecommendationIntent(
        execute_trade=execute,
        broker_adapter=adapter,  # type: ignore[arg-type]
        submit_intent_store=store,
    )
    result = await uc.execute(
        recommendation_raw=_raw(decision_id=decision_id),
        account_id="acc-1",
        execute=True,
    )
    assert adapter.submit_calls == 0
    assert result["trade"]["status"] == "executed"
    assert result["trade"].get("idempotentReplay") is True
    assert result["executionRecord"]["outcome"] == "executed"
