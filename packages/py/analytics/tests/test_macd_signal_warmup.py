"""Classic MACD signal EMA warm-up (no None→0 seed)."""

from bolsa_analytics.indicators.compute import (
    compute_macd_line,
    compute_macd_signal_from_line,
    compute_macd_signal_line,
)


def test_macd_signal_stays_none_until_classic_warmup() -> None:
    closes = [100.0 + (i % 7) * 0.4 - (i % 5) * 0.2 for i in range(80)]
    fast, slow, signal = 12, 26, 9
    macd = compute_macd_line(closes, fast, slow)
    classic = compute_macd_signal_line(closes, fast, slow, signal)

    first_macd = next(i for i, v in enumerate(macd) if v is not None)
    # Classic: first signal value at first_macd + signal - 1
    first_signal = first_macd + signal - 1
    assert all(v is None for v in classic[:first_signal])
    assert classic[first_signal] is not None


def test_zero_seed_differs_from_classic_early_bars() -> None:
    closes = [100.0 + i * 0.05 + ((i % 11) - 5) * 0.3 for i in range(100)]
    macd = compute_macd_line(closes, 12, 26)
    classic = compute_macd_signal_from_line(macd, 9)
    # Legacy zero-fill path (what grids used before this fix)
    from bolsa_analytics.indicators.compute import compute_ema

    zero_seeded = compute_ema([v if v is not None else 0.0 for v in macd], 9)
    # Early zero-seeded values exist while classic is still None
    early_classic_none = [i for i, v in enumerate(classic) if v is None]
    assert early_classic_none
    assert any(zero_seeded[i] is not None for i in early_classic_none)
