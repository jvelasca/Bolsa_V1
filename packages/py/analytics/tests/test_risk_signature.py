"""P2 — firma de riesgo (qty ≤ plan · override · sin plan honest)."""

from bolsa_analytics.cognitive.risk_signature import evaluate_risk_signature


def _plan(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "decisionId": "dec-1",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "quantity": 10.0,
        "entry": 100.0,
        "structuralStop": 95.0,
        "riskAmount": 50.0,
        "initialRiskR": 5.0,
    }
    base.update(overrides)
    return base


def test_no_plan_when_missing() -> None:
    s = evaluate_risk_signature(None, signed_qty=10.0, signed_price=100.0)
    assert s["mode"] == "no_plan"
    assert s["allowed"] is True
    assert s["overrideRequired"] is False
    assert s["stop"] is None


def test_no_plan_fail_closed_when_required() -> None:
    s = evaluate_risk_signature(
        None,
        signed_qty=10.0,
        signed_price=100.0,
        require_triggered_plan=True,
    )
    assert s["mode"] == "no_plan"
    assert s["allowed"] is False
    assert s["blockReason"] == "no_tradeplan"


def test_no_plan_when_watch() -> None:
    s = evaluate_risk_signature(
        _plan(status="WATCH"), signed_qty=10.0, signed_price=100.0
    )
    assert s["mode"] == "no_plan"
    assert s["allowed"] is True


def test_allows_qty_at_or_below_plan() -> None:
    at = evaluate_risk_signature(_plan(), signed_qty=10.0, signed_price=100.0)
    assert at["mode"] == "plan"
    assert at["allowed"] is True
    assert at["maxQty"] == 10.0
    assert at["signedLossAtStop"] == 50.0
    assert at["signedR"] == 1.0

    below = evaluate_risk_signature(_plan(), signed_qty=5.0, signed_price=100.0)
    assert below["allowed"] is True
    assert below["overrideRequired"] is False
    assert below["signedLossAtStop"] == 25.0
    assert below["signedR"] == 0.5


def test_blocks_qty_above_plan_without_override() -> None:
    s = evaluate_risk_signature(_plan(), signed_qty=20.0, signed_price=100.0)
    assert s["allowed"] is False
    assert s["overrideRequired"] is True
    assert s["excess"] == "qty_above_plan"
    assert s["blockReason"] == "override_missing"


def test_allows_qty_above_plan_with_override() -> None:
    s = evaluate_risk_signature(
        _plan(),
        signed_qty=20.0,
        signed_price=100.0,
        override_reason="acepto más riesgo",
    )
    assert s["allowed"] is True
    assert s["overrideRequired"] is True
    assert s["blockReason"] is None


def test_rejects_blank_override() -> None:
    s = evaluate_risk_signature(
        _plan(), signed_qty=20.0, signed_price=100.0, override_reason="   "
    )
    assert s["allowed"] is False


def test_blocks_loss_above_risk_amount() -> None:
    s = evaluate_risk_signature(_plan(), signed_qty=10.0, signed_price=110.0)
    assert s["excess"] == "loss_above_plan"
    assert s["allowed"] is False
    assert s["signedLossAtStop"] == 150.0
