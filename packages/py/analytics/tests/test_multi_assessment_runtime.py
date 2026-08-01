"""Assessments multi-motor + DecisionRuntime fusion v1.1."""

from __future__ import annotations

from bolsa_analytics.cognitive.edge_report import StatisticalSuiteResult, build_edge_report
from bolsa_analytics.cognitive.macro_inputs import MacroInputs
from bolsa_analytics.knowledge import (
    Assessment,
    FundamentalInputs,
    TechnicalInputs,
    build_evidence_assessment,
    build_fundamental_assessment,
    build_macro_assessment,
    build_technical_assessment,
    run_decision_runtime,
)


def _bullish_ta() -> TechnicalInputs:
    return TechnicalInputs(
        rsi=62,
        adx=28,
        plus_di=28,
        minus_di=12,
        obv_slope=1.0,
        price_slope=0.5,
        bb_width_pct=4.0,
        atr=1.2,
        atr_percentile=40,
        close=150,
        sma_20=148,
        sma_50=145,
    )


def _healthy_fund() -> FundamentalInputs:
    return FundamentalInputs(
        market_cap=5e10,
        trailing_pe=12,
        forward_pe=11,
        roe=0.22,
        operating_margin=0.18,
        revenue_growth=0.12,
        debt_to_equity=0.4,
        current_ratio=1.8,
        altman_z=3.5,
    )


def _distress_fund() -> FundamentalInputs:
    return FundamentalInputs(
        market_cap=1e9,
        trailing_pe=80,
        debt_to_equity=5.0,
        current_ratio=0.4,
        altman_z=0.8,
    )


def test_fundamental_assessment_no_action():
    fa, _, score = build_fundamental_assessment("inst-1", _healthy_fund())
    assert fa.assessment_type == "fundamental"
    assert not hasattr(fa, "action")
    assert fa.bias in {"bullish", "bearish", "neutral"}
    assert score.score == fa.score
    env = fa.as_assessment()
    assert isinstance(env, Assessment)
    assert env.assessment_type == "fundamental"


def test_macro_assessment_from_inputs():
    ma, _, score = build_macro_assessment(
        "MARKET",
        MacroInputs(vix=14, yield_curve_10y2y_bps=80, credit_spread_oas_bps=300, breadth_pct_above_ma50=62),
    )
    assert ma.assessment_type == "macro"
    assert ma.regime in {"risk_on", "neutral", "risk_off", "crisis", "uncertain"}
    assert score.score == ma.score


def test_evidence_assessment_from_edge_report():
    suite = StatisticalSuiteResult(
        trials_n=50,
        walk_forward_efficiency=0.7,
        monte_carlo_p_value=0.02,
        dsr=0.8,
        bootstrap_alpha_ci_lower=0.01,
        bootstrap_alpha_ci_upper=0.05,
        stress_survival_rate=0.8,
    )
    report = build_edge_report("sig-1", suite)
    ea = build_evidence_assessment("inst-1", report)
    assert ea.assessment_type == "evidence"
    assert ea.band == report.band
    assert ea.as_assessment().metadata["directional"] is False


def test_runtime_distress_blocks_long():
    ta, _, _ = build_technical_assessment("inst-1", _bullish_ta())
    fa, _, score = build_fundamental_assessment("inst-1", _distress_fund())
    assert score.distress is True
    result = run_decision_runtime(instrument_id="inst-1", assessments=[ta, fa])
    assert result.package.action != "recommend_long"
    assert result.combined_score <= 0


def test_runtime_evidence_does_not_vote_direction():
    ta, _, _ = build_technical_assessment("inst-1", _bullish_ta())
    suite = StatisticalSuiteResult(trials_n=0)
    report = build_edge_report("sig-weak", suite)
    ea = build_evidence_assessment("inst-1", report, auto_live_eligible=False)
    alone = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    with_ev = run_decision_runtime(instrument_id="inst-1", assessments=[ta, ea])
    # Misma acción direccional; evidence solo afecta confianza/warnings
    assert alone.package.action == with_ev.package.action
    assert any("luck" in w.lower() or "débil" in w.lower() or "edge" in w.lower() for w in ea.warnings) or ea.band == "luck"


def test_runtime_ta_only_still_works():
    ta, _, _ = build_technical_assessment("inst-1", _bullish_ta())
    result = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    assert result.weights is not None
    assert result.weights.rationale == "ta_only" or "ta" in result.weights.rationale.lower()
    if ta.bias == "bullish":
        assert result.package.action == "recommend_long"
