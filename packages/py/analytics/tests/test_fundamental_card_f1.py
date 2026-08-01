"""F1 — FundamentalCard DTO, confidence, scoreDisplay100, scoreVersion freeze."""

from __future__ import annotations

from bolsa_analytics.knowledge.fundamental_card import (
    FUND_CARD_SCHEMA_VERSION,
    build_fundamental_card,
    compute_data_confidence,
    fund_score_to_display_100,
    resolve_card_confidence,
)
from bolsa_analytics.knowledge.fundamental_facts import build_fundamental_fact_set
from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.score_fund import SCORE_FUND_VERSION, score_fund_from_facts


def _full_raw(**overrides):
    base = {
        "marketCap": 5e10,
        "trailingPe": 12.0,
        "forwardPe": 11.0,
        "sector": "Technology",
        "roe": 0.22,
        "operatingMargin": 0.18,
        "revenueGrowth": 0.12,
        "debtToEquity": 0.4,
        "currentRatio": 1.8,
        "freeCashflow": 2e9,
        "fcfYield": 0.04,
        "altmanZ": 3.5,
        "altmanMethod": "altman_z_classic_v1",
        "altmanEbitSource": "income_statement",
        "fetchedAt": "2026-07-29T12:00:00Z",
        "sourceVersion": "yahoo_quote_summary_v3",
    }
    base.update(overrides)
    return base


def test_fund_score_to_display_100():
    assert fund_score_to_display_100(-1.0) == 0
    assert fund_score_to_display_100(0.0) == 50
    assert fund_score_to_display_100(1.0) == 100
    assert fund_score_to_display_100(-0.5) == 25
    assert fund_score_to_display_100(0.8) == 90
    assert fund_score_to_display_100(None) is None


def test_confidence_high():
    assert compute_data_confidence(_full_raw()) == "HIGH"


def test_confidence_medium():
    raw = {
        "roe": 0.2,
        "debtToEquity": 0.5,
        "currentRatio": 1.5,
    }
    assert compute_data_confidence(raw) == "MEDIUM"


def test_confidence_low():
    assert compute_data_confidence({"roe": 0.1}) == "LOW"
    assert compute_data_confidence(None) == "LOW"


def test_resolve_stale_forces_low():
    assert (
        resolve_card_confidence(input_confidence="HIGH", pillar_coverage=1.0, is_stale=True)
        == "LOW"
    )


def test_fundamental_card_dto_shape():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="AAPL",
        fundamentals=_full_raw(),
    )
    assert card["schemaVersion"] == FUND_CARD_SCHEMA_VERSION
    assert card["ticker"] == "AAPL"
    assert "bias" not in card
    assert card["scoreFund"] is not None
    assert card["scoreDisplay100"] == fund_score_to_display_100(card["scoreFund"])
    assert card["pillars"] is not None
    assert set(card["pillars"]) == {"value", "quality", "growth", "risk"}
    # nulls explícitos
    assert "quickRatio" in card["facts"]
    assert card["derived"]["fcfYield"] == 0.04
    assert card["derived"]["piotroski"] is None
    assert card["derived"]["piotroskiMethod"] is None
    assert card["derived"]["roic"] is None
    assert card["derived"]["beneishM"] is None
    assert card["derived"]["dcfUpside"] is None
    assert card["derived"]["dcfScenarios"] is None
    assert card["derived"]["grahamNumber"] is None
    assert card["derived"]["beta"] is None
    assert card["derived"]["advUsd"] is None
    assert card["derived"]["wacc"] is None
    assert card["derived"]["waccMethod"] is None
    assert card["derived"]["capmRf"] is None
    assert card["derived"]["capmErp"] is None
    assert card["derived"]["altmanMethod"] == "altman_z_classic_v1"
    meta = card["metadata"]
    assert meta["scoreVersion"] == SCORE_FUND_VERSION == "fund_score_v1"
    assert meta["confidence"] == "HIGH"
    assert meta["isStale"] is False


def test_score_fund_v1_regression_healthy():
    """Si cambian pesos/tablas, este test falla → bump scoreVersion."""
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="TEST",
        fundamentals=_full_raw(),
    )
    assert card["metadata"]["scoreVersion"] == "fund_score_v1"
    assert card["scoreFund"] == 0.8725
    assert card["scoreDisplay100"] == 94
    assert card["pillars"] == {
        "value": 0.85,
        "quality": 0.9,
        "growth": 0.85,
        "risk": 0.9,
    }


def test_card_without_fundamentals():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="EMPTY",
        fundamentals=None,
    )
    assert card["scoreFund"] is None
    assert card["scoreDisplay100"] is None
    assert card["pillars"] is None
    assert card["metadata"]["confidence"] == "LOW"
    assert card["metadata"]["isStale"] is True
    assert all(v is None for v in card["facts"].values())


def test_card_to_chip():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="AAPL",
        fundamentals=_full_raw(),
    )
    from bolsa_analytics.knowledge.fundamental_card import card_to_chip

    chip = card_to_chip(card)
    assert chip["instrumentId"] == "inst-1"
    assert chip["ticker"] == "AAPL"
    assert chip["scoreDisplay100"] == card["scoreDisplay100"]
    assert chip["confidence"] == card["metadata"]["confidence"]
    assert "pillars" not in chip
    assert chip["altmanZ"] == 3.5


def test_score_fund_distress_hard_limit():
    inp = FundamentalInputs(
        market_cap=1e9,
        trailing_pe=80,
        debt_to_equity=5.0,
        current_ratio=0.4,
        altman_z=0.8,
    )
    fs = build_fundamental_fact_set("x", inp)
    result = score_fund_from_facts(fs)
    assert result.distress is True
    assert result.score <= -0.85
    assert result.score_version == "fund_score_v1"
    assert "risk" in result.components
    assert any("Distress" in w for w in result.warnings)


def test_score_fund_beneish_hard_limit():
    """Beneish M > −1.78 → distress aunque Altman sea sano."""
    inp = FundamentalInputs(
        market_cap=50e9,
        trailing_pe=14,
        roe=0.18,
        debt_to_equity=0.4,
        current_ratio=1.8,
        altman_z=3.5,
        beneish_m=-1.0,
    )
    fs = build_fundamental_fact_set("x", inp)
    result = score_fund_from_facts(fs)
    assert result.distress is True
    assert result.score <= -0.85
    assert any("Distress" in w for w in result.warnings)
    assert fs.get("fund.solvency") is not None
    assert fs.get("fund.solvency").value == "distress"


def test_score_fund_beneish_ok_no_distress():
    inp = FundamentalInputs(
        market_cap=50e9,
        trailing_pe=14,
        roe=0.18,
        debt_to_equity=0.4,
        current_ratio=1.8,
        altman_z=3.5,
        beneish_m=-2.5,
    )
    fs = build_fundamental_fact_set("x", inp)
    result = score_fund_from_facts(fs)
    assert result.distress is False
    assert result.score > -0.85


def test_score_fund_all_unknown():
    fs = build_fundamental_fact_set("x", FundamentalInputs())
    result = score_fund_from_facts(fs)
    assert result.score == 0.0
    assert result.coverage == 0.0
    assert result.confidence == "LOW"
