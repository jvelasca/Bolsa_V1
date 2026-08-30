"""V1.32 — tests exit risk signature."""

from bolsa_analytics.cognitive.exit_risk_signature import evaluate_exit_risk_signature


def test_allows_at_or_below_plan() -> None:
    v = evaluate_exit_risk_signature(planned_qty=5.0, signed_qty=5.0)
    assert v["allowed"] is True
    assert v["blockReason"] is None


def test_requires_override_when_exceeds() -> None:
    denied = evaluate_exit_risk_signature(planned_qty=3.0, signed_qty=5.0)
    assert denied["allowed"] is False
    assert denied["blockReason"] == "qty_exceeds_plan"

    ok = evaluate_exit_risk_signature(
        planned_qty=3.0,
        signed_qty=5.0,
        override_reason="más tamaño",
    )
    assert ok["allowed"] is True


def test_no_plan_allows() -> None:
    v = evaluate_exit_risk_signature(planned_qty=None, signed_qty=2.0)
    assert v["mode"] == "no_plan"
    assert v["allowed"] is True
