"""RSI mean-reversion parameter grid (Campaign 2) — bar-by-bar, no future peek."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.indicators.legacy import rsi
from bolsa_analytics.optimize.grid_is_metrics import finalize_grid_is_metrics

ProgressCallback = Callable[[int, int, float | None], None]


@dataclass(frozen=True, slots=True)
class RsiGridTrial:
    period: int
    oversold: float
    overbought: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    score: float
    is_metrics: dict[str, Any] = field(default_factory=dict)
    oos_metrics: dict[str, Any] | None = None


def _simulate_rsi_mean_reversion(
    bars: list[BacktestBarInput],
    *,
    period: int,
    oversold: float,
    overbought: float,
    initial_cash: float,
    trade_from_index: int = 0,
    attach_round_trips: bool = False,
) -> dict[str, Any]:
    """RSI MR sim. Indicator uses all bars; trading starts at ``trade_from_index``."""
    if period < 2:
        raise ValueError("period must be >= 2")
    if oversold >= overbought:
        raise ValueError("oversold must be < overbought")
    start = max(0, min(int(trade_from_index), len(bars)))

    closes = [bar.close for bar in bars]
    series = rsi(closes, period)

    cash = initial_cash
    shares = 0.0
    trades = 0
    peak = initial_cash
    max_drawdown = 0.0
    equity_values: list[float] = []
    entry_costs: list[float] = []
    exit_proceeds: list[float] = []
    open_entry_cost: float | None = None

    for index, bar in enumerate(bars):
        if index < start:
            continue
        value = series[index]
        price = bar.close
        if value is not None:
            if shares == 0 and value < oversold and cash >= price:
                quantity = int(cash // price)
                if quantity > 0:
                    cost = quantity * price
                    cash -= cost
                    shares = float(quantity)
                    trades += 1
                    open_entry_cost = cost
            elif shares > 0 and value > overbought:
                proceeds = shares * price
                cash += proceeds
                if open_entry_cost is not None:
                    entry_costs.append(open_entry_cost)
                    exit_proceeds.append(proceeds)
                    open_entry_cost = None
                shares = 0.0
                trades += 1

        equity = cash + shares * price
        equity_values.append(equity)
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = ((peak - equity) / peak) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    if not equity_values:
        raise ValueError("trade_from_index deja el tramo de trading vacío")

    return finalize_grid_is_metrics(
        equity_values=equity_values,
        initial_cash=initial_cash,
        max_drawdown_pct=max_drawdown,
        trade_count=trades,
        round_trip_pnls=[exit - entry for entry, exit in zip(entry_costs, exit_proceeds, strict=False)],
        attach_round_trips=attach_round_trips,
    )


def estimate_rsi_grid_trial_total(
    periods: list[int],
    oversold_levels: list[float],
    overbought_levels: list[float],
    *,
    max_trials: int = 25,
) -> int:
    count = 0
    for period in periods:
        for oversold in oversold_levels:
            for overbought in overbought_levels:
                if oversold >= overbought:
                    continue
                count += 1
                if count >= max_trials:
                    return max_trials
    return max(1, count)


def run_rsi_mean_reversion_grid(
    bars: list[BacktestBarInput],
    *,
    periods: list[int] | None = None,
    oversold_levels: list[float] | None = None,
    overbought_levels: list[float] | None = None,
    initial_cash: float = 10000.0,
    max_trials: int = 25,
    on_progress: ProgressCallback | None = None,
) -> list[RsiGridTrial]:
    if not bars:
        raise ValueError("bars must not be empty")

    resolved_periods = periods or [10, 12, 14, 16, 18, 20]
    resolved_os = oversold_levels or [20.0, 25.0, 30.0, 35.0]
    resolved_ob = overbought_levels or [65.0, 70.0, 75.0, 80.0]
    total = estimate_rsi_grid_trial_total(
        resolved_periods, resolved_os, resolved_ob, max_trials=max_trials
    )

    trials: list[RsiGridTrial] = []
    best_score: float | None = None
    for period in resolved_periods:
        for oversold in resolved_os:
            for overbought in resolved_ob:
                if oversold >= overbought:
                    continue
                if len(trials) >= max_trials:
                    trials.sort(key=lambda trial: trial.score, reverse=True)
                    return trials
                try:
                    metrics = _simulate_rsi_mean_reversion(
                        bars,
                        period=period,
                        oversold=oversold,
                        overbought=overbought,
                        initial_cash=initial_cash,
                    )
                except ValueError:
                    continue
                score = float(metrics["score"])
                trials.append(
                    RsiGridTrial(
                        period=period,
                        oversold=oversold,
                        overbought=overbought,
                        total_return_pct=float(metrics["totalReturnPct"]),
                        max_drawdown_pct=float(metrics["maxDrawdownPct"]),
                        trade_count=int(metrics["tradeCount"]),
                        score=score,
                        is_metrics=metrics,
                    )
                )
                if best_score is None or score > best_score:
                    best_score = score
                if on_progress is not None:
                    on_progress(len(trials), total, best_score)
    trials.sort(key=lambda trial: trial.score, reverse=True)
    return trials
