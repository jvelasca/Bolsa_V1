from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.rsi_grid import run_rsi_mean_reversion_grid


def test_rsi_grid_respects_max_trials() -> None:
    from datetime import date, timedelta

    start = date(2020, 1, 1)
    bars = [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + ((i % 20) - 10) * 1.5,
        )
        for i in range(120)
    ]
    trials = run_rsi_mean_reversion_grid(bars, max_trials=10)
    assert len(trials) == 10
    assert all(t.oversold < t.overbought for t in trials)
    assert "sharpeRatio" in trials[0].is_metrics
