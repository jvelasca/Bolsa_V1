"""F3 — Composite Investment Score."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_analytics.knowledge.composite_score import (
    COMPOSITE_SCORE_VERSION,
    build_composite_card,
    composite_to_chip,
    liquidity_score_from_mcap,
    regime_to_score,
)
from bolsa_analytics.knowledge.indice_operativo import compute_indice_operativo
from bolsa_analytics.knowledge.models import TechnicalInputs


def _fund(**overrides):
    base = {
        "marketCap": 5e10,
        "trailingPe": 14.0,
        "forwardPe": 13.0,
        "sector": "Technology",
        "roe": 0.2,
        "operatingMargin": 0.15,
        "revenueGrowth": 0.1,
        "debtToEquity": 0.5,
        "currentRatio": 1.6,
        "freeCashflow": 2e9,
        "fcfYield": 0.04,
        "altmanZ": 3.2,
        "fetchedAt": (datetime.now(UTC) - timedelta(days=1)).strftime(
            "%Y-%m-%dT12:00:00Z"
        ),
        "sourceVersion": "yahoo_quote_summary_v3",
    }
    base.update(overrides)
    return base


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


def test_liquidity_buckets():
    from bolsa_analytics.knowledge.composite_score import (
        liquidity_score_from_adv_usd,
        resolve_liquidity_score,
    )

    # mcap v1.1 — mega ≥500B · large ≥100B · mid_large ≥20B
    assert liquidity_score_from_mcap(2e12) == (0.8, "mcap_mega")
    assert liquidity_score_from_mcap(1.5e11) == (0.55, "mcap_large")
    assert liquidity_score_from_mcap(3e10) == (0.3, "mcap_mid_large")
    assert liquidity_score_from_mcap(None)[0] is None

    # ADV v1.1 — mega ≥1B · very_high ≥100M · high ≥20M (ACS ~51M ≠ AAPL)
    assert liquidity_score_from_adv_usd(1.7e10) == (0.85, "adv_mega")
    assert liquidity_score_from_adv_usd(2.9e8) == (0.65, "adv_very_high")
    assert liquidity_score_from_adv_usd(5.1e7) == (0.4, "adv_high")
    assert liquidity_score_from_adv_usd(8e6) == (0.15, "adv_medium")

    score, method = resolve_liquidity_score(adv_usd=5.1e7, market_cap=1e8)
    assert method == "adv_high"
    assert score == 0.4
    score2, method2 = resolve_liquidity_score(adv_usd=None, market_cap=2e12)
    assert method2 == "mcap_mega"
    assert score2 == 0.8


def test_regime_crisis_negative():
    assert regime_to_score("crisis") < regime_to_score("neutral")


def test_composite_with_ta_and_fund():
    card = build_composite_card(
        instrument_id="inst-1",
        ticker="ACME",
        fundamentals=_fund(),
        technical=_bullish_ta(),
        horizon="swing",
        regime="neutral",
    )
    assert card["schemaVersion"] == "composite_card_v1"
    assert card["metadata"]["scoreVersion"] == COMPOSITE_SCORE_VERSION
    assert card["metadata"]["paperDUnlocked"] is True
    assert card["combinedScore"] is not None
    assert card["scoreDisplay100"] is not None
    assert -1 <= card["combinedScore"] <= 1
    keys = {leg["key"] for leg in card["legs"]}
    assert keys == {
        "technical",
        "fundamental",
        "riskProfile",
        "liquidity",
        "marketRegime",
        "portfolioConstraints",
    }
    ta_leg = next(L for L in card["legs"] if L["key"] == "technical")
    assert ta_leg["status"] == "ok"
    port = next(L for L in card["legs"] if L["key"] == "portfolioConstraints")
    assert port["status"] == "not_evaluated"
    assert "check_opening" in (port.get("note") or "") or "Fit" in (port.get("note") or "")
    chip = composite_to_chip(card)
    assert chip["paperDUnlocked"] is True
    assert chip["ticker"] == "ACME"
    assert chip["technicalDisplay100"] is not None
    assert 0 <= chip["technicalDisplay100"] <= 100
    assert chip["indiceOperativo"] is not None
    assert chip["indiceOperativo"] == card["indiceOperativo"]
    assert 0 <= chip["indiceOperativo"] <= 100


def test_composite_fund_only_missing_ta():
    card = build_composite_card(
        instrument_id="inst-2",
        ticker="NO_TA",
        fundamentals=_fund(),
        technical=None,
        technical_score=None,
        horizon="long_term",
        regime="risk_on",
    )
    ta_leg = next(L for L in card["legs"] if L["key"] == "technical")
    assert ta_leg["status"] == "missing"
    assert card["combinedScore"] is not None
    # long_term pesa más FUND
    assert card["weights"]["fund"] > card["weights"]["ta"]


def test_crisis_veto_warning():
    card = build_composite_card(
        instrument_id="inst-3",
        ticker="X",
        fundamentals=_fund(),
        technical_score=0.2,
        technical_method="override",
        regime="crisis",
    )
    assert card["weights"]["vetoNewLong"] is True
    assert any("veto" in w.lower() for w in card["warnings"])


def test_chip_indice_operativo_applies_distress_floor():
    card = build_composite_card(
        instrument_id="inst-distress",
        ticker="DIST",
        fundamentals=_fund(
            trailingPe=80.0,
            debtToEquity=5.0,
            currentRatio=0.4,
            altmanZ=0.8,
        ),
        technical=_bullish_ta(),
        horizon="swing",
        regime="neutral",
    )
    chip = composite_to_chip(card)
    expected = compute_indice_operativo(
        card["scoreDisplay100"], distress=True
    )
    assert chip["indiceOperativo"] == expected
    assert expected is not None
    assert expected <= 40

