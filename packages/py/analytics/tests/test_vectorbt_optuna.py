from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.engines import engine_result_label, resolve_optimize_engine
from bolsa_analytics.optimize.optuna_sma import run_optuna_sma_search
from bolsa_analytics.optimize.vectorbt_sma import run_vectorbt_sma_grid


def _trend_bars(count: int = 80) -> list[BacktestBarInput]:
    return [
        BacktestBarInput(timestamp=f"2024-01-{day:02d}", close=100.0 + day * 0.4)
        for day in range(1, count + 1)
    ]


def test_resolve_optimize_engine_auto_prefers_vectorbt() -> None:
    assert resolve_optimize_engine("auto") in {"vectorbt", "h0"}


def test_engine_result_label() -> None:
    assert engine_result_label("vectorbt") == "vectorbt_sma_grid"
    assert engine_result_label("optuna") == "optuna_sma"


def test_run_vectorbt_sma_grid_returns_trials() -> None:
    bars = _trend_bars()
    trials = run_vectorbt_sma_grid(
        bars,
        fast_periods=[10, 15],
        slow_periods=[40, 50],
        initial_cash=10000,
        max_trials=4,
    )
    assert trials
    assert all(trial.fast_period < trial.slow_period for trial in trials)


def test_run_optuna_sma_search_returns_trials() -> None:
    bars = _trend_bars()
    trials = run_optuna_sma_search(
        bars,
        fast_periods=[10, 12, 15],
        slow_periods=[40, 45, 50],
        initial_cash=10000,
        max_trials=5,
    )
    assert trials
    assert len(trials) <= 5
