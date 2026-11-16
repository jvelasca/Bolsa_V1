"""RSI mean-reversion parameter grid (Campaign 2) — bar-by-bar, no future peek."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from bolsa_analytics.backtest import (
    REFERENCE_COSTS,
    BacktestBarInput,
    BacktestCostModel,
    bps_frac,
    buy_fill_price,
    commission_for,
    sell_fill_price,
)
from bolsa_analytics.indicators.legacy import rsi
from bolsa_analytics.optimize.grid_is_metrics import (
    finalize_grid_is_metrics,
    grid_buy_hold_return_pct,
)
from bolsa_analytics.warmup_matrix import assert_grid_warmup

ProgressCallback = Callable[[int, int, float | None], None]


@dataclass(frozen=True, slots=True)
class RsiGridTrial:
    """Trial de grid: Rsi Grid Trial."""
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
    execution_model: Literal["next_open"] = "next_open",
    costs: BacktestCostModel | None = None,
) -> dict[str, Any]:
    """RSI MR sim. Indicator uses all bars; trading starts at ``trade_from_index``.

    ``costs`` aplica la convención de ``run_backtest`` (deslizamiento + media horquilla en el
    fill, comisión sobre el nocional). Con ``costs=None`` la simulación es bruta y el payload
    lo declara.
    """
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
    total_commission = 0.0
    peak = initial_cash
    max_drawdown = 0.0
    equity_values: list[float] = []
    entry_costs: list[float] = []
    exit_proceeds: list[float] = []
    open_entry_cost: float | None = None
    curve_start: int | None = None

    for index, bar in enumerate(bars):
        if index < start:
            continue
        if index - 1 < start:
            continue
        value = series[index - 1]
        mid_price = float(bar.open if bar.open is not None else bar.close)
        close_price = float(bar.close)
        if value is not None:
            if shares == 0 and value < oversold:
                fill = buy_fill_price(mid_price, costs) if costs is not None else mid_price
                commission_frac = bps_frac(costs.commission_bps) if costs is not None else 0.0
                cost_per_share = fill * (1.0 + commission_frac)
                quantity = int(cash // cost_per_share) if cost_per_share > 0 else 0
                if quantity > 0:
                    notional = quantity * fill
                    commission = commission_for(notional, costs) if costs is not None else 0.0
                    cash -= notional + commission
                    shares = float(quantity)
                    trades += 1
                    total_commission += commission
                    open_entry_cost = notional + commission
            elif shares > 0 and value > overbought:
                fill = sell_fill_price(mid_price, costs) if costs is not None else mid_price
                notional = shares * fill
                commission = commission_for(notional, costs) if costs is not None else 0.0
                cash += notional - commission
                total_commission += commission
                if open_entry_cost is not None:
                    entry_costs.append(open_entry_cost)
                    exit_proceeds.append(notional - commission)
                    open_entry_cost = None
                shares = 0.0
                trades += 1

        equity = cash + shares * close_price
        equity_values.append(equity)
        if curve_start is None:
            curve_start = index
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
        costs=costs,
        total_commission=total_commission,
        round_trip_entry_costs=entry_costs,
        buy_hold_return_pct=grid_buy_hold_return_pct(
            bars, start=curve_start if curve_start is not None else start, costs=costs
        ),
    )


def estimate_rsi_grid_trial_total(
    periods: list[int],
    oversold_levels: list[float],
    overbought_levels: list[float],
    *,
    max_trials: int = 25,
) -> int:
    """Estima ``rsi_grid_trial_total``."""
    count = 0
    for _period in periods:
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
    execution_model: Literal["next_open"] = "next_open",
    costs: BacktestCostModel | None = None,
) -> list[RsiGridTrial]:
    """Ejecuta ``rsi_mean_reversion_grid``.

    ``costs=None`` resuelve a :data:`~bolsa_analytics.backtest.REFERENCE_COSTS`: la rejilla
    mide neto por defecto. ``BacktestCostModel()`` fuerza bruto declarado (0 bps).
    """
    if not bars:
        raise ValueError("bars must not be empty")
    resolved_costs = costs if costs is not None else REFERENCE_COSTS

    resolved_periods = periods or [10, 12, 14, 16, 18, 20]
    resolved_os = oversold_levels or [20.0, 25.0, 30.0, 35.0]
    resolved_ob = overbought_levels or [65.0, 70.0, 75.0, 80.0]
    assert_grid_warmup(
        "rsi",
        len(bars),
        ({"period": period} for period in resolved_periods),
    )
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
                        execution_model=execution_model,
                        costs=resolved_costs,
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
