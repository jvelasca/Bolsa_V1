"""Motor de backtest H0 (barra a barra, presets / rules).

Costes v1 fijos en bps; v2 opcional vía ``CostModelV2Config`` (gated).
Convención anualización: 252 sesiones/año.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Literal

from bolsa_analytics.cost_model_v2 import (
    CostModelV2Config,
    median_volume,
    resolve_bar_costs_v2,
)
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.preset_catalog import (
    is_valid_preset_key,
    strategy_definition_from_preset,
)
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
    """Barra OHLCV mínima para el motor (timestamp ISO + close obligatorio)."""

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


#: Fricción de referencia del laboratorio: ``2 × (10 + 5) + 2 = 32 bps`` ida y vuelta.
#: Coincide con ``bolsa_application.baseline_arms.BaselineCosts`` (10/5/2) y con el suelo de
#: ``BASELINE_THRESHOLDS['minRoundTripCostBps']`` (22 bps). Es lo que una simulación LAB debe
#: cobrarse cuando nadie declara otra cosa: optimizar con fricción cero produce campeones que
#: pierden en cuanto se pagan comisiones.
REFERENCE_COSTS = BacktestCostModel(commission_bps=10, slippage_bps=5, spread_bps=2)


@dataclass(frozen=True, slots=True)
class BacktestRiskPolicy:
    """Alineación opcional con TradingPolicy live (sizing por riesgo + stop)."""

    max_risk_per_trade_pct: float = 1.0
    stop_loss_pct: float = 5.0


@dataclass(frozen=True, slots=True)
class BacktestTradeResult:
    """Fill simulado (buy/sell) con equity tras la operación."""

    type: Literal["buy", "sell"]
    timestamp: str
    price: float
    quantity: float
    equity_after: float
    commission: float = 0.0
    reason: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BacktestEquityPoint:
    """Punto de la curva de equity al cierre de barra."""

    timestamp: str
    equity: float


@dataclass(frozen=True, slots=True)
class BacktestEngineResult:
    """Resultado completo del motor (métricas + trades + equity curve)."""

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


def bps_frac(bps: int) -> float:
    """Bps → fracción (1 bps = 1/10 000)."""
    return bps / 10_000.0


def buy_fill_price(mid: float, costs: BacktestCostModel) -> float:
    """Precio de compra con deslizamiento y media horquilla."""
    return mid * (1.0 + bps_frac(costs.slippage_bps) + bps_frac(costs.spread_bps) / 2.0)


def sell_fill_price(mid: float, costs: BacktestCostModel) -> float:
    """Precio de venta con deslizamiento y media horquilla."""
    return mid * (1.0 - bps_frac(costs.slippage_bps) - bps_frac(costs.spread_bps) / 2.0)


def commission_for(notional: float, costs: BacktestCostModel) -> float:
    """Comisión en moneda de la cuenta para un nocional dado."""
    return abs(notional) * bps_frac(costs.commission_bps)


def round_trip_cost_bps(costs: BacktestCostModel) -> float:
    """Coste de ida y vuelta en bps: ``2 × (comisión + deslizamiento) + horquilla``.

    Misma convención que ``CampaignCosts``/``BaselineCosts`` (el spread se paga medio
    por lado). Es el número que declara la fricción asumida por una simulación.
    """
    return 2.0 * (costs.commission_bps + costs.slippage_bps) + costs.spread_bps


# Alias privados por compatibilidad con llamadores internos y exports previos.
_bps_frac = bps_frac
_buy_fill_price = buy_fill_price
_sell_fill_price = sell_fill_price
_commission = commission_for


def _bar_costs(
    base: BacktestCostModel,
    *,
    cost_v2: CostModelV2Config | None,
    volume: float,
    median_vol: float | None,
) -> BacktestCostModel:
    if cost_v2 is None or not cost_v2.enabled:
        return base
    commission, slippage, spread = resolve_bar_costs_v2(
        cost_v2, volume=volume, median_vol=median_vol
    )
    return BacktestCostModel(
        commission_bps=commission,
        slippage_bps=slippage,
        spread_bps=spread,
    )


def _compute_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0

    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            drawdown = ((peak - equity) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)

    return max_drawdown


def _round_trip_pnls(entry_costs: list[float], exit_proceeds: list[float]) -> list[float]:
    return [exit - entry for entry, exit in zip(entry_costs, exit_proceeds, strict=False)]


def compute_buy_hold_return_pct(
    first_close: float,
    last_close: float,
    *,
    costs: BacktestCostModel | None = None,
) -> float:
    """Buy & hold de la ventana, comparable con la estrategia.

    Sin ``costs`` es el suelo de referencia sin fricción (comportamiento histórico). Con
    ``costs`` aplica la **misma** convención que la estrategia —compra al primer cierre con
    deslizamiento y horquilla, venta al último con ambas y comisión en cada lado—, de modo que
    ``exceso = estrategia − benchmark`` compara dos cosas con el mismo coste.
    """
    if first_close <= 0:
        return 0.0
    if costs is None:
        return ((last_close - first_close) / first_close) * 100.0
    entry = buy_fill_price(first_close, costs)
    exit_ = sell_fill_price(last_close, costs)
    entry_cost = entry * (1.0 + bps_frac(costs.commission_bps))
    exit_proceeds = exit_ * (1.0 - bps_frac(costs.commission_bps))
    if entry_cost <= 0:
        return 0.0
    return ((exit_proceeds - entry_cost) / entry_cost) * 100.0


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
    round_trip_entry_costs: list[float] | None = None,
    round_trip_risk: list[float] | None = None,
    buy_hold_return_pct: float | None = None,
) -> dict[str, Any]:
    """Homogeneous IS payload for human backtests and grid trials (ledger).

    **Base declarada del retorno.** Si ``costs`` llega, la curva de equity ya incorpora la
    fricción y ``totalReturnPct`` **es neto**: se publica además como ``netReturnPct``. Si
    ``costs`` es ``None`` la simulación es bruta y ``netReturnPct`` queda ``None`` — un hueco
    declarado, nunca un cero que aparente medición.

    **Expectancy.** ``expectancyCurrency`` es la media de PnL neto por round trip.
    ``expectancyPct`` normaliza por el capital comprometido en cada operación y solo se emite
    con ``round_trip_entry_costs``. ``expectancyR`` exige una unidad de riesgo **declarada**
    por operación (``round_trip_risk``); sin ella es ``None`` — no se fabrica dividiendo por
    el propio PnL, que solo daría el signo.
    """
    resolved_costs = costs or BacktestCostModel()
    costs_declared = costs is not None
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

    # --- Base del retorno y expectativa por operación (P1) -------------------------------
    net_return_pct: float | None = total_return_pct if costs_declared else None

    expectancy_currency: float | None = mean(round_trip_pnls) if round_trip_pnls else None

    expectancy_pct: float | None = None
    if round_trip_pnls and round_trip_entry_costs:
        per_trade = [
            (pnl / entry) * 100.0
            for pnl, entry in zip(round_trip_pnls, round_trip_entry_costs, strict=False)
            if entry > 0
        ]
        if per_trade:
            expectancy_pct = mean(per_trade)

    expectancy_r: float | None = None
    if round_trip_pnls and round_trip_risk:
        per_r = [
            pnl / risk
            for pnl, risk in zip(round_trip_pnls, round_trip_risk, strict=False)
            if risk > 0
        ]
        if per_r:
            expectancy_r = mean(per_r)

    excess_return_pct: float | None = None
    if net_return_pct is not None and buy_hold_return_pct is not None:
        excess_return_pct = net_return_pct - buy_hold_return_pct

    metrics: dict[str, Any] = {
        "totalReturnPct": round(total_return_pct, 6),
        "netReturnPct": None if net_return_pct is None else round(net_return_pct, 6),
        "returnBasis": "net" if costs_declared else "gross",
        "buyHoldReturnPct": (
            None if buy_hold_return_pct is None else round(buy_hold_return_pct, 6)
        ),
        "excessReturnPct": (
            None if excess_return_pct is None else round(excess_return_pct, 6)
        ),
        "expectancyCurrency": (
            None if expectancy_currency is None else round(expectancy_currency, 6)
        ),
        "expectancyPct": None if expectancy_pct is None else round(expectancy_pct, 6),
        "expectancyR": None if expectancy_r is None else round(expectancy_r, 6),
        "netTradeCount": closed,
        "roundTripCostBps": (
            round(round_trip_cost_bps(resolved_costs), 6) if costs_declared else None
        ),
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
    cost_v2: CostModelV2Config | None = None,
    strategy_definition: dict[str, Any] | None = None,
    execution_model: Literal["next_open"] = "next_open",
    risk_policy: BacktestRiskPolicy | None = None,
) -> BacktestEngineResult:
    """Ejecuta un backtest H0 sobre ``bars`` con preset o ``strategy_definition``.

    Si ``cost_v2`` está enabled, ajusta slippage/spread por barra; si no, usa bps fijos.

    ``execution_model`` fija la política de fill. Único valor soportado: ``next_open``
    (inmutable para 1D, D1): una señal calculada al cierre de la barra ``t`` se ejecuta
    al precio de apertura de la barra ``t+1`` (``open[t+1]``). Si la señal cae en la
    última barra, no se ejecuta. Esto elimina el look-ahead/same-bar (P0.1).
    """
    if not bars:
        raise ValueError("No hay barras OHLCV para el backtest")
    if initial_cash <= 0:
        raise ValueError("El capital inicial debe ser mayor que cero")

    resolved_costs = costs or BacktestCostModel(
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        spread_bps=spread_bps,
    )
    median_vol = (
        median_volume([float(b.volume or 0.0) for b in bars])
        if cost_v2 is not None and cost_v2.enabled
        else None
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
    structural_stop: float | None = None

    for i, bar in enumerate(bars):
        kind = signal_by_index.get(i - 1)
        signal: Literal["buy", "sell"] | None = None
        reason: dict[str, Any] | None = None
        signal_index = i - 1
        if kind == "entry_long":
            signal = "buy"
            reason = explain_signal_at_bar(
                strategy_def,
                index=signal_index,
                context=context,
                closes=closes,
                side="entries",
            )
        elif kind == "exit":
            signal = "sell"
            reason = explain_signal_at_bar(
                strategy_def,
                index=signal_index,
                context=context,
                closes=closes,
                side="exits",
            )

        fill_price = float(bar.open if bar.open is not None else bar.close)
        close_price = float(bar.close)
        bar_low = float(bar.low if bar.low is not None else bar.close)
        bar_costs = _bar_costs(
            resolved_costs,
            cost_v2=cost_v2,
            volume=float(bar.volume or 0.0),
            median_vol=median_vol,
        )

        if (
            shares > 0
            and structural_stop is not None
            and risk_policy is not None
            and bar_low <= structural_stop
        ):
            signal = "sell"
            reason = {"stop_loss": structural_stop}

        if signal == "buy" and shares == 0:
            fill = _buy_fill_price(fill_price, bar_costs)
            cost_per_share = fill * (1.0 + _bps_frac(bar_costs.commission_bps))
            if risk_policy is not None and risk_policy.stop_loss_pct > 0:
                risk_budget = cash * (risk_policy.max_risk_per_trade_pct / 100.0)
                risk_per_share = fill * (risk_policy.stop_loss_pct / 100.0)
                quantity = int(risk_budget / risk_per_share) if risk_per_share > 0 else 0
                structural_stop = fill * (1.0 - risk_policy.stop_loss_pct / 100.0)
            else:
                quantity = int(cash // cost_per_share) if cost_per_share > 0 else 0
                structural_stop = None
            if quantity > 0:
                notional = quantity * fill
                commission = _commission(notional, bar_costs)
                cash -= notional + commission
                shares = float(quantity)
                total_commission += commission
                open_entry_cost = notional + commission
                equity_after = cash + shares * close_price
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
            fill = _sell_fill_price(fill_price, bar_costs)
            notional = shares * fill
            commission = _commission(notional, bar_costs)
            cash += notional - commission
            quantity = shares
            shares = 0.0
            structural_stop = None
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
            BacktestEquityPoint(timestamp=bar.timestamp, equity=cash + shares * close_price),
        )

    final_equity = cash + shares * bars[-1].close
    total_return_pct = ((final_equity - initial_cash) / initial_cash) * 100 if initial_cash > 0 else 0.0
    equity_values = [point.equity for point in equity_curve]
    max_drawdown_pct = _compute_max_drawdown(equity_values)
    round_trips = _round_trip_pnls(entry_costs, exit_proceeds)
    win_count = sum(1 for pnl in round_trips if pnl > 0)
    buy_hold_return_pct = compute_buy_hold_return_pct(
        bars[0].close,
        bars[-1].close,
        costs=resolved_costs,
    )
    is_metrics = _compute_is_metrics(
        equity_values=equity_values,
        initial_cash=initial_cash,
        final_equity=final_equity,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=len(trades),
        round_trip_pnls=round_trips,
        total_commission=total_commission,
        costs=resolved_costs,
        round_trip_entry_costs=entry_costs,
        buy_hold_return_pct=buy_hold_return_pct,
    )
    is_metrics["costModelV2"] = bool(cost_v2 is not None and cost_v2.enabled)

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
