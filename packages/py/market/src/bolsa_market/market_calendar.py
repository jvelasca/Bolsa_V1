"""Calendario de mercado simplificado para frescura de barras diarias.

Fase P2: reglas por exchange/timezone. Sustituible por tabla MarketCalendar (ADR-005).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

POST_CLOSE_HOUR = 17
POST_CLOSE_MINUTE = 35

_EXCHANGE_TIMEZONES: dict[str, ZoneInfo] = {
    "BME": ZoneInfo("Europe/Madrid"),
    "MC": ZoneInfo("Europe/Madrid"),
    "MAD": ZoneInfo("Europe/Madrid"),
    "NYSE": ZoneInfo("America/New_York"),
    "NASDAQ": ZoneInfo("America/New_York"),
    "NMS": ZoneInfo("America/New_York"),
    "LSE": ZoneInfo("Europe/London"),
    "LON": ZoneInfo("Europe/London"),
}


def resolve_exchange_timezone(exchange: str, country: str = "ES") -> ZoneInfo:
    key = exchange.upper()
    if key in _EXCHANGE_TIMEZONES:
        return _EXCHANGE_TIMEZONES[key]
    if country.upper() in ("ES", "PT", "FR", "DE", "IT", "NL", "BE"):
        return ZoneInfo("Europe/Madrid")
    if country.upper() in ("US", "CA"):
        return ZoneInfo("America/New_York")
    if country.upper() in ("GB", "UK"):
        return ZoneInfo("Europe/London")
    return ZoneInfo("UTC")


def _previous_trading_day(d: date) -> date:
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def expected_last_daily_bar(
    *,
    exchange: str,
    country: str = "ES",
    as_of: datetime | None = None,
) -> date:
    """Última sesión diaria cuya vela debería existir en BD."""
    tz = resolve_exchange_timezone(exchange, country)
    now = (as_of or datetime.now(tz)).astimezone(tz)

    if now.weekday() >= 5:
        session = now.date()
        while session.weekday() >= 5:
            session = _previous_trading_day(session)
        return session

    session = now.date()
    post_close = (
        now.hour > POST_CLOSE_HOUR
        or (now.hour == POST_CLOSE_HOUR and now.minute >= POST_CLOSE_MINUTE)
    )
    if not post_close:
        return _previous_trading_day(session)
    return session
