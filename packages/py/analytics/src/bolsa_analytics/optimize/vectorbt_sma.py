"""RD-3 full — grid SMA crossover con VectorBT."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import vectorbt as vbt

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.metrics import trial_score, vectorbt_freq
from bolsa_analytics.optimize.sma_grid import SmaGridTrial, estimate_sma_grid_trial_total

ProgressCallback = Callable[[int, int, float | None], None]


def _simulate_vectorbt_sma(
    close: np.ndarray,
    fast_period: int,
    slow_period: int,
    initial_cash: float,
    freq: str,
) -> tuple[float, float, int]:
    if fast_period >= slow_period:
        raise ValueError("fastPeriod debe ser menor que slowPeriod")

    fast_ma = vbt.MA.run(close, fast_period)
    slow_ma = vbt.MA.run(close, slow_period)
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)
    portfolio = vbt.Portfolio.from_signals(
        close,
        entries,
        exits,
        init_cash=initial_cash,
        freq=freq,
    )
    total_return_pct = float(portfolio.total_return()) * 100
    max_drawdown_pct = abs(float(portfolio.max_drawdown())) * 100
    trade_count = int(portfolio.trades.count())
    return total_return_pct, max_drawdown_pct, trade_count


def run_vectorbt_sma_grid(
    bars: list[BacktestBarInput],
    *,
    fast_periods: list[int],
    slow_periods: list[int],
    initial_cash: float = 10000.0,
    max_trials: int = 200,
    timeframe: str = "1d",
    on_progress: ProgressCallback | None = None,
) -> list[SmaGridTrial]:
    """Ejecuta ``vectorbt_sma_grid``."""
    if not bars:
        raise ValueError("bars must not be empty")

    close = np.asarray([bar.close for bar in bars], dtype=float)
    freq = vectorbt_freq(timeframe)
    total = estimate_sma_grid_trial_total(fast_periods, slow_periods, max_trials=max_trials)
    trials: list[SmaGridTrial] = []
    best_score: float | None = None

    for fast in fast_periods:
        for slow in slow_periods:
            if fast >= slow:
                continue
            if len(trials) >= max_trials:
                break
            try:
                total_return, max_dd, trade_count = _simulate_vectorbt_sma(
                    close,
                    fast,
                    slow,
                    initial_cash,
                    freq,
                )
            except ValueError:
                continue
            score = trial_score(total_return, max_dd)
            trials.append(
                SmaGridTrial(
                    fast_period=fast,
                    slow_period=slow,
                    total_return_pct=round(total_return, 4),
                    max_drawdown_pct=round(max_dd, 4),
                    trade_count=trade_count,
                    score=score,
                    is_metrics={
                        "totalReturnPct": round(total_return, 4),
                        "maxDrawdownPct": round(max_dd, 4),
                        "tradeCount": trade_count,
                        "score": score,
                    },
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
