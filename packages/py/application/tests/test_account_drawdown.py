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


def test_zero_reference_is_unmeasured_not_zero_percent():
    """P3: `reference <= 0` es ausencia de marca, no "sin caída"."""
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    d = book.update("acc-zero", 0.0, initial_deposit=100_000.0, now=t0)
    assert d.daily_pct is None
    assert d.weekly_pct is None
    # El pico sigue siendo medible (lo siembra el depósito), pero la cuenta a cero no
    # produce un 0 % de drawdown: produce el 100 % real desde el pico.
    assert d.max_pct == 100.0


def test_zero_value_stored_mark_is_unmeasured_not_reopened():
    """Una marca guardada a 0 no se usa como denominador ni se reabre a 0 %."""
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    day = t0.strftime("%Y-%m-%d")
    book.load_from_settings(
        "acc-stale-zero",
        {
            "equityMarks": {
                "dayKey": day,
                "weekKey": day,
                "dayOpen": 0.0,
                "weekOpen": 0.0,
            }
        },
    )
    d = book.update("acc-stale-zero", 95_000.0, initial_deposit=100_000.0, now=t0)
    # `None` (no medido) y no `0.0`: reabrir el día borraría la caída real.
    assert d.daily_pct is None
    assert d.day_open_equity == 0.0


def test_non_finite_equity_is_unmeasured_and_does_not_poison_the_book():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    book.update("acc-nan", 100_000.0, initial_deposit=100_000.0, now=t0)
    poisoned = book.update(
        "acc-nan", float("nan"), initial_deposit=100_000.0, now=t0 + timedelta(hours=1)
    )
    assert poisoned.daily_pct is None
    assert poisoned.weekly_pct is None
    assert poisoned.max_pct is None
    assert poisoned.day_open_equity is None
    # La marca buena del día sigue siendo la referencia: el NaN no la reemplaza.
    recovered = book.update(
        "acc-nan", 97_000.0, initial_deposit=100_000.0, now=t0 + timedelta(hours=2)
    )
    assert recovered.daily_pct == 3.0
    assert recovered.max_pct == 3.0


def test_infinite_equity_is_unmeasured():
    book = EquityMarkBook()
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    d = book.update(
        "acc-inf", float("inf"), initial_deposit=100_000.0, now=t0
    )
    assert d.daily_pct is None
    assert d.max_pct is None
    assert d.day_open_equity is None
