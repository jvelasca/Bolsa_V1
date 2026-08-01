from datetime import date

from bolsa_application.sync_instrument import resolve_sync_date_range


def test_resolve_sync_date_range_full_history_without_bars() -> None:
    to_date = date(2026, 6, 24)
    from_date, _, incremental = resolve_sync_date_range(
        to_date=to_date,
        years_back=5,
        latest_bar_date=None,
    )
    assert incremental is False
    assert from_date == date(2021, 6, 24)


def test_resolve_sync_date_range_incremental_with_overlap() -> None:
    to_date = date(2026, 6, 24)
    from_date, _, incremental = resolve_sync_date_range(
        to_date=to_date,
        years_back=5,
        latest_bar_date="2026-06-20",
        overlap_days=7,
    )
    assert incremental is True
    assert from_date == date(2026, 6, 13)
