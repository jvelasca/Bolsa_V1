"""Smoke tests for warm-up matrix (Q0.3)."""

from bolsa_analytics.warmup_matrix import WARMUP_MATRIX, min_bars_for, warmup_audit_rows


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
