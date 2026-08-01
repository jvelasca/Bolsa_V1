from bolsa_analytics.backtest import BacktestBarInput, run_backtest
from bolsa_analytics.signals.evaluate import (
    evaluate_preset_signals,
    evaluate_preset_signals_gated,
)


def test_gated_signals_match_backtest_trades() -> None:
    bars = [
        BacktestBarInput(timestamp=f"2024-01-{day:02d}", close=100.0 + day * 0.5)
        for day in range(1, 61)
    ]
    timestamps = [bar.timestamp for bar in bars]
    closes = [bar.close for bar in bars]

    result = run_backtest(bars, "sma_crossover", 10000)
    gated = evaluate_preset_signals_gated("sma_crossover", timestamps, closes)

    assert len(gated) == len(result.trades)
    for event, trade in zip(gated, result.trades, strict=True):
        assert event.timestamp == trade.timestamp
        assert event.price == trade.price
        if trade.type == "buy":
            assert event.kind == "entry_long"
        else:
            assert event.kind == "exit"


def test_raw_signals_include_reentries() -> None:
    """Raw mode emite cada cruce — útil para screener (SC-1)."""
    bars = [
        BacktestBarInput(timestamp=f"2024-02-{day:02d}", close=100.0 + day * 0.3)
        for day in range(1, 61)
    ]
    timestamps = [bar.timestamp for bar in bars]
    closes = [bar.close for bar in bars]

    raw = evaluate_preset_signals("sma_crossover", timestamps, closes)
    gated = evaluate_preset_signals_gated("sma_crossover", timestamps, closes)

    assert len(raw) >= len(gated)
