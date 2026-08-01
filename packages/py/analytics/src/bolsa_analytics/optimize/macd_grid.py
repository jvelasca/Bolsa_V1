"""MACD signal-cross parameter grid (Campaign 3) — bar-by-bar, no future peek."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.indicators.compute import compute_ema, compute_macd_line
from bolsa_analytics.optimize.grid_is_metrics import finalize_grid_is_metrics

ProgressCallback = Callable[[int, int, float | None], None]


@dataclass(frozen=True, slots=True)
class MacdGridTrial:
    fast_period: int
    slow_period: int
    signal_period: int
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    score: float
    is_metrics: dict[str, Any] = field(default_factory=dict)
    oos_metrics: dict[str, Any] | None = None


def _macd_signal_line(
    closes: list[float], fast: int, slow: int, signal_period: int
) -> list[float | None]:
    macd_line = compute_macd_line(closes, fast, slow)
    # NOTE (C3.5): seeding None→0.0 warms EMA on artificial zeros; revisit before
    # treating macd_grid_h0 as definitive reference (classic MACD waits for valid seed).
    # Issue: research/observations/ISSUES.md#macd-signal-ema-warmup
    numeric = [value if value is not None else 0.0 for value in macd_line]
    return compute_ema(numeric, signal_period)


def _simulate_macd_signal_cross(
    bars: list[BacktestBarInput],
    *,
    fast_period: int,
    slow_period: int,
    signal_period: int,
    initial_cash: float,
    trade_from_index: int = 0,
    attach_round_trips: bool = False,
) -> dict[str, Any]:
    """MACD sim. Indicator uses all bars; trading starts at ``trade_from_index``."""
    if fast_period < 2 or slow_period < 2 or signal_period < 2:
        raise ValueError("periods must be >= 2")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be < slow_period")
    start = max(0, min(int(trade_from_index), len(bars)))

    closes = [bar.close for bar in bars]
    macd_line = compute_macd_line(closes, fast_period, slow_period)
    signal_line = _macd_signal_line(closes, fast_period, slow_period, signal_period)

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
        price = bar.close
        if index > 0:
            prev_macd = macd_line[index - 1]
            prev_signal = signal_line[index - 1]
            cur_macd = macd_line[index]
            cur_signal = signal_line[index]
            if (
                prev_macd is not None
                and prev_signal is not None
                and cur_macd is not None
                and cur_signal is not None
            ):
                bullish = prev_macd <= prev_signal and cur_macd > cur_signal
                bearish = prev_macd >= prev_signal and cur_macd < cur_signal
                if shares == 0 and bullish and cash >= price:
                    quantity = int(cash // price)
                    if quantity > 0:
                        cost = quantity * price
                        cash -= cost
                        shares = float(quantity)
                        trades += 1
                        open_entry_cost = cost
                elif shares > 0 and bearish:
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


DEFAULT_MACD_TRIPLES: list[tuple[int, int, int]] = [
    (5, 13, 5),
    (5, 20, 5),
    (5, 26, 9),
    (8, 17, 5),
    (8, 17, 9),
    (8, 21, 5),
    (8, 21, 9),
    (8, 26, 9),
    (10, 20, 7),
    (10, 26, 9),
    (10, 30, 9),
    (12, 26, 5),
    (12, 26, 9),
    (12, 26, 12),
    (12, 30, 9),
    (12, 35, 9),
    (16, 26, 9),
    (16, 35, 9),
    (16, 40, 9),
    (20, 40, 9),
    (20, 50, 9),
    (6, 19, 6),
    (7, 21, 7),
    (9, 26, 9),
    (15, 35, 9),
]


def estimate_macd_grid_trial_total(
    triples: list[tuple[int, int, int]],
    *,
    max_trials: int = 25,
) -> int:
    count = sum(1 for fast, slow, _signal in triples if fast < slow)
    return max(1, min(count, max_trials))


def run_macd_signal_cross_grid(
    bars: list[BacktestBarInput],
    *,
    triples: list[tuple[int, int, int]] | None = None,
    initial_cash: float = 10000.0,
    max_trials: int = 25,
    on_progress: ProgressCallback | None = None,
) -> list[MacdGridTrial]:
    if not bars:
        raise ValueError("bars must not be empty")

    # Compact classic MACD neighbourhood (~25) — fast < slow always.
    resolved = triples or list(DEFAULT_MACD_TRIPLES)
    total = estimate_macd_grid_trial_total(resolved, max_trials=max_trials)

    trials: list[MacdGridTrial] = []
    best_score: float | None = None
    for fast_period, slow_period, signal_period in resolved:
        if len(trials) >= max_trials:
            break
        if fast_period >= slow_period:
            continue
        try:
            metrics = _simulate_macd_signal_cross(
                bars,
                fast_period=fast_period,
                slow_period=slow_period,
                signal_period=signal_period,
                initial_cash=initial_cash,
            )
        except ValueError:
            continue
        score = float(metrics["score"])
        trials.append(
            MacdGridTrial(
                fast_period=fast_period,
                slow_period=slow_period,
                signal_period=signal_period,
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
