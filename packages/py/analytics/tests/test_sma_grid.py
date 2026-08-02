from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.sma_grid import run_baseline_preset_backtest, run_sma_grid_search


def _trend_bars(count: int = 120, start: float = 100.0, step: float = 0.5) -> list[BacktestBarInput]:
    from datetime import date, timedelta

    start_d = date(2024, 1, 1)
    return [
        BacktestBarInput(
            timestamp=(start_d + timedelta(days=day)).isoformat(),
            close=start + day * step,
        )
        for day in range(1, count + 1)
    ]


def test_run_sma_grid_search_skips_invalid_pairs() -> None:
    bars = _trend_bars()
    trials = run_sma_grid_search(
        bars,
        fast_periods=[10, 30],
        slow_periods=[20, 40],
        initial_cash=10000,
        max_trials=10,
    )
    assert all(trial.fast_period < trial.slow_period for trial in trials)
    assert len(trials) <= 3


def test_run_sma_grid_search_sorted_by_score() -> None:
    bars = _trend_bars()
    trials = run_sma_grid_search(
        bars,
        fast_periods=[10, 15, 20],
        slow_periods=[40, 50, 60],
        initial_cash=10000,
    )
    assert trials
    scores = [trial.score for trial in trials]
    assert scores == sorted(scores, reverse=True)
    assert "sharpeRatio" in trials[0].is_metrics


def test_run_baseline_preset_backtest() -> None:
    bars = _trend_bars()
    baseline = run_baseline_preset_backtest(bars, 10000)
    assert baseline.fast_period == 20
    assert baseline.slow_period == 50
    assert baseline.trade_count >= 0
