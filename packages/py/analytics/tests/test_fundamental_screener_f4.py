"""F4 — Screener FA evaluate + assemble."""

from __future__ import annotations

from bolsa_analytics.signals.fundamental_gate import build_fundamental_gate
from bolsa_analytics.signals.fundamental_screener import (
    FUNDAMENTAL_SCREENER_VERSION,
    assemble_screener_result,
    evaluate_fundamental_candidate,
    week_key_utc,
)


def _good_fund():
    return {
        "marketCap": 5e10,
        "trailingPe": 12.0,
        "sector": "Technology",
        "roe": 0.18,
        "operatingMargin": 0.14,
        "debtToEquity": 0.4,
        "currentRatio": 1.5,
        "fcfYield": 0.04,
        "altmanZ": 3.0,
        "piotroski": 8,
        "fetchedAt": "2026-07-29T12:00:00Z",
        "sourceVersion": "yahoo_quote_summary_v3",
    }


def test_week_key_format():
    key = week_key_utc()
    assert key.startswith("20")
    assert "-W" in key


def test_evaluate_pass_and_reject():
    gate = build_fundamental_gate(max_trailing_pe=20, min_roe=0.1, min_piotroski=6)
    assert gate is not None
    hit, skip = evaluate_fundamental_candidate(
        instrument_id="a",
        symbol="GOOD",
        name="Good Co",
        fundamentals=_good_fund(),
        gate=gate,
    )
    assert hit is not None and skip is None
    assert hit["symbol"] == "GOOD"
    assert hit["scoreDisplay100"] is not None

    bad = dict(_good_fund(), trailingPe=40.0)
    hit2, skip2 = evaluate_fundamental_candidate(
        instrument_id="b",
        symbol="BAD",
        name=None,
        fundamentals=bad,
        gate=gate,
    )
    assert hit2 is None and skip2 is not None
    assert "filtro" in (skip2["reason"] or "").lower() or skip2["reason"]


def test_assemble_caps_hits():
    hits = [
        {"instrumentId": f"i{i}", "symbol": f"S{i}", "scoreDisplay100": 50 + i}
        for i in range(10)
    ]
    out = assemble_screener_result(
        hits=hits,
        skipped=[],
        scanned_count=10,
        refreshed_count=0,
        list_id="ibex35",
        persisted_list_id=None,
        max_results=3,
    )
    assert out["screenerVersion"] == FUNDAMENTAL_SCREENER_VERSION
    assert out["hitCount"] == 3
    assert len(out["hits"]) == 3
