"""Calendario de MarketEvents compartido (proceso) — D4 / NewsAssessment."""

from __future__ import annotations

from bolsa_domain.entities.market_event import MarketEventCalendar

_SHARED_CALENDAR = MarketEventCalendar()


def get_shared_market_event_calendar() -> MarketEventCalendar:
    return _SHARED_CALENDAR
