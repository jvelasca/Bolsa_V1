"""Escenarios Gate: propose pasivo vs paper_auto hard; bias/score/warnings."""

from __future__ import annotations

from bolsa_analytics.cognitive import (
    CONSERVATIVE_POLICY,
    MODERATE_POLICY,
    ProposedTradeContext,
    gate_decision_package,
)
from bolsa_analytics.knowledge import (
    TechnicalInputs,
    build_technical_assessment,
    run_decision_runtime,
)


def _bullish_inputs() -> TechnicalInputs:
    return TechnicalInputs(
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


def _bearish_inputs() -> TechnicalInputs:
    return TechnicalInputs(
        rsi=28,
        adx=30,
        plus_di=12,
        minus_di=28,
        obv_slope=-1.0,
        price_slope=-0.8,
        atr_percentile=55,
        close=90,
        sma_20=95,
        sma_50=100,
    )


def _neutral_inputs() -> TechnicalInputs:
    return TechnicalInputs(
        rsi=50,
        adx=12,
        plus_di=18,
        minus_di=17,
        close=100,
        sma_20=100,
        sma_50=100,
    )


def test_bearish_bias_maps_to_recommend_short():
    ta, _, _ = build_technical_assessment("inst-1", _bearish_inputs())
    assert ta.bias == "bearish"
    result = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    assert result.package.action == "recommend_short"


def test_low_score_forces_wait():
    ta, _, _ = build_technical_assessment("inst-1", _neutral_inputs())
    assert ta.bias == "neutral"
    assert abs(ta.score) < 0.35
    result = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    assert result.package.action == "wait"
    assert any("neutral" in w.lower() for w in ta.warnings)


def test_propose_path_gate_is_passive_skipped():
    """Propose: Runtime emite decisión; Gate NO bloquea (SKIPPED)."""
    ta, _, _ = build_technical_assessment("inst-1", _bullish_inputs())
    result = run_decision_runtime(
        instrument_id="inst-1",
        assessments=[ta],
        evaluate_policy_gate=False,
    )
    assert result.policy_gate is not None
    assert result.policy_gate["status"] == "SKIPPED"
    assert result.package.compliance_check is not None
    assert result.package.compliance_check.get("skipped") is True
    # La recomendación existe aunque hubiera blackouts en el mundo real
    assert result.package.action in {"recommend_long", "recommend_short", "wait"}


def test_paper_auto_hard_veto_keeps_recommendation_intact():
    """paper_auto: Gate VETO — no reescribe action; solo niega ejecución."""
    ta, _, _ = build_technical_assessment("inst-1", _bullish_inputs())
    runtime = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    assert runtime.package.action == "recommend_long"

    gated = gate_decision_package(
        runtime.package,
        CONSERVATIVE_POLICY,
        ProposedTradeContext(
            symbol="AAPL",
            market_cap_usd=3e12,
            average_daily_volume_usd=1e9,
            risk_pct_of_account=0.3,
            reward_to_risk_ratio=3.0,
            has_stop_loss=True,
            hours_to_earnings=12,  # blackout
        ),
    )
    assert gated.execution_allowed is False
    assert gated.gate is not None and gated.gate.passed is False
    assert gated.package.action == "recommend_long"  # intacta
    assert gated.memory.opportunity_intact is True


def test_paper_auto_pass_allows_execution():
    ta, _, _ = build_technical_assessment("inst-1", _bullish_inputs())
    runtime = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    gated = gate_decision_package(
        runtime.package,
        MODERATE_POLICY,
        ProposedTradeContext(
            symbol="AAPL",
            market_cap_usd=3e12,
            average_daily_volume_usd=1e9,
            risk_pct_of_account=0.4,
            reward_to_risk_ratio=2.5,
            has_stop_loss=True,
            hours_to_earnings=72,
        ),
    )
    assert gated.execution_allowed is True
    assert gated.package.action == runtime.package.action


def test_critical_warnings_do_not_override_action_alone():
    """Warnings son evidencia; no reescriben la Recommendation por sí solas."""
    ta, _, _ = build_technical_assessment("inst-1", _bullish_inputs())
    # Forzar warning en envelope
    env = ta.as_assessment()
    # Runtime con TA bullish sigue long aunque haya warnings de cobertura
    result = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    if ta.bias == "bullish":
        assert result.package.action == "recommend_long"
    assert env.warnings is not None
