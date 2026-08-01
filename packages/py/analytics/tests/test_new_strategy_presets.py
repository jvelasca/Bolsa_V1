"""Smoke tests for new channel / ADX / Ichimoku / VWAP / SuperTrend presets."""

from __future__ import annotations

from bolsa_analytics.backtest import BacktestBarInput, run_backtest
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.preset_catalog import (
    is_valid_preset_key,
    load_preset_catalog,
    preset_strategy_keys,
)
from bolsa_analytics.signals.rules_engine import build_indicator_context


NEW_PRESETS = (
    "donchian_breakout",
    "adx_di_trend",
    "ichimoku_tk_cross",
    "vwap_reclaim",
    "supertrend_follow",
)


def _ohlcv_trend_bars(n: int = 120) -> list[BacktestBarInput]:
    bars: list[BacktestBarInput] = []
    for day in range(1, n + 1):
        close = 100.0 + day * 0.8
        high = close + 1.2
        low = close - 1.0
        open_ = close - 0.3
        bars.append(
            BacktestBarInput(
                timestamp=f"2024-{(day // 28) + 1:02d}-{(day % 28) + 1:02d}",
                close=close,
                open=open_,
                high=high,
                low=low,
                volume=1_000.0 + day * 10,
            )
        )
    return bars


def test_new_presets_are_in_catalog() -> None:
    load_preset_catalog.cache_clear()
    preset_strategy_keys.cache_clear()
    keys = preset_strategy_keys()
    for key in NEW_PRESETS:
        assert key in keys
        assert is_valid_preset_key(key)


def test_series_for_new_preset_specs_resolve() -> None:
    load_preset_catalog.cache_clear()
    catalog = load_preset_catalog()
    raw = _ohlcv_trend_bars(90)
    ohlcv = [
        OhlcvBar(
            timestamp=b.timestamp,
            open=b.open or b.close,
            high=b.high or b.close,
            low=b.low or b.close,
            close=b.close,
            volume=float(b.volume),
        )
        for b in raw
    ]
    for key in NEW_PRESETS:
        specs = catalog["presets"][key]["indicatorSpecs"]
        context = build_indicator_context(ohlcv, specs)
        assert len(context) == len(specs), f"{key} missing series"
        for series in context.values():
            assert any(v is not None for v in series), f"{key} all-null series"


def test_donchian_and_supertrend_backtest_smoke() -> None:
    bars = _ohlcv_trend_bars(100)
    for key in ("donchian_breakout", "supertrend_follow", "vwap_reclaim"):
        result = run_backtest(bars, key, 10_000.0)
        assert result.bar_count == len(bars)
        assert "totalReturnPct" in result.is_metrics
