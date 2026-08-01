from bolsa_application.alerts import _is_triggered


def test_is_triggered_above() -> None:
    assert _is_triggered("above", 10.5, 10.0) is True
    assert _is_triggered("above", 9.9, 10.0) is False


def test_is_triggered_below() -> None:
    assert _is_triggered("below", 9.5, 10.0) is True
    assert _is_triggered("below", 10.1, 10.0) is False


def test_post_ibex_close_window_weekday_evening() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from bolsa_api.background.daily_alert_evaluator import _is_post_ibex_close_window

    madrid = ZoneInfo("Europe/Madrid")
    assert _is_post_ibex_close_window(datetime(2026, 6, 30, 18, 0, tzinfo=madrid)) is True
    assert _is_post_ibex_close_window(datetime(2026, 6, 30, 17, 30, tzinfo=madrid)) is False
    assert _is_post_ibex_close_window(datetime(2026, 6, 28, 18, 0, tzinfo=madrid)) is False
