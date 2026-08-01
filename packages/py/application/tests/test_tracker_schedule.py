from datetime import datetime
from zoneinfo import ZoneInfo

from bolsa_application.tracker_schedule import (
    is_bar_close_window,
    is_tracker_due_for_bar,
    merge_schedule_run_state,
    schedule_kind,
)


def test_schedule_kind_from_definition() -> None:
    assert schedule_kind({"schedule": {"kind": "on_bar_close"}}) == "on_bar_close"
    assert schedule_kind({}) is None


def test_is_tracker_due_when_new_bar() -> None:
    madrid = ZoneInfo("Europe/Madrid")
    friday_evening = datetime(2026, 7, 10, 18, 0, tzinfo=madrid)
    assert is_tracker_due_for_bar(
        latest_bar_timestamp="2026-07-10",
        schedule={},
        timeframe="1d",
        now=friday_evening,
    )


def test_is_tracker_not_due_same_bar() -> None:
    madrid = ZoneInfo("Europe/Madrid")
    friday_evening = datetime(2026, 7, 10, 18, 0, tzinfo=madrid)
    assert not is_tracker_due_for_bar(
        latest_bar_timestamp="2026-07-10",
        schedule={"lastBarTimestamp": "2026-07-10"},
        timeframe="1d",
        now=friday_evening,
    )


def test_weekly_bar_close_window_friday() -> None:
    madrid = ZoneInfo("Europe/Madrid")
    friday = datetime(2026, 7, 10, 10, 0, tzinfo=madrid)
    assert is_bar_close_window("1wk", now=friday)


def test_merge_schedule_run_state() -> None:
    definition = {"schedule": {"kind": "on_bar_close"}}
    merged = merge_schedule_run_state(
        definition,
        latest_bar_timestamp="2026-07-10",
        run_at="2026-07-10T18:00:00+00:00",
    )
    assert merged["schedule"]["lastBarTimestamp"] == "2026-07-10"
    assert merged["schedule"]["lastRunAt"] == "2026-07-10T18:00:00+00:00"
