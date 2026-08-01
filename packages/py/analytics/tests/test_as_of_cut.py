"""Point-in-time cut for FA (DÍA D)."""

from __future__ import annotations

from bolsa_analytics.knowledge.as_of_cut import (
    LOOKAHEAD_BLOCKED_WARNING,
    normalize_as_of_date,
    resolve_fundamentals_pit,
    strip_lookahead_fundamentals,
)
from bolsa_analytics.knowledge.fundamental_card import build_fundamental_card


def test_normalize_as_of_rejects_garbage():
    assert normalize_as_of_date("") is None
    assert normalize_as_of_date("not-a-date") is None
    assert normalize_as_of_date("2024-06-15") == "2024-06-15"


def test_pit_live_when_no_as_of():
    assert resolve_fundamentals_pit(as_of=None, fetched_at="2026-07-29T12:00:00Z") == "live"


def test_pit_snapshot_when_fetched_on_or_before_d():
    assert (
        resolve_fundamentals_pit(as_of="2025-01-15", fetched_at="2025-01-10T08:00:00Z")
        == "snapshot"
    )
    assert (
        resolve_fundamentals_pit(as_of="2025-01-15", fetched_at="2025-01-15T23:00:00Z")
        == "snapshot"
    )


def test_pit_blocked_when_fetched_after_d():
    assert (
        resolve_fundamentals_pit(as_of="2024-06-01", fetched_at="2026-07-29T12:00:00Z")
        == "blocked"
    )


def test_pit_reconstructed_flag():
    assert (
        resolve_fundamentals_pit(
            as_of="2024-01-01",
            fetched_at="2026-07-29T12:00:00Z",
            reconstructed=True,
        )
        == "reconstructed"
    )


def test_strip_keeps_sector_only():
    out = strip_lookahead_fundamentals(
        {
            "roe": 0.2,
            "marketCap": 1e9,
            "sector": "Technology",
            "fetchedAt": "2026-07-29T12:00:00Z",
            "sourceVersion": "yahoo_quote_summary_v3",
        }
    )
    assert out is not None
    assert out.get("sector") == "Technology"
    assert "roe" not in out
    assert "marketCap" not in out


def test_card_blocked_nulls_scores():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="AAPL",
        fundamentals={
            "marketCap": 5e10,
            "trailingPe": 12.0,
            "roe": 0.22,
            "operatingMargin": 0.18,
            "debtToEquity": 0.4,
            "currentRatio": 1.8,
            "sector": "Technology",
            "fetchedAt": "2026-07-29T12:00:00Z",
            "sourceVersion": "yahoo_quote_summary_v3",
        },
        as_of="2024-01-01",
    )
    assert card["metadata"]["pointInTime"] == "blocked"
    assert card["metadata"]["asOfDate"] == "2024-01-01"
    assert card["scoreFund"] is None
    assert card["scoreDisplay100"] is None
    assert card["facts"]["roe"] is None
    assert card["facts"]["sector"] == "Technology"
    assert LOOKAHEAD_BLOCKED_WARNING in card["warnings"]
    assert card["metadata"]["confidence"] == "LOW"


def test_card_reconstructed_keeps_score():
    card = build_fundamental_card(
        instrument_id="inst-1",
        ticker="AAPL",
        fundamentals={
            "marketCap": 5e10,
            "trailingPe": 12.0,
            "forwardPe": 11.0,
            "roe": 0.22,
            "operatingMargin": 0.18,
            "revenueGrowth": 0.12,
            "debtToEquity": 0.4,
            "currentRatio": 1.8,
            "freeCashflow": 2e9,
            "fcfYield": 0.04,
            "altmanZ": 3.5,
            "fetchedAt": "2024-01-01T12:00:00Z",
            "sourceVersion": "yahoo_quote_summary_v3_asof_statements_v1",
            "asOfReconstructed": True,
            "asOfDate": "2024-01-01",
        },
        as_of="2024-01-01",
    )
    assert card["metadata"]["pointInTime"] == "reconstructed"
    assert card["scoreFund"] is not None
    assert any("reconstruida" in w for w in card["warnings"])
