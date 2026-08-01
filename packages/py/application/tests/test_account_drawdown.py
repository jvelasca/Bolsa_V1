"""F4 — EquityMarkBook daily/weekly drawdown telemetry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bolsa_application.account_drawdown import EquityMarkBook


def test_equity_mark_book_daily_weekly():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)  # Monday
    d1 = book.update("acc-1", 100_000.0, initial_deposit=100_000.0, now=t0)
    assert d1.daily_pct == 0.0
    assert d1.max_pct == 0.0
    d2 = book.update("acc-1", 97_000.0, initial_deposit=100_000.0, now=t0 + timedelta(hours=2))
    assert d2.daily_pct == 3.0
    assert d2.max_pct == 3.0
    t1 = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    d3 = book.update("acc-1", 97_000.0, initial_deposit=100_000.0, now=t1)
    assert d3.daily_pct == 0.0
    assert d3.weekly_pct == 3.0


def test_equity_mark_book_roundtrip_settings():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
    book.update("acc-1", 100_000.0, initial_deposit=100_000.0, now=t0)
    book.update("acc-1", 95_000.0, initial_deposit=100_000.0, now=t0 + timedelta(hours=1))
    frag = book.export_settings_fragment("acc-1")
    restored = EquityMarkBook()
    restored.load_from_settings("acc-1", frag)
    d = restored.update(
        "acc-1",
        95_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=2),
    )
    assert d.daily_pct == 5.0
    assert d.max_pct == 5.0
