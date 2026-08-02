"""Smoke tests for warm-up matrix (Q0.3) + Q1.6 asserts."""

import pytest

from bolsa_analytics.warmup_matrix import (
    WARMUP_MATRIX,
    WarmupInsufficientError,
    assert_grid_warmup,
    check_manifest_warmup,
    family_from_engine,
    min_bars_for,
    warmup_audit_rows,
)


def test_warmup_matrix_covers_required_families() -> None:
    families = {s.family for s in WARMUP_MATRIX}
    assert {"sma", "ema", "rsi", "macd", "bollinger", "adx", "atr"} <= families


def test_macd_min_bars_is_slow_plus_signal() -> None:
    assert min_bars_for("macd", {"fast": 12, "slow": 26, "signal": 9}) == 35


def test_sma_min_bars_uses_slow() -> None:
    assert min_bars_for("sma", {"fast": 10, "slow": 40}) == 40


def test_warmup_audit_rows_smoke() -> None:
    rows = warmup_audit_rows()
    assert len(rows) >= 7
    assert all("minBars" in r and int(r["minBars"]) > 0 for r in rows)


def test_family_from_engine() -> None:
    assert family_from_engine("rsi_grid_h0") == "rsi"
    assert family_from_engine("sma_grid_h0") == "sma"
    assert family_from_engine("macd_grid_h0") == "macd"
    assert family_from_engine("unknown") is None


def test_assert_grid_warmup_raises_when_short() -> None:
    with pytest.raises(WarmupInsufficientError) as exc:
        assert_grid_warmup("sma", 10, [{"fast": 5, "slow": 40}])
    assert exc.value.required == 40
    assert exc.value.bar_count == 10


def test_check_manifest_warmup_ok_and_fail() -> None:
    assert check_manifest_warmup(
        {"engine": "rsi_grid_h0", "bar_count": 500}
    ) == []
    errs = check_manifest_warmup({"engine": "macd_grid_h0", "bar_count": 10})
    assert errs and "warm-up macd" in errs[0]
