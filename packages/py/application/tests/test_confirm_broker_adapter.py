"""BrokerAdapter — Confirm default paper; mock LIVE; XTB sin ledger."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.broker_adapter import MockBrokerAdapter, XtbBrokerAdapter
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_market.providers import XtbBridgeOrderResult


class _OkExecute:
    async def execute(self, **kwargs: Any) -> Any:
        return type("Trade", (), {"transaction_id": "tx-ok"})()


def _triggered(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-1",
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


def _raw(*, qty: float = 10.0, price: float = 100.0, plan: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": qty,
        "suggestedPrice": price,
        "tradePlan": plan,
    }


@pytest.mark.asyncio
async def test_confirm_paper_adapter_stamps_broker_adapter() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_OkExecute())
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["paperOrder"]["status"] == "FILLED"
    assert result["paperBroker"]["adapter"] == "paper_broker"
    adapter = result["brokerAdapter"]
    assert adapter["venue"] == "PAPER"
    assert adapter["adapter"] == "paper_broker"
    assert adapter["fillStatus"] == "executed"


@pytest.mark.asyncio
async def test_confirm_mock_live_does_not_fill() -> None:
    uc = ConfirmRecommendationIntent(broker_adapter=MockBrokerAdapter())
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "skipped"
    assert result["trade"]["reason"] == "live_not_wired"
    assert "paperOrder" not in result
    assert "paperBroker" not in result
    adapter = result["brokerAdapter"]
    assert adapter["venue"] == "LIVE"
    assert adapter["adapter"] == "mock"
    assert adapter["fillStatus"] == "not_wired"
    assert adapter["fillStatus"] != "executed"


@pytest.mark.asyncio
async def test_gate_reject_has_no_broker_adapter() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_OkExecute())
    result = await uc.execute(
        recommendation_raw=_raw(qty=20.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert "brokerAdapter" not in result
    assert "paperOrder" not in result


class _FakeXtb:
    def __init__(self, result: XtbBridgeOrderResult) -> None:
        self.result = result

    async def submit_order(self, **kwargs: Any) -> XtbBridgeOrderResult:
        _ = kwargs
        return self.result


@pytest.mark.asyncio
async def test_confirm_xtb_rejected_skips_without_fill() -> None:
    adapter = XtbBrokerAdapter(
        client=_FakeXtb(XtbBridgeOrderResult(status="rejected", reason="live_orders_disabled"))
    )
    uc = ConfirmRecommendationIntent(broker_adapter=adapter)
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "skipped"
    assert result["trade"]["reason"] == "live_orders_disabled"
    assert "paperOrder" not in result
    adapter_receipt = result["brokerAdapter"]
    assert adapter_receipt["venue"] == "LIVE"
    assert adapter_receipt["adapter"] == "xtb"
    assert adapter_receipt["fillStatus"] == "rejected"
    assert adapter_receipt["fillStatus"] != "executed"


@pytest.mark.asyncio
async def test_confirm_xtb_submitted_is_unknown_not_executed() -> None:
    adapter = XtbBrokerAdapter(
        client=_FakeXtb(
            XtbBridgeOrderResult(status="submitted", venue_order_id="xtb-1")
        )
    )
    uc = ConfirmRecommendationIntent(broker_adapter=adapter)
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "unknown"
    assert result["trade"]["reason"] == "live_submitted_no_fill"
    assert result["trade"]["venueOrderId"] == "xtb-1"
    assert result["intent"]["status"] == "unknown"
    assert "paperOrder" not in result
    assert result["brokerAdapter"]["fillStatus"] == "submitted"
    assert result["brokerAdapter"]["fillStatus"] != "executed"


@pytest.mark.asyncio
async def test_confirm_xtb_filled_executes_with_transaction_id() -> None:
    adapter = XtbBrokerAdapter(
        client=_FakeXtb(
            XtbBridgeOrderResult(
                status="filled",
                reason="live_filled",
                venue_order_id="xtb-fill-1",
            )
        ),
        execute_trade=_OkExecute(),
    )
    uc = ConfirmRecommendationIntent(broker_adapter=adapter)
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "executed"
    assert result["trade"]["transactionId"] == "tx-ok"
    assert result["intent"]["status"] == "executed"
    assert result["brokerAdapter"]["venue"] == "LIVE"
    assert result["brokerAdapter"]["adapter"] == "xtb"
    assert result["brokerAdapter"]["fillStatus"] == "executed"
    assert "paperOrder" not in result
