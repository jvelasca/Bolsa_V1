from datetime import date, timedelta

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.macd_grid import run_macd_signal_cross_grid


def test_macd_grid_respects_max_trials() -> None:
    start = date(2020, 1, 1)
    bars = [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + ((i % 20) - 10) * 1.5,
        )
        for i in range(120)
    ]
    trials = run_macd_signal_cross_grid(bars, max_trials=10)
    assert len(trials) == 10
    assert all(t.fast_period < t.slow_period for t in trials)
    assert "sharpeRatio" in trials[0].is_metrics
    assert "totalReturnPct" in trials[0].is_metrics
