from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Literal

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.preset_catalog import is_valid_preset_key, strategy_definition_from_preset
from bolsa_analytics.signals.preset_rules import enrich_definition_with_preset_rules
from bolsa_analytics.signals.rules_engine import (
    build_indicator_context,
    evaluate_rules_signals,
    explain_signal_at_bar,
)

BacktestStrategyType = str

# Daily bars → 252 trading sessions/year (H0 convention).
_PERIODS_PER_YEAR = 252.0


@dataclass(frozen=True, slots=True)
class BacktestBarInput:
    timestamp: str
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float = 0.0


@dataclass(frozen=True, slots=True)
class BacktestCostModel:
    """Execution costs applied to fills (bps = 1/100 of 1%)."""

    commission_bps: int = 0
    slippage_bps: int = 0
    spread_bps: int = 0

    def __post_init__(self) -> None:
        if self.commission_bps < 0 or self.slippage_bps < 0 or self.spread_bps < 0:
            raise ValueError("Los costes en bps no pueden ser negativos")


@dataclass(frozen=True, slots=True)
class BacktestTradeResult:
    type: Literal["buy", "sell"]
    timestamp: str
    price: float
    quantity: float
    equity_after: float
    commission: float = 0.0
    reason: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BacktestEquityPoint:
    timestamp: str
    equity: float


@dataclass(frozen=True, slots=True)
class BacktestEngineResult:
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_count: int
    trades: list[BacktestTradeResult]
    equity_curve: list[BacktestEquityPoint]
    first_date: str
    last_date: str
    bar_count: int
    is_metrics: dict[str, Any]


def _bps_frac(bps: int) -> float:
    return bps / 10_000.0


def _buy_fill_price(mid: float, costs: BacktestCostModel) -> float:
    return mid * (1.0 + _bps_frac(costs.slippage_bps) + _bps_frac(costs.spread_bps) / 2.0)


def _sell_fill_price(mid: float, costs: BacktestCostModel) -> float:
    return mid * (1.0 - _bps_frac(costs.slippage_bps) - _bps_frac(costs.spread_bps) / 2.0)


def _commission(notional: float, costs: BacktestCostModel) -> float:
    return abs(notional) * _bps_frac(costs.commission_bps)


def _compute_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0

    for equity in equity_curve:
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = ((peak - equity) / peak) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    return max_drawdown


def _round_trip_pnls(entry_costs: list[float], exit_proceeds: list[float]) -> list[float]:
    return [exit - entry for entry, exit in zip(entry_costs, exit_proceeds, strict=False)]


def compute_buy_hold_return_pct(first_close: float, last_close: float) -> float:
    """Naive buy & hold over the window (no costs): reference floor for IA / research."""
    if first_close <= 0:
        return 0.0
    return ((last_close - first_close) / first_close) * 100.0


def compute_is_metrics(
    *,
    equity_values: list[float],
    initial_cash: float,
    final_equity: float,
    max_drawdown_pct: float,
    trade_count: int,
    round_trip_pnls: list[float],
    total_commission: float = 0.0,
    costs: BacktestCostModel | None = None,
) -> dict[str, Any]:
    """Homogeneous IS payload for human backtests and grid trials (ledger)."""
    resolved_costs = costs or BacktestCostModel()
    total_return_pct = ((final_equity - initial_cash) / initial_cash) * 100 if initial_cash > 0 else 0.0
    closed = len(round_trip_pnls)
    wins = sum(1 for pnl in round_trip_pnls if pnl > 0)
    losses = sum(1 for pnl in round_trip_pnls if pnl < 0)
    gross_profit = sum(pnl for pnl in round_trip_pnls if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in round_trip_pnls if pnl < 0))
    win_rate = (wins / closed) if closed > 0 else None
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (None if gross_profit == 0 else float("inf"))

    period_returns: list[float] = []
    for i in range(1, len(equity_values)):
        prev = equity_values[i - 1]
        if prev > 0:
            period_returns.append(equity_values[i] / prev - 1.0)

    sharpe: float | None = None
    sortino: float | None = None
    if len(period_returns) >= 2:
        avg = mean(period_returns)
        vol = pstdev(period_returns)
        if vol > 0:
            sharpe = (avg / vol) * sqrt(_PERIODS_PER_YEAR)
        downside = [r for r in period_returns if r < 0]
        if len(downside) >= 1:
            down_vol = pstdev(downside) if len(downside) > 1 else abs(downside[0])
            if down_vol > 0:
                sortino = (avg / down_vol) * sqrt(_PERIODS_PER_YEAR)

    n_periods = max(len(equity_values) - 1, 0)
    if n_periods > 0 and initial_cash > 0 and final_equity > 0:
        ann_return = (final_equity / initial_cash) ** (_PERIODS_PER_YEAR / n_periods) - 1.0
    else:
        ann_return = total_return_pct / 100.0

    calmar: float | None = None
    if max_drawdown_pct > 0:
        calmar = ann_return / (max_drawdown_pct / 100.0)

    metrics: dict[str, Any] = {
        "totalReturnPct": round(total_return_pct, 6),
        "maxDrawdownPct": round(max_drawdown_pct, 6),
        "sharpeRatio": None if sharpe is None else round(sharpe, 6),
        "sortinoRatio": None if sortino is None else round(sortino, 6),
        "calmarRatio": None if calmar is None else round(calmar, 6),
        "winRate": None if win_rate is None else round(win_rate, 6),
        "profitFactor": (
            None
            if profit_factor is None
            else (round(profit_factor, 6) if profit_factor != float("inf") else None)
        ),
        "tradeCount": trade_count,
        "closedTrades": closed,
        "winCount": wins,
        "lossCount": losses,
        "totalCommission": round(total_commission, 6),
        "commissionBps": resolved_costs.commission_bps,
        "slippageBps": resolved_costs.slippage_bps,
        "spreadBps": resolved_costs.spread_bps,
    }
    return metrics


# Backward-compatible alias (grids / older call sites).
_compute_is_metrics = compute_is_metrics


def run_backtest(
    bars: list[BacktestBarInput],
    strategy_type: BacktestStrategyType,
    initial_cash: float,
    *,
    costs: BacktestCostModel | None = None,
    commission_bps: int = 0,
    slippage_bps: int = 0,
    spread_bps: int = 0,
    strategy_definition: dict[str, Any] | None = None,
) -> BacktestEngineResult:
    if not bars:
        raise ValueError("No hay barras OHLCV para el backtest")
    if initial_cash <= 0:
        raise ValueError("El capital inicial debe ser mayor que cero")

    resolved_costs = costs or BacktestCostModel(
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        spread_bps=spread_bps,
    )

    if not is_valid_preset_key(strategy_type):
        raise ValueError(f"Unsupported strategy preset: {strategy_type}")

    timestamps = [bar.timestamp for bar in bars]
    closes = [bar.close for bar in bars]
    # Prefer a persisted definition (e.g. optimized SMA periods) over the builtin preset.
    definition = (
        dict(strategy_definition)
        if isinstance(strategy_definition, dict) and strategy_definition
        else strategy_definition_from_preset(strategy_type, ["backtest"])
    )
    strategy_def = enrich_definition_with_preset_rules(definition)
    ohlcv_bars = [
        OhlcvBar(
            timestamp=bar.timestamp,
            open=bar.open if bar.open is not None else bar.close,
            high=bar.high if bar.high is not None else bar.close,
            low=bar.low if bar.low is not None else bar.close,
            close=bar.close,
            volume=float(bar.volume or 0.0),
        )
        for bar in bars
    ]
    context = build_indicator_context(ohlcv_bars, strategy_def.get("indicatorSpecs") or [])
    gated_signals = evaluate_rules_signals(
        strategy_def, timestamps, closes, mode="gated", context=context
    )

    signal_by_index = {event.bar_index: event.kind for event in gated_signals}

    cash = initial_cash
    shares = 0.0
    trades: list[BacktestTradeResult] = []
    equity_curve: list[BacktestEquityPoint] = []
    entry_costs: list[float] = []
    exit_proceeds: list[float] = []
    open_entry_cost: float | None = None
    total_commission = 0.0

    for i, bar in enumerate(bars):
        mid = bar.close
        kind = signal_by_index.get(i)
        signal: Literal["buy", "sell"] | None = None
        reason: dict[str, Any] | None = None
        if kind == "entry_long":
            signal = "buy"
            reason = explain_signal_at_bar(
                strategy_def, index=i, context=context, closes=closes, side="entries"
            )
        elif kind == "exit":
            signal = "sell"
            reason = explain_signal_at_bar(
                strategy_def, index=i, context=context, closes=closes, side="exits"
            )

        if signal == "buy" and shares == 0:
            fill = _buy_fill_price(mid, resolved_costs)
            cost_per_share = fill * (1.0 + _bps_frac(resolved_costs.commission_bps))
            quantity = int(cash // cost_per_share) if cost_per_share > 0 else 0
            if quantity > 0:
                notional = quantity * fill
                commission = _commission(notional, resolved_costs)
                cash -= notional + commission
                shares = float(quantity)
                total_commission += commission
                open_entry_cost = notional + commission
                equity_after = cash + shares * mid
                trades.append(
                    BacktestTradeResult(
                        type="buy",
                        timestamp=bar.timestamp,
                        price=fill,
                        quantity=float(quantity),
                        equity_after=equity_after,
                        commission=commission,
                        reason=reason,
                    )
                )
        elif signal == "sell" and shares > 0:
            fill = _sell_fill_price(mid, resolved_costs)
            notional = shares * fill
            commission = _commission(notional, resolved_costs)
            cash += notional - commission
            quantity = shares
            shares = 0.0
            total_commission += commission
            if open_entry_cost is not None:
                entry_costs.append(open_entry_cost)
                exit_proceeds.append(notional - commission)
                open_entry_cost = None
            trades.append(
                BacktestTradeResult(
                    type="sell",
                    timestamp=bar.timestamp,
                    price=fill,
                    quantity=quantity,
                    equity_after=cash,
                    commission=commission,
                    reason=reason,
                )
            )

        equity_curve.append(
            BacktestEquityPoint(timestamp=bar.timestamp, equity=cash + shares * mid),
        )

    final_equity = cash + shares * bars[-1].close
    total_return_pct = ((final_equity - initial_cash) / initial_cash) * 100 if initial_cash > 0 else 0.0
    equity_values = [point.equity for point in equity_curve]
    max_drawdown_pct = _compute_max_drawdown(equity_values)
    round_trips = _round_trip_pnls(entry_costs, exit_proceeds)
    win_count = sum(1 for pnl in round_trips if pnl > 0)
    is_metrics = _compute_is_metrics(
        equity_values=equity_values,
        initial_cash=initial_cash,
        final_equity=final_equity,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=len(trades),
        round_trip_pnls=round_trips,
        total_commission=total_commission,
        costs=resolved_costs,
    )
    buy_hold_return_pct = compute_buy_hold_return_pct(bars[0].close, bars[-1].close)
    is_metrics["buyHoldReturnPct"] = round(buy_hold_return_pct, 6)
    is_metrics["excessReturnPct"] = round(total_return_pct - buy_hold_return_pct, 6)

    return BacktestEngineResult(
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=len(trades),
        win_count=win_count,
        trades=trades,
        equity_curve=equity_curve,
        first_date=bars[0].timestamp,
        last_date=bars[-1].timestamp,
        bar_count=len(bars),
        is_metrics=is_metrics,
    )
