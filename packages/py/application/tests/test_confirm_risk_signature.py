"""P2 — Confirm execute gate: qty/pérdida vs TradePlan (ADR-033 §6)."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("Trade", (), {"transaction_id": "tx-p2"})()


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
async def test_execute_qty_above_plan_rejected() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=20.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_signature"
    assert result["intent"]["status"] == "rejected_by_gate"
    assert fake.calls == []


@pytest.mark.asyncio
async def test_execute_qty_above_plan_with_override_fills() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=20.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
        risk_override_reason="acepto más riesgo",
    )
    assert result["trade"]["status"] == "executed"
    assert len(fake.calls) == 1
    assert fake.calls[0]["quantity"] == 20.0


@pytest.mark.asyncio
async def test_execute_qty_at_plan_fills_without_override() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=10.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "executed"
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_no_plan_opening_rejected_at_confirm() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=99.0, plan=None),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_signature"
    assert fake.calls == []


@pytest.mark.asyncio
async def test_authorize_only_skips_signature_gate() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=20.0, plan=_triggered()),
        account_id="acc-1",
        execute=False,
    )
    assert result["trade"] is None
    assert fake.calls == []


@pytest.mark.asyncio
async def test_execute_stop_wrong_side_rejected_even_with_override() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=10.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
        signed_stop=110.0,
        risk_override_reason="acepto el stop invertido",
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_signature"
    assert fake.calls == []


@pytest.mark.asyncio
async def test_execute_signed_stop_tighter_fills() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=10.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
        signed_stop=97.0,
    )
    assert result["trade"]["status"] == "executed"
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_execute_signed_stop_zero_rejected_no_substitute() -> None:
    fake = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    result = await uc.execute(
        recommendation_raw=_raw(qty=10.0, plan=_triggered()),
        account_id="acc-1",
        execute=True,
        signed_stop=0.0,
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_signature"
    assert fake.calls == []
