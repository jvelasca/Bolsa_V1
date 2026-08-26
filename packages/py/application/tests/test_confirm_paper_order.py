"""OI-4 — Confirm PaperOrder: CREATED→FILLED; gate sin orden."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent


class _OkExecute:
    async def execute(self, **kwargs: Any) -> Any:
        return type("Trade", (), {"transaction_id": "tx-ok"})()


class _BoomExecute:
    async def execute(self, **kwargs: Any) -> Any:
        raise RuntimeError("ledger timeout")


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
async def test_fill_ok_paper_order_is_filled() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_OkExecute())
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    order = result["paperOrder"]
    assert order["status"] == "FILLED"
    assert order["venue"] == "PAPER"
    assert order["transactionId"] == "tx-ok"
    assert order["side"] == "buy"
    assert order["status"] != "CREATED"
    broker = result["paperBroker"]
    assert broker["venue"] == "PAPER"
    assert broker["adapter"] == "paper_broker"
    assert broker["fillStatus"] == "executed"
    adapter = result["brokerAdapter"]
    assert adapter["venue"] == "PAPER"
    assert adapter["adapter"] == "paper_broker"


@pytest.mark.asyncio
async def test_execute_exception_paper_order_marks_unknown() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_BoomExecute())
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "unknown"
    order = result["paperOrder"]
    assert order["status"] == "UNKNOWN"
    assert order["venue"] == "PAPER"
    assert order["transactionId"] is None
    assert order["status"] != "FILLED"
    broker = result["paperBroker"]
    assert broker["fillStatus"] == "unknown"
    assert broker["venue"] == "PAPER"


@pytest.mark.asyncio
async def test_gate_reject_has_no_paper_order() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_OkExecute())
    result = await uc.execute(
        recommendation_raw=_raw(qty=20.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert "paperOrder" not in result
    assert "paperBroker" not in result
    assert "brokerAdapter" not in result
