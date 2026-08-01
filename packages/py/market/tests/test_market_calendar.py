from datetime import datetime
from zoneinfo import ZoneInfo

from bolsa_market.market_calendar import expected_last_daily_bar, resolve_exchange_timezone


def test_resolve_exchange_timezone_bme() -> None:
    tz = resolve_exchange_timezone("BME", "ES")
    assert str(tz) == "Europe/Madrid"


def test_expected_last_daily_bar_weekend() -> None:
    saturday = datetime(2026, 6, 27, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    expected = expected_last_daily_bar(exchange="BME", country="ES", as_of=saturday)
    assert expected.isoformat() == "2026-06-26"


def test_expected_last_daily_bar_before_close() -> None:
    morning = datetime(2026, 6, 24, 10, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    expected = expected_last_daily_bar(exchange="BME", country="ES", as_of=morning)
    assert expected.isoformat() == "2026-06-23"


def test_expected_last_daily_bar_after_close() -> None:
    evening = datetime(2026, 6, 24, 18, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    expected = expected_last_daily_bar(exchange="BME", country="ES", as_of=evening)
    assert expected.isoformat() == "2026-06-24"
