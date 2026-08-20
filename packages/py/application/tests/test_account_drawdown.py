"""F4 — EquityMarkBook daily/weekly drawdown telemetry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_application.account_drawdown import EquityMarkBook


def test_equity_mark_book_daily_weekly():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)  # Monday
    d1 = book.update("acc-1", 100_000.0, initial_deposit=100_000.0, now=t0)
    assert d1.daily_pct == 0.0
    assert d1.max_pct == 0.0
    d2 = book.update("acc-1", 97_000.0, initial_deposit=100_000.0, now=t0 + timedelta(hours=2))
    assert d2.daily_pct == 3.0
    assert d2.max_pct == 3.0
    t1 = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
    d3 = book.update("acc-1", 97_000.0, initial_deposit=100_000.0, now=t1)
    assert d3.daily_pct == 0.0
    assert d3.weekly_pct == 3.0


def test_equity_mark_book_roundtrip_settings():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
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


def test_max_pct_stays_elevated_after_partial_recovery():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    d1 = book.update("acc-hwm", 100_000.0, initial_deposit=100_000.0, now=t0)
    assert d1.max_pct == 0.0
    d2 = book.update(
        "acc-hwm",
        90_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=2),
    )
    assert d2.max_pct == 10.0
    d3 = book.update(
        "acc-hwm",
        98_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=3),
    )
    assert d3.max_pct == 10.0
    assert d3.daily_pct == 2.0


def test_max_pct_resets_on_new_high():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    book.update("acc-hwm2", 100_000.0, initial_deposit=100_000.0, now=t0)
    book.update(
        "acc-hwm2",
        90_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=2),
    )
    book.update(
        "acc-hwm2",
        98_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=3),
    )
    d = book.update(
        "acc-hwm2",
        105_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=4),
    )
    assert d.max_pct == 0.0


def test_max_pct_survives_restart_via_settings_roundtrip():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    book.update("acc-hwm3", 100_000.0, initial_deposit=100_000.0, now=t0)
    book.update(
        "acc-hwm3",
        90_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=1),
    )
    book.update(
        "acc-hwm3",
        98_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=2),
    )
    frag = book.export_settings_fragment("acc-hwm3")
    restored = EquityMarkBook()
    restored.load_from_settings("acc-hwm3", frag)
    d = restored.update(
        "acc-hwm3",
        98_000.0,
        initial_deposit=100_000.0,
        now=t0 + timedelta(hours=3),
    )
    assert d.max_pct == 10.0


def test_no_deposit_baseline_keeps_max_pct_none():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    d = book.update("acc-nodep", 100_000.0, now=t0)
    assert d.max_pct is None
