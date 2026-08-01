"""RFC-008 D6 — Macro + WeightRules + Market State."""

from __future__ import annotations

from bolsa_analytics.cognitive import (
    MacroInputs,
    build_macro_fact_set,
    build_market_state,
    resolve_weight_rules,
    score_macro_from_facts,
    validate_context,
    weight_rules_for_horizon,
)
from bolsa_analytics.knowledge import (
    FundamentalInputs,
    TechnicalInputs,
    build_opportunity_package,
)


def _bullish_ta() -> TechnicalInputs:
    return TechnicalInputs(
        rsi=65,
        adx=30,
        plus_di=28,
        minus_di=14,
        obv_slope=1.0,
        price_slope=1.0,
        close=120,
        sma_20=115,
        sma_50=110,
        atr_percentile=40,
    )


def test_macro_facts_risk_on():
    inp = MacroInputs(
        vix=14,
        vix_percentile=30,
        yield_curve_10y2y_bps=90,
        credit_spread_oas_bps=280,
        breadth_pct_above_ma50=72,
    )
    fs = build_macro_fact_set(inp)
    assert fs.get("macro.volatility_regime").value == "calm"
    assert fs.get("macro.risk_appetite").value == "risk_on"
    score = score_macro_from_facts(fs)
    assert score.score > 0.2
    assert score.stress is False


def test_market_state_crisis_not_tradable():
    inp = MacroInputs(
        vix=42,
        vix_percentile=95,
        yield_curve_10y2y_bps=-25,
        credit_spread_oas_bps=720,
        breadth_pct_above_ma50=25,
    )
    state = build_market_state(inp)
    assert state.regime == "crisis"
    assert state.tradable is False
    assert state.tradability == "wait"
    assert any(e.evidence_kind == "market_regime" for e in state.evidence_bundle.evidences)


def test_weight_rules_crisis_vetoes_long():
    w = resolve_weight_rules("swing", "crisis")
    assert w.veto_new_long is True
    assert w.w_macro > w.w_fund
    assert w.size_hint < 0.5
    assert abs(w.w_ta + w.w_fund + w.w_macro + w.w_news - 1.0) < 1e-6


def test_weight_rules_horizon_compat():
    assert weight_rules_for_horizon("intraday").w_fund < 0.1
    assert weight_rules_for_horizon("long_term").w_fund > 0.45
    swing = weight_rules_for_horizon("swing")
    assert abs(swing.w_ta + swing.w_fund + swing.w_macro + swing.w_news - 1.0) < 1e-6


def test_context_validation_blocks_crisis_and_blackout():
    crisis = build_market_state(
        MacroInputs(vix=40, vix_percentile=92, credit_spread_oas_bps=650, breadth_pct_above_ma50=20)
    )
    assert validate_context(crisis).valid is False
    calm = build_market_state(
        MacroInputs(
            vix=15,
            vix_percentile=35,
            yield_curve_10y2y_bps=50,
            credit_spread_oas_bps=300,
            breadth_pct_above_ma50=60,
        )
    )
    assert validate_context(calm).valid is True
    assert validate_context(calm, high_impact_macro_active=True).valid is False


def test_opportunity_with_crisis_blocks_long():
    ta = _bullish_ta()
    fund = FundamentalInputs(
        market_cap=80e9,
        trailing_pe=14,
        roe=0.18,
        altman_z=3.5,
    )
    crisis = build_market_state(
        MacroInputs(vix=38, vix_percentile=93, credit_spread_oas_bps=680, breadth_pct_above_ma50=22)
    )
    opp = build_opportunity_package("inst-x", ta, fund, horizon="swing", market_state=crisis)
    assert opp.market_state is not None
    assert opp.score_macro is not None
    assert opp.package.action != "recommend_long"
    assert any(b["role"] == "macro" for b in opp.package.evidence_breakdown)


def test_opportunity_risk_on_keeps_long():
    ta = _bullish_ta()
    fund = FundamentalInputs(
        market_cap=80e9,
        trailing_pe=14,
        forward_pe=12,
        roe=0.18,
        revenue_growth=0.1,
        altman_z=3.5,
    )
    risk_on = build_market_state(
        MacroInputs(
            vix=13,
            vix_percentile=28,
            yield_curve_10y2y_bps=100,
            credit_spread_oas_bps=260,
            breadth_pct_above_ma50=70,
        )
    )
    opp = build_opportunity_package("inst-y", ta, fund, horizon="swing", market_state=risk_on)
    assert risk_on.regime == "risk_on"
    assert opp.package.action == "recommend_long"
    assert opp.weights.regime == "risk_on"
