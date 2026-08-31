"""V1.27 — paridad PositionDecision / ExitPolicy."""

from bolsa_analytics.cognitive.exit_policy import (
    AGGRESSIVE_SWING_EXIT_POLICY,
    MODERATE_EXIT_POLICY,
    suggestion_from_exit_policy,
)
from bolsa_analytics.cognitive.position_decision import build_position_decision
from bolsa_analytics.cognitive.position_state import build_position_state_from_fill


def _pos():
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "AAPL",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 105.0,
            "target2": 110.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-28T10:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return pos


def test_legacy_t1_halves_without_policy() -> None:
    action, qty, _stop = suggestion_from_exit_policy("TARGET_1", 10.0, None)
    assert action == "reduce"
    assert qty == 5.0


def test_moderate_t1_reduces_30() -> None:
    action, qty, _stop = suggestion_from_exit_policy("TARGET_1", 10.0, MODERATE_EXIT_POLICY)
    assert action == "reduce"
    assert qty == 3.0


def test_aggressive_t1_holds() -> None:
    action, qty, _stop = suggestion_from_exit_policy(
        "TARGET_1", 10.0, AGGRESSIVE_SWING_EXIT_POLICY
    )
    assert action == "hold"
    assert qty is None


def test_decision_hold_next_t1() -> None:
    d = build_position_decision(
        _pos(),
        mark_price=102.0,
        template_id="moderate",
        portfolio_recon_status="clean",
    )
    assert d is not None
    assert d.action == "HOLD"
    assert d.attention == "NORMAL"
    assert d.next_event == "T1"
    assert d.protection == "ACTIVE"
    assert d.urgency == "LOW"
    assert 0 <= d.confidence <= 1
    assert 0 <= d.evidence_strength <= 1
    assert d.recon_health == "CLEAN"


def test_decision_t1_moderate_take_profit() -> None:
    d = build_position_decision(
        _pos(),
        mark_price=105.0,
        exit_policy=MODERATE_EXIT_POLICY,
        portfolio_recon_status="ok",
    )
    assert d is not None
    assert d.action == "TAKE_PROFIT"
    assert d.suggested_qty == 3.0
    assert d.attention == "ATTENTION"


def test_decision_thesis_review_not_hold() -> None:
    d = build_position_decision(
        _pos(),
        mark_price=102.0,
        thesis_invalid=True,
        portfolio_recon_status="clean",
    )
    assert d is not None
    assert d.action == "REVIEW"
    assert d.attention == "URGENT"


def test_decision_recon_drift_blocks() -> None:
    d = build_position_decision(
        _pos(),
        mark_price=102.0,
        portfolio_recon_status="drift",
    )
    assert d is not None
    assert d.recon_health == "CRITICAL"
    assert d.attention == "BLOCKED"
    assert d.action == "REVIEW"
    assert d.next_event == "RECONCILIATION"
    assert d.reason == "reconciliation:portfolio_drift"
