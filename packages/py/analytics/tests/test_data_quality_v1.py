"""Tests para data_quality_v1."""

from datetime import date, timedelta

from bolsa_analytics.signals.data_quality_v1 import (
    compute_data_quality_v1,
    compute_global_score,
    count_recent_weekday_gaps,
)


def _date_series(start: date, count: int, *, skip_after: int | None = None) -> list[str]:
    timestamps: list[str] = []
    current = start
    added = 0
    while added < count:
        if current.weekday() < 5:
            timestamps.append(current.isoformat())
            added += 1
            if skip_after is not None and added == skip_after:
                current += timedelta(days=5)
                continue
        current += timedelta(days=1)
    return timestamps


def test_count_recent_weekday_gaps_detects_missing_business_day() -> None:
    timestamps = _date_series(date(2024, 1, 1), 10, skip_after=5)
    # Tras el 5º día hábil (vie 5 ene) saltamos al mié 10 ene → faltan lun/mar.
    assert count_recent_weekday_gaps(timestamps) >= 2


def test_compute_data_quality_v1_current_data_scores_high() -> None:
    expected = date(2024, 6, 14)
    timestamps = _date_series(expected - timedelta(days=120), 120)
    breakdown = compute_data_quality_v1(
        bar_count=520,
        last_bar_timestamp=expected.isoformat(),
        expected_last_bar_date=expected.isoformat(),
        last_sync_status="ok",
        recent_timestamps=timestamps,
        has_fundamental_gate=True,
        fundamentals_ok=True,
    )
    assert breakdown.total >= 85.0
    assert breakdown.freshness >= 95.0
    assert breakdown.bar_depth >= 95.0


def test_compute_data_quality_v1_stale_and_failed_sync_score_lower() -> None:
    expected = date(2024, 6, 14)
    last = expected - timedelta(days=7)
    breakdown = compute_data_quality_v1(
        bar_count=80,
        last_bar_timestamp=last.isoformat(),
        expected_last_bar_date=expected.isoformat(),
        last_sync_status="failed",
        last_sync_error="timeout",
        recent_timestamps=_date_series(last - timedelta(days=30), 30),
        has_fundamental_gate=True,
        fundamentals_ok=False,
    )
    assert breakdown.total < 60.0
    assert breakdown.sync <= 20.0
    assert breakdown.fundamentals <= 30.0


def test_compute_global_score_weighted() -> None:
    assert compute_global_score(80.0, 60.0) == 74.0
