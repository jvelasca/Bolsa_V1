"""RFC-008 D4 — MarketEvent + decay + blackout context."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bolsa_analytics.cognitive import (
    MarketEventCalendar,
    build_market_event,
    event_decay_weight,
)


def test_decay_weight_inside_window():
    now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    ev = build_market_event(
        entity="MACRO",
        event_type="FOMC",
        sentiment=0.0,
        impact="high",
        horizon_days=1,
        source="Fed",
        credibility=0.95,
        valid_from=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        valid_to=(now + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
    )
    w = event_decay_weight(ev, now=now)
    assert 0 < w <= 0.95


def test_earnings_blackout_uses_valid_from_as_event_time():
    now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    earnings_at = now + timedelta(hours=24)
    cal = MarketEventCalendar()
    cal.add(
        build_market_event(
            entity="AAPL",
            event_type="earnings",
            sentiment=0.2,
            impact="very_high",
            horizon_days=3,
            source="Reuters",
            credibility=0.95,
            valid_from=earnings_at.isoformat().replace("+00:00", "Z"),
            valid_to=(earnings_at + timedelta(hours=24)).isoformat().replace("+00:00", "Z"),
            affects=["AAPL", "TECH"],
        )
    )
    cal.add(
        build_market_event(
            entity="MACRO",
            event_type="FOMC",
            sentiment=0.0,
            impact="high",
            horizon_days=1,
            source="Fed",
            credibility=1.0,
            valid_from=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            valid_to=(now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        )
    )
    ctx = cal.blackout_context("AAPL", now=now)
    assert ctx.hours_to_earnings is not None
    assert 20 < ctx.hours_to_earnings < 28
    assert ctx.fed_fomc_active is True
    assert ctx.high_impact_macro_active is True
    assert len(ctx.active_event_ids) >= 2


def test_expired_event_has_zero_weight():
    now = datetime(2026, 7, 23, tzinfo=timezone.utc)
    ev = build_market_event(
        entity="MSFT",
        event_type="CPI",
        sentiment=-0.1,
        impact="high",
        horizon_days=1,
        source="BLS",
        credibility=0.9,
        valid_from=(now - timedelta(days=5)).isoformat().replace("+00:00", "Z"),
        valid_to=(now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
    )
    assert event_decay_weight(ev, now=now) == 0.0
