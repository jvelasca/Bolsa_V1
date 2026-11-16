"""RD-3 — grid search SMA crossover (stub previo a VectorBT + Optuna)."""

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
    run_backtest,
    sell_fill_price,
)
from bolsa_analytics.indicators.legacy import sma
from bolsa_analytics.optimize.grid_is_metrics import (
    finalize_grid_is_metrics,
    grid_buy_hold_return_pct,
)
from bolsa_analytics.signals.evaluate import PresetFeatureSeries, evaluate_preset_signals_gated
from bolsa_analytics.warmup_matrix import assert_grid_warmup

ProgressCallback = Callable[[int, int, float | None], None]


@dataclass(frozen=True, slots=True)
class SmaGridTrial:
    """Trial de grid: Sma Grid Trial."""
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
    execution_model: Literal["next_open"] = "next_open",
    costs: BacktestCostModel | None = None,
) -> dict[str, Any]:
    """Simulate SMA cross. Indicators use all bars; trading starts at ``trade_from_index``.

    ``costs`` sigue la convención de ``run_backtest``: deslizamiento + media horquilla en el
    precio de ejecución y comisión sobre el nocional. Con ``costs=None`` la simulación es
    bruta, igual que antes de RD-1, y el payload lo declara.
    """
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
        kind = signal_by_index.get(index - 1)
        if index - 1 < start:
            continue
        mid_price = float(bar.open if bar.open is not None else bar.close)
        close_price = float(bar.close)
        if kind == "entry_long" and shares == 0:
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
        elif kind == "exit" and shares > 0:
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


def estimate_sma_grid_trial_total(
    fast_periods: list[int],
    slow_periods: list[int],
    *,
    max_trials: int = 200,
) -> int:
    """Estima ``sma_grid_trial_total``."""
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
    execution_model: Literal["next_open"] = "next_open",
    costs: BacktestCostModel | None = None,
) -> list[SmaGridTrial]:
    """Ejecuta ``sma_grid_search``.

    ``costs=None`` resuelve a :data:`~bolsa_analytics.backtest.REFERENCE_COSTS` (32 bps ida y
    vuelta): el LAB mide **neto por defecto**. Para una simulación bruta declarada, pasar
    ``BacktestCostModel()`` — el payload lo rotulará con 0 bps y el gate P1 lo rechazará.
    """
    if not bars:
        raise ValueError("bars must not be empty")
    resolved_costs = costs if costs is not None else REFERENCE_COSTS

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
                metrics = _simulate_sma_crossover(
                    bars,
                    fast,
                    slow,
                    initial_cash,
                    execution_model=execution_model,
                    costs=resolved_costs,
                )
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
    *,
    costs: BacktestCostModel | None = None,
) -> SmaGridTrial:
    """Ejecuta ``baseline_preset_backtest`` con el motor real de reglas (H0).

    ``costs=None`` resuelve a :data:`~bolsa_analytics.backtest.REFERENCE_COSTS`, la misma
    fricción que los trials: el baseline contra el que se compara el campeón no puede ser más
    barato que el campeón.
    """
    result = run_backtest(
        bars,
        "sma_crossover",
        initial_cash,
        costs=costs if costs is not None else REFERENCE_COSTS,
    )
    metrics = {**result.is_metrics}
    net_return = metrics.get("netReturnPct")
    basis = "net" if net_return is not None else "gross"
    ranking_return = float(net_return) if net_return is not None else float(metrics["totalReturnPct"])
    score = ranking_return - float(metrics["maxDrawdownPct"]) * 0.25
    metrics["score"] = round(score, 6)
    metrics["scoreBasis"] = basis
    return SmaGridTrial(
        fast_period=20,
        slow_period=50,
        total_return_pct=result.total_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        trade_count=result.trade_count,
        score=round(score, 4),
        is_metrics=metrics,
    )
