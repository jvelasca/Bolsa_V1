"""NewsAssessment + fusión w_news en DecisionRuntime."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_analytics.cognitive import (
    MODERATE_POLICY,
    MarketEventCalendar,
    build_market_event,
    evaluate_policy_gate,
)
from bolsa_analytics.knowledge import (
    TechnicalInputs,
    build_news_assessment,
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


def test_news_assessment_aggregates_sentiment():
    now = datetime.now(UTC)
    cal = MarketEventCalendar()
    cal.add(
        build_market_event(
            entity="AAPL",
            event_type="news",
            sentiment=0.8,
            impact="medium",
            horizon_days=2,
            source="test",
            credibility=0.9,
            valid_from=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            valid_to=(now + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        )
    )
    na = build_news_assessment("inst-1", calendar=cal, symbol="AAPL")
    assert na.event_count == 1
    assert na.score > 0.3
    assert na.bias == "bullish"


def test_runtime_fuses_news_weight():
    ta, _, _ = build_technical_assessment("inst-1", _bullish_ta())
    now = datetime.now(UTC)
    cal = MarketEventCalendar()
    cal.add(
        build_market_event(
            entity="INST-1",
            event_type="news",
            sentiment=-0.9,
            impact="high",
            horizon_days=1,
            source="test",
            credibility=1.0,
            valid_from=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            valid_to=(now + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            affects=["INST-1"],
        )
    )
    na = build_news_assessment("inst-1", calendar=cal, symbol="INST-1")
    alone = run_decision_runtime(instrument_id="inst-1", assessments=[ta])
    with_news = run_decision_runtime(instrument_id="inst-1", assessments=[ta, na])
    assert with_news.weights is not None
    assert with_news.weights.w_news > 0
    assert with_news.combined_score <= alone.combined_score


def test_daily_drawdown_gate_veto():
    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        symbol="AAPL",
        asset_class="equities",
        market_cap_usd=3e12,
        average_daily_volume_usd=5e9,
        risk_pct_of_account=0.5,
        reward_to_risk_ratio=2.0,
        leverage=1.0,
        has_stop_loss=True,
        open_positions_count=0,
        portfolio_concentration_pct=5.0,
        account_daily_drawdown_pct=5.0,
    )
    assert any(r.rule == "HardDailyDrawdown" and r.status == "FAILED" for r in gate.evaluated_rules)
