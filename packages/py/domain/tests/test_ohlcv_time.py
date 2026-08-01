from datetime import datetime, timezone

from bolsa_domain.ohlcv_time import is_cache_stale, parse_bar_timestamp
from bolsa_domain.value_objects.timeframe import TimeFrame


def test_parse_bar_timestamp_daily() -> None:
    moment = parse_bar_timestamp("2024-06-15")
    assert moment == datetime(2024, 6, 15, tzinfo=timezone.utc)


def test_parse_bar_timestamp_intraday() -> None:
    moment = parse_bar_timestamp("2024-06-15T14:30:00Z")
    assert moment.hour == 14
    assert moment.minute == 30


def test_is_cache_stale_when_empty() -> None:
    assert is_cache_stale(TimeFrame.H1, None) is True


def test_is_cache_stale_when_recent() -> None:
    recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assert is_cache_stale(TimeFrame.H1, recent) is False
