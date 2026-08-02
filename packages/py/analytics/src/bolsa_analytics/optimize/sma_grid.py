"""RD-3 — grid search SMA crossover (stub previo a VectorBT + Optuna)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput, run_backtest
from bolsa_analytics.indicators.legacy import sma
from bolsa_analytics.optimize.grid_is_metrics import finalize_grid_is_metrics
from bolsa_analytics.signals.evaluate import PresetFeatureSeries, evaluate_preset_signals_gated
from bolsa_analytics.warmup_matrix import assert_grid_warmup

ProgressCallback = Callable[[int, int, float | None], None]


@dataclass(frozen=True, slots=True)
class SmaGridTrial:
    fast_period: int
    slow_period: int
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    score: float
    is_metrics: dict[str, Any] = field(default_factory=dict)
    oos_metrics: dict[str, Any] | None = None


def _simulate_sma_crossover(
    bars: list[BacktestBarInput],
    fast_period: int,
    slow_period: int,
    initial_cash: float,
    *,
    trade_from_index: int = 0,
    attach_round_trips: bool = False,
) -> dict[str, Any]:
    """Simulate SMA cross. Indicators use all bars; trading starts at ``trade_from_index``."""
    if fast_period >= slow_period:
        raise ValueError("fastPeriod debe ser menor que slowPeriod")
    start = max(0, min(int(trade_from_index), len(bars)))

    timestamps = [bar.timestamp for bar in bars]
    closes = [bar.close for bar in bars]
    features = PresetFeatureSeries(
        sma20=sma(closes, fast_period),
        sma50=sma(closes, slow_period),
        rsi14=[None] * len(closes),
    )
    gated = evaluate_preset_signals_gated("sma_crossover", timestamps, closes, features)
    signal_by_index = {event.bar_index: event.kind for event in gated}

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
        kind = signal_by_index.get(index)
        price = bar.close
        if kind == "entry_long" and cash >= price and shares == 0:
            quantity = int(cash // price)
            if quantity > 0:
                cost = quantity * price
                cash -= cost
                shares = float(quantity)
                trades += 1
                open_entry_cost = cost
        elif kind == "exit" and shares > 0:
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
        peak = max(peak, equity)
        if peak > 0:
            drawdown = ((peak - equity) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)

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


def estimate_sma_grid_trial_total(
    fast_periods: list[int],
    slow_periods: list[int],
    *,
    max_trials: int = 200,
) -> int:
    count = 0
    for fast in fast_periods:
        for slow in slow_periods:
            if fast >= slow:
                continue
            count += 1
            if count >= max_trials:
                return max_trials
    return max(1, count)


def run_sma_grid_search(
    bars: list[BacktestBarInput],
    *,
    fast_periods: list[int],
    slow_periods: list[int],
    initial_cash: float = 10000.0,
    max_trials: int = 200,
    on_progress: ProgressCallback | None = None,
) -> list[SmaGridTrial]:
    if not bars:
        raise ValueError("bars must not be empty")

    assert_grid_warmup(
        "sma",
        len(bars),
        (
            {"fast": fast, "slow": slow}
            for fast in fast_periods
            for slow in slow_periods
            if fast < slow
        ),
    )

    total = estimate_sma_grid_trial_total(
        fast_periods, slow_periods, max_trials=max_trials
    )
    trials: list[SmaGridTrial] = []
    best_score: float | None = None
    for fast in fast_periods:
        for slow in slow_periods:
            if fast >= slow:
                continue
            if len(trials) >= max_trials:
                break
            try:
                metrics = _simulate_sma_crossover(bars, fast, slow, initial_cash)
            except ValueError:
                continue
            score = float(metrics["score"])
            trials.append(
                SmaGridTrial(
                    fast_period=fast,
                    slow_period=slow,
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
        if len(trials) >= max_trials:
            break

    trials.sort(key=lambda trial: trial.score, reverse=True)
    return trials


def run_baseline_preset_backtest(
    bars: list[BacktestBarInput],
    initial_cash: float = 10000.0,
) -> SmaGridTrial:
    result = run_backtest(bars, "sma_crossover", initial_cash)
    metrics = {**result.is_metrics}
    score = float(metrics["totalReturnPct"]) - float(metrics["maxDrawdownPct"]) * 0.25
    metrics["score"] = round(score, 6)
    return SmaGridTrial(
        fast_period=20,
        slow_period=50,
        total_return_pct=result.total_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        trade_count=result.trade_count,
        score=round(score, 4),
        is_metrics=metrics,
    )
