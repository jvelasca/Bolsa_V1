"""OI-3 — Confirm ExecutionRecord: UNKNOWN ≠ ERROR ≠ rejected_by_gate."""

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
async def test_execute_exception_is_unknown_not_error_or_gate() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_BoomExecute())
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "unknown"
    assert "ledger timeout" in result["trade"]["reason"]
    assert result["intent"]["status"] == "unknown"
    rec = result["executionRecord"]
    assert rec["outcome"] == "unknown"
    assert rec["sendAttempted"] is True
    assert rec["outcome"] != "error"
    assert rec["outcome"] != "not_executed"


@pytest.mark.asyncio
async def test_gate_reject_is_not_executed() -> None:
    fake = _OkExecute()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=20.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["executionRecord"]["outcome"] == "not_executed"
    assert result["executionRecord"]["sendAttempted"] is False
    assert result["executionRecord"]["reason"] == "risk_signature"


@pytest.mark.asyncio
async def test_fill_ok_record_is_executed() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_OkExecute())
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "executed"
    assert result["executionRecord"]["outcome"] == "executed"
    assert result["executionRecord"]["transactionId"] == "tx-ok"
    assert result["executionRecord"]["sendAttempted"] is True
