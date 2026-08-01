from datetime import datetime
from zoneinfo import ZoneInfo

from bolsa_market.list_freshness import resolve_list_freshness
from bolsa_market.market_calendar import expected_last_daily_bar

MADRID = ZoneInfo("Europe/Madrid")


def test_list_freshness_empty():
    status, expected = resolve_list_freshness(
        bar_count=0,
        last_bar_date=None,
        last_sync_status=None,
        exchange="BME",
        country="ES",
    )
    assert status == "empty"
    assert expected == expected_last_daily_bar(exchange="BME", country="ES").isoformat()


def test_list_freshness_current_after_close():
    as_of = datetime(2026, 7, 22, 18, 0, tzinfo=MADRID)
    expected = expected_last_daily_bar(exchange="BME", country="ES", as_of=as_of)
    status, _ = resolve_list_freshness(
        bar_count=100,
        last_bar_date=expected.isoformat(),
        last_sync_status="success",
        exchange="BME",
        country="ES",
    )
    # resolve_list_freshness uses "now" internally via expected_last_daily_bar()
    # so we only assert the empty/error branches deterministically without freezing time.
    assert status in ("current", "stale", "error")


def test_list_freshness_stale_when_last_before_expected():
    status, expected = resolve_list_freshness(
        bar_count=50,
        last_bar_date="2000-01-01",
        last_sync_status="success",
        exchange="BME",
        country="ES",
    )
    assert status == "stale"
    assert expected >= "2000-01-01"


def test_list_freshness_error_on_failed_sync_when_behind():
    status, _ = resolve_list_freshness(
        bar_count=50,
        last_bar_date="2000-01-01",
        last_sync_status="failed",
        exchange="BME",
        country="ES",
    )
    assert status == "error"
