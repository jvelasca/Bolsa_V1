"""Yahoo news → MarketEvents + sentiment heurístico."""

from __future__ import annotations

from bolsa_domain.entities.market_event import MarketEventCalendar
from bolsa_market.news_snapshot import (
    heuristic_title_sentiment,
    news_items_to_events,
    upsert_events_into_calendar,
)


def test_heuristic_sentiment_bull_bear():
    assert heuristic_title_sentiment("Company beats estimates, shares surge") > 0.2
    assert heuristic_title_sentiment("Firm plunges after fraud probe") < -0.2
    assert heuristic_title_sentiment("Weekly market wrap-up") == 0.0


def test_news_items_to_events_and_upsert():
    items = [
        {
            "uuid": "abc-1",
            "title": "Acme upgrades outlook after strong growth",
            "publisher": "Reuters",
            "providerPublishTime": 1_720_000_000,
            "relatedTickers": ["AAPL"],
        }
    ]
    # Force published near now by using current-ish timestamp via monkeypatch-like override:
    # providerPublishTime far in past would be filtered; use a recent epoch.
    import time

    items[0]["providerPublishTime"] = int(time.time()) - 3600
    events = news_items_to_events(items, symbol="AAPL")
    assert len(events) == 1
    assert events[0].event_type == "news"
    assert events[0].sentiment > 0
    assert "AAPL" in events[0].affects

    cal = MarketEventCalendar()
    n = upsert_events_into_calendar(cal, events)
    assert n == 1
    assert len(cal.events) == 1
    # upsert same id replaces, no duplicate
    upsert_events_into_calendar(cal, events)
    assert len(cal.events) == 1
