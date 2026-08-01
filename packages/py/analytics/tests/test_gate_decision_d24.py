"""RFC-008 D2.4 — Policy Gate sobre DecisionPackage."""

from __future__ import annotations

from bolsa_analytics.cognitive import (
    CONSERVATIVE_POLICY,
    MODERATE_POLICY,
    ProposedTradeContext,
    gate_decision_package,
)
from bolsa_analytics.knowledge import TechnicalInputs, build_decision_package_ta


def _bullish_package():
    inputs = TechnicalInputs(
        rsi=68,
        adx=32,
        plus_di=28,
        minus_di=15,
        obv_slope=1.0,
        price_slope=1.0,
        atr_percentile=50,
        close=150,
        sma_20=145,
        sma_50=140,
    )
    package, _, _ = build_decision_package_ta("inst-aapl", inputs)
    assert package.action == "recommend_long"
    return package


def test_gate_pass_allows_execution():
    package = _bullish_package()
    trade = ProposedTradeContext(
        symbol="AAPL",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        risk_pct_of_account=0.4,
        reward_to_risk_ratio=2.5,
        has_stop_loss=True,
        hours_to_earnings=72,
    )
    gated = gate_decision_package(package, MODERATE_POLICY, trade)
    assert gated.execution_allowed is True
    assert gated.gate is not None and gated.gate.passed is True
    assert gated.memory.outcome == "accepted"
    assert gated.package.action == "recommend_long"  # intacta
    assert gated.package.execution_allowed is True
    assert gated.package.memory_ref == gated.memory.memory_id
    assert gated.package.compliance_check["passed"] is True


def test_gate_veto_earnings_keeps_recommendation():
    package = _bullish_package()
    trade = ProposedTradeContext(
        symbol="AAPL",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        risk_pct_of_account=0.3,
        reward_to_risk_ratio=3.0,
        has_stop_loss=True,
        hours_to_earnings=12,  # within conservative 48h
    )
    gated = gate_decision_package(package, CONSERVATIVE_POLICY, trade)
    assert gated.execution_allowed is False
    assert gated.gate is not None and gated.gate.passed is False
    assert gated.memory.outcome == "rejected"
    assert gated.memory.opportunity_intact is True
    assert gated.package.action == "recommend_long"  # Opportunity ≠ Permission
    assert "after_earnings_blackout_clears" in gated.memory.reevaluate_when


def test_wait_is_deferred_not_veto():
    inputs = TechnicalInputs(rsi=50, adx=15, plus_di=20, minus_di=19, close=100, sma_20=100, sma_50=100)
    package, _, _ = build_decision_package_ta("inst-flat", inputs)
    assert package.action == "wait"
    gated = gate_decision_package(
        package,
        MODERATE_POLICY,
        ProposedTradeContext(symbol="XYZ"),
    )
    assert gated.execution_allowed is False
    assert gated.gate is None
    assert gated.memory.outcome == "deferred"
    assert gated.package.compliance_check.get("skipped") is True
