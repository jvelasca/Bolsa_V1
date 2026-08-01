"""Application-layer OOS attach uses IS warm-up."""

from datetime import UTC, datetime, timedelta

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.holdout import split_holdout_bars
from bolsa_application.optimize import (
    STRATEGY_FAMILY_SMA,
    OptimizeGridTrial,
    _attach_oos,
    _eval_oos_for_grid,
)


def _bars(n: int) -> list[BacktestBarInput]:
    start = datetime(2016, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + i * 0.12 + (1.5 if i % 11 < 5 else -0.8),
        )
        for i in range(n)
    ]


def test_eval_oos_attaches_metrics_with_warmup() -> None:
    bars = _bars(250)
    holdout = split_holdout_bars(bars, 0.2)
    assert holdout is not None
    trial = OptimizeGridTrial(
        total_return_pct=1.0,
        max_drawdown_pct=5.0,
        trade_count=3,
        score=0.0,
        params={"fastPeriod": 10, "slowPeriod": 30},
    )
    evaluated = _eval_oos_for_grid(
        trial,
        family=STRATEGY_FAMILY_SMA,
        is_bars=holdout.is_bars,
        oos_bars=holdout.oos_bars,
        initial_cash=10_000.0,
    )
    assert evaluated.oos_metrics is not None
    assert "score" in evaluated.oos_metrics
    assert "tradeCount" in evaluated.oos_metrics


def test_attach_oos_populates_baseline_and_trials() -> None:
    bars = _bars(250)
    holdout = split_holdout_bars(bars, 0.2)
    assert holdout is not None
    baseline = OptimizeGridTrial(
        total_return_pct=0.0,
        max_drawdown_pct=0.0,
        trade_count=0,
        score=0.0,
        params={"fastPeriod": 20, "slowPeriod": 50},
    )
    trials = [
        OptimizeGridTrial(
            total_return_pct=2.0,
            max_drawdown_pct=4.0,
            trade_count=4,
            score=1.0,
            params={"fastPeriod": 12, "slowPeriod": 40},
        )
    ]
    baseline_oos, trials_oos = _attach_oos(
        baseline,
        trials,
        family=STRATEGY_FAMILY_SMA,
        holdout=holdout,
        initial_cash=10_000.0,
    )
    assert baseline_oos.oos_metrics is not None
    assert trials_oos[0].oos_metrics is not None
