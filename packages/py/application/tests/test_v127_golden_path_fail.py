"""GOLDEN-PATH-FAIL — geometría, riesgo, stale, recon, tesis (no HOLD automático)."""

from datetime import UTC, datetime, timedelta

from bolsa_analytics.cognitive.position_decision import build_position_decision
from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_analytics.cognitive.risk_signature import evaluate_risk_signature
from bolsa_application.reconciliation_opening_gate import (
    reconciliation_opening_veto_reason,
)
from bolsa_application.risk_engine import data_freshness_veto_reason


def test_fail_stop_wrong_side_blocks_without_override() -> None:
    sig = evaluate_risk_signature(
        {
            "decisionId": "dec-fail",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        signed_qty=10.0,
        signed_price=100.0,
        signed_stop=105.0,
        require_triggered_plan=True,
    )
    assert sig["allowed"] is False
    assert sig["blockReason"] == "stop_wrong_side"
    assert sig["overrideRequired"] is False


def test_fail_recon_drift_blocks_new_openings() -> None:
    assert (
        reconciliation_opening_veto_reason(portfolio_recon_status="drift")
        == "reconciliation:portfolio_drift"
    )


def test_fail_thesis_invalidated_is_review_not_hold() -> None:
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-fail",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 105.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-fail",
    )
    d = build_position_decision(
        pos,
        mark_price=102.0,
        thesis_invalid=True,
        portfolio_recon_status="clean",
    )
    assert d is not None
    assert d.action != "HOLD"
    assert d.action == "REVIEW"


def test_fail_excess_risk_blocks_without_override() -> None:
    sig = evaluate_risk_signature(
        {
            "decisionId": "dec-fail",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        signed_qty=20.0,
        signed_price=100.0,
        signed_stop=95.0,
        require_triggered_plan=True,
    )
    assert sig["allowed"] is False
    assert sig["overrideRequired"] is True
    assert sig["excess"] == "qty_above_plan"
    assert sig["blockReason"] == "override_missing"


def test_fail_excess_risk_allows_with_audited_override() -> None:
    sig = evaluate_risk_signature(
        {
            "decisionId": "dec-fail",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        signed_qty=20.0,
        signed_price=100.0,
        signed_stop=95.0,
        override_reason="acepto más riesgo",
        require_triggered_plan=True,
    )
    assert sig["allowed"] is True
    assert sig["overrideRequired"] is True
    assert sig["blockReason"] is None


def test_fail_stale_data_blocks_opening() -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    stale = (now - timedelta(days=6)).isoformat().replace("+00:00", "Z")
    reason = data_freshness_veto_reason(stale, now=now, require=True)
    assert reason is not None
    assert reason.startswith("data_freshness:stale:")


def test_fail_stale_stop_invalid() -> None:
    sig = evaluate_risk_signature(
        {
            "decisionId": "dec-fail",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        signed_qty=10.0,
        signed_price=100.0,
        signed_stop=0.0,
        require_triggered_plan=True,
    )
    assert sig["allowed"] is False
    assert sig["blockReason"] == "stop_invalid"
