"""RFC-008 D2 — Knowledge Layer TA → Score_TA → DecisionPackage."""

from __future__ import annotations

from bolsa_analytics.knowledge import (
    TechnicalInputs,
    build_decision_package_ta,
    build_technical_fact_set,
    score_ta_from_facts,
)


def test_bullish_facts_and_long_recommendation():
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
    fact_set = build_technical_fact_set("inst-aapl", inputs)
    assert fact_set.artifact_type == "ART-FACT-SET"
    assert fact_set.get("trend.primary").value == "strong_bullish"
    assert fact_set.get("momentum").value == "strong"
    assert fact_set.get("exhaustion").value == "false"
    assert fact_set.get("participation").value == "institutional_bias"
    assert fact_set.get("structure.sma").value == "bullish_stack"

    score = score_ta_from_facts(fact_set)
    assert score.score > 0.35

    package, fs, sr = build_decision_package_ta("inst-aapl", inputs)
    assert package.action == "recommend_long"
    assert package.artifact_type == "ART-DECISION-PACKAGE"
    assert package.fact_set_ref == fs.fact_set_id
    assert 0 <= package.metrics.confidence <= 1
    assert package.metrics.conviction >= 0
    payload = package.to_dict()
    assert payload["evidenceBreakdown"][0]["role"] == "technical"
    assert sr.score == package.score_ta


def test_bearish_and_exhaustion_wait_or_short():
    inputs = TechnicalInputs(
        rsi=85,  # exhaustion
        adx=30,
        plus_di=12,
        minus_di=27,
        obv_slope=-1.0,
        price_slope=-1.0,
        close=90,
        sma_20=95,
        sma_50=100,
        atr_percentile=80,
    )
    fact_set = build_technical_fact_set("inst-xyz", inputs)
    assert fact_set.get("trend.primary").value == "strong_bearish"
    assert fact_set.get("exhaustion").value == "true"
    assert fact_set.get("volatility").value == "high"

    package, _, score = build_decision_package_ta("inst-xyz", inputs)
    assert score.exhaustion is True
    assert package.action in {"recommend_short", "wait"}
    assert package.score_ta < 0


def test_weak_trend_wait():
    inputs = TechnicalInputs(
        rsi=50,
        adx=18,
        plus_di=20,
        minus_di=19,
        close=100,
        sma_20=100,
        sma_50=100,
    )
    package, _, score = build_decision_package_ta("inst-flat", inputs)
    assert score.score == 0 or abs(score.score) < 0.35
    assert package.action == "wait"


def test_from_feature_map_aliases():
    inp = TechnicalInputs.from_feature_map(
        {
            "rsi_14_close": 55,
            "adx_14": 40,
            "di_plus": 30,
            "di_minus": 10,
            "sma_20_close": 10,
            "sma_50_close": 9,
            "close": 11,
        }
    )
    assert inp.rsi == 55
    assert inp.plus_di == 30
    fs = build_technical_fact_set("x", inp)
    assert fs.get("trend.primary").value == "strong_bullish"
