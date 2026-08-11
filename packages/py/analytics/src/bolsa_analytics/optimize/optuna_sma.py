"""RD-3 full — búsqueda bayesiana SMA con Optuna + VectorBT."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import numpy as np
import optuna
import vectorbt as vbt

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.metrics import trial_score, vectorbt_freq
from bolsa_analytics.optimize.sma_grid import SmaGridTrial

ProgressCallback = Callable[[int, int, float | None], None]


def run_optuna_sma_search(
    bars: list[BacktestBarInput],
    *,
    fast_periods: list[int],
    slow_periods: list[int],
    initial_cash: float = 10000.0,
    max_trials: int = 50,
    timeframe: str = "1d",
    on_progress: ProgressCallback | None = None,
    execution_model: Literal["next_open"] = "next_open",
) -> list[SmaGridTrial]:
    """Ejecuta ``optuna_sma_search``."""
    if not bars:
        raise ValueError("bars must not be empty")
    if not fast_periods or not slow_periods:
        raise ValueError("fastPeriods y slowPeriods son obligatorios para Optuna")

    close = np.asarray([bar.close for bar in bars], dtype=float)
    open_prices = np.asarray(
        [bar.open if bar.open is not None else bar.close for bar in bars],
        dtype=float,
    )
    freq = vectorbt_freq(timeframe)
    fast_min, fast_max = min(fast_periods), max(fast_periods)
    slow_min, slow_max = min(slow_periods), max(slow_periods)

    collected: list[SmaGridTrial] = []
    best_score: float | None = None

    def objective(trial: optuna.Trial) -> float:
        nonlocal best_score
        fast = trial.suggest_int("fast_period", fast_min, fast_max)
        slow = trial.suggest_int("slow_period", slow_min, slow_max)
        if fast >= slow:
            return -1_000.0

        fast_ma = vbt.MA.run(close, fast)
        slow_ma = vbt.MA.run(close, slow)
        entries = np.asarray(fast_ma.ma_crossed_above(slow_ma), dtype=bool)
        exits = np.asarray(fast_ma.ma_crossed_below(slow_ma), dtype=bool)
        # next_open: señal en t, llenar en open[t+1] (sin look-ahead).
        entries_fill = np.zeros_like(entries)
        exits_fill = np.zeros_like(exits)
        if entries.shape[0] > 1:
            entries_fill[1:] = entries[:-1]
            exits_fill[1:] = exits[:-1]
        portfolio = vbt.Portfolio.from_signals(
            open_prices,
            entries_fill,
            exits_fill,
            init_cash=initial_cash,
            freq=freq,
        )
        total_return_pct = float(portfolio.total_return()) * 100
        max_drawdown_pct = abs(float(portfolio.max_drawdown())) * 100
        trade_count = int(portfolio.trades.count())
        score = trial_score(total_return_pct, max_drawdown_pct)
        collected.append(
            SmaGridTrial(
                fast_period=fast,
                slow_period=slow,
                total_return_pct=round(total_return_pct, 4),
                max_drawdown_pct=round(max_drawdown_pct, 4),
                trade_count=trade_count,
                score=score,
                is_metrics={
                    "totalReturnPct": round(total_return_pct, 4),
                    "maxDrawdownPct": round(max_drawdown_pct, 4),
                    "tradeCount": trade_count,
                    "score": score,
                },
            )
        )
        if best_score is None or score > best_score:
            best_score = score
        if on_progress is not None:
            on_progress(len(collected), max_trials, best_score)
        return score

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=max_trials, show_progress_bar=False)

    unique: dict[tuple[int, int], SmaGridTrial] = {}
    for trial in collected:
        key = (trial.fast_period, trial.slow_period)
        existing = unique.get(key)
        if existing is None or trial.score > existing.score:
            unique[key] = trial

    trials = sorted(unique.values(), key=lambda item: item.score, reverse=True)
    return trials
