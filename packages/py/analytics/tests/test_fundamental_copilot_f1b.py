"""F1b — variables copiloto + heurística (sin Ollama)."""

from __future__ import annotations

from bolsa_analytics.knowledge.fundamental_card import build_fundamental_card
from bolsa_analytics.knowledge.fundamental_copilot import (
    build_fundamental_copilot_variables,
    heuristic_fundamental_explanation,
)


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


def test_copilot_variables_contain_frozen_fields():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="AAPL",
        fundamentals=_full_raw(),
    )
    vars_ = build_fundamental_copilot_variables(card)
    assert vars_["ticker"] == "AAPL"
    assert vars_["sector"] == "Technology"
    assert vars_["scoreVersion"] == "fund_score_v1"
    assert vars_["confidence"] in {"HIGH", "MEDIUM", "LOW"}
    assert vars_["score100"] != "—"
    # No placeholders vacíos críticos
    assert "{{" not in vars_["pe"]


def test_heuristic_has_three_paragraphs():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="AAPL",
        fundamentals=_full_raw(),
    )
    out = heuristic_fundamental_explanation(card)
    assert len(out["paragraphs"]) == 3
    assert "disclaimer" in out
    assert "Score_FUND" in out["paragraphs"][0]


def test_heuristic_low_confidence_mentions_low():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="X",
        fundamentals={"roe": 0.1, "fetchedAt": "2020-01-01T00:00:00Z", "sourceVersion": "yahoo_quote_summary_v3"},
    )
    out = heuristic_fundamental_explanation(card)
    assert "LOW" in out["paragraphs"][0]
