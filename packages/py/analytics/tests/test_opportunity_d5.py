"""RFC-008 D5 — Score_FUND + Opportunity TA+FUND."""

from __future__ import annotations

from bolsa_analytics.knowledge import (
    FundamentalInputs,
    TechnicalInputs,
    build_fundamental_fact_set,
    build_opportunity_package,
    score_fund_from_facts,
    weight_rules_for_horizon,
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


def test_fundamental_facts_from_yahoo_shape():
    inp = FundamentalInputs.from_dict(
        {
            "marketCap": 2.5e12,
            "trailingPe": 28,
            "forwardPe": 24,
            "sector": "Technology",
            "fetchedAt": "2026-07-23T00:00:00Z",
        }
    )
    fs = build_fundamental_fact_set("inst-aapl", inp)
    assert fs.get("fund.valuation").value == "fair"
    assert fs.get("fund.size").value == "large"
    assert fs.get("fund.quality").value == "unknown"  # sin ROE aún
    score = score_fund_from_facts(fs)
    assert -1 <= score.score <= 1
    assert score.coverage > 0


def test_attractive_valuation_and_quality_boosts_fund_score():
    inp = FundamentalInputs(
        market_cap=50e9,
        trailing_pe=10,
        roe=0.22,
        roic=0.18,
        operating_margin=0.2,
        revenue_growth=0.15,
        eps_growth=0.18,
        altman_z=4.0,
        piotroski=8,
    )
    score = score_fund_from_facts(build_fundamental_fact_set("x", inp))
    assert score.score > 0.5
    assert score.distress is False


def test_altman_distress_blocks_long_opportunity():
    ta = _bullish_ta()
    fund = FundamentalInputs(
        market_cap=1e9,
        trailing_pe=8,
        altman_z=1.2,  # distress
        debt_to_equity=3.5,
    )
    opp = build_opportunity_package("inst-risk", ta, fund, horizon="swing")
    assert opp.score_fund is not None
    assert opp.score_fund.distress is True
    assert opp.package.action != "recommend_long"
    assert opp.combined_score < 0
    assert any(b["role"] == "fundamental" for b in opp.package.evidence_breakdown)


def test_weight_rules_by_horizon():
    assert weight_rules_for_horizon("intraday").w_fund < 0.1
    assert weight_rules_for_horizon("long_term").w_fund > 0.45
    swing = weight_rules_for_horizon("swing")
    assert abs(swing.w_ta + swing.w_fund + swing.w_macro + swing.w_news - 1.0) < 1e-9


def test_opportunity_swing_combines_ta_and_fund():
    ta = _bullish_ta()
    fund = FundamentalInputs(
        market_cap=80e9,
        trailing_pe=14,
        forward_pe=12,
        roe=0.18,
        revenue_growth=0.1,
        altman_z=3.5,
    )
    opp = build_opportunity_package("inst-good", ta, fund, horizon="swing")
    assert opp.package.action == "recommend_long"
    assert opp.weights.w_ta > opp.weights.w_fund
    assert opp.weights.w_macro == 0.0  # sin MarketState → renormaliza TA+FUND
    assert len(opp.package.evidence_breakdown) == 2
    assert opp.fact_set_fund is not None
