"""V2.31 / A11 — grid genérico de reglas declarativas (Discovery).

Los grids H0 existentes (``sma_grid`` / ``rsi_grid`` / ``macd_grid``) implementan
su simulación con features cableadas. Para el DISCOVERY ENGINE necesitamos evaluar
**plantillas declarativas** (``StrategyDefinitionV1`` con ``indicatorSpecs`` +
``entries``/``exits``) sin escribir un grid por indicador.

Este módulo hace exactamente eso: recorre un ``param_space``, materializa la
definición con la ``template`` de la familia y simula la estrategia bar-a-bar con el
motor real de reglas (``evaluate_rules_signals`` en modo ``gated``), reutilizando la
misma contabilidad de equity/drawdown/score que los grids H0.

Causalidad: las señales se evalúan en ``index - 1`` y se ejecutan en el ``open`` de
``index`` (mismo contrato que ``_simulate_sma_crossover``), de modo que no hay
look-ahead. Sin red, sin IA.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.grid_is_metrics import finalize_grid_is_metrics
from bolsa_analytics.signals.rules_engine import build_indicator_context, evaluate_rules_signals

ProgressCallback = Callable[[int, int, float | None], None]

# La plantilla materializa una definición ejecutable desde un punto del grid.
DefinitionTemplate = Callable[[Mapping[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True, slots=True)
class RulesGridTrial:
    """Trial de grid genérico: params del punto + métricas IS/OOS."""

    params: dict[str, Any]
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    score: float
    is_metrics: dict[str, Any] = field(default_factory=dict)
    oos_metrics: dict[str, Any] | None = None


def _simulate_rules_strategy(
    bars: list[BacktestBarInput],
    definition: dict[str, Any],
    *,
    initial_cash: float,
    trade_from_index: int = 0,
    attach_round_trips: bool = False,
    execution_model: Literal["next_open"] = "next_open",
) -> dict[str, Any]:
    """Simula una ``StrategyDefinitionV1`` declarativa bar-a-bar (gated, sin look-ahead)."""
    start = max(0, min(int(trade_from_index), len(bars)))
    timestamps = [bar.timestamp for bar in bars]
    closes = [float(bar.close) for bar in bars]

    # Contexto de indicadores sobre TODAS las barras (causal) y señales gated.
    specs = list(definition.get("indicatorSpecs") or [])
    context = build_indicator_context(
        [
            # El rules_engine reconstruye sus propias OhlcvBar internamente desde
            # timestamps+closes, así que basta con barras sintéticas consistentes.
            _ohlcv_from(bar)
            for bar in bars
        ],
        specs,
    )
    events = evaluate_rules_signals(
        definition,
        timestamps,
        closes,
        mode="gated",
        context=context,
    )
    signal_by_index = {event.bar_index: event.kind for event in events}

    cash = float(initial_cash)
    shares = 0.0
    trades = 0
    peak = float(initial_cash)
    max_drawdown = 0.0
    equity_values: list[float] = []
    entry_costs: list[float] = []
    exit_proceeds: list[float] = []
    open_entry_cost: float | None = None

    for index, bar in enumerate(bars):
        if index < start or index - 1 < start:
            continue
        kind = signal_by_index.get(index - 1)
        fill_price = float(bar.open if bar.open is not None else bar.close)
        close_price = float(bar.close)
        if kind == "entry_long" and shares == 0 and cash >= fill_price:
            quantity = int(cash // fill_price)
            if quantity > 0:
                cost = quantity * fill_price
                cash -= cost
                shares = float(quantity)
                trades += 1
                open_entry_cost = cost
        elif kind == "exit" and shares > 0:
            proceeds = shares * fill_price
            cash += proceeds
            if open_entry_cost is not None:
                entry_costs.append(open_entry_cost)
                exit_proceeds.append(proceeds)
                open_entry_cost = None
            shares = 0.0
            trades += 1

        equity = cash + shares * close_price
        equity_values.append(equity)
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, ((peak - equity) / peak) * 100)

    if not equity_values or trades == 0:
        # Sin operaciones no hay evidencia: el LAB lo tratará como "sin trials".
        raise ValueError("la plantilla no generó operaciones en la ventana")

    return finalize_grid_is_metrics(
        equity_values=equity_values,
        initial_cash=initial_cash,
        max_drawdown_pct=max_drawdown,
        trade_count=trades,
        round_trip_pnls=[
            exit_ - entry for entry, exit_ in zip(entry_costs, exit_proceeds, strict=False)
        ],
        attach_round_trips=attach_round_trips,
    )


def _ohlcv_from(bar: BacktestBarInput) -> Any:
    """Adapta ``BacktestBarInput`` a la ``OhlcvBar`` que consume el rules engine."""
    from bolsa_analytics.indicators.compute import OhlcvBar

    return OhlcvBar(
        timestamp=str(bar.timestamp),
        open=float(bar.open if bar.open is not None else bar.close),
        high=float(bar.high if bar.high is not None else bar.close),
        low=float(bar.low if bar.low is not None else bar.close),
        close=float(bar.close),
        volume=float(bar.volume or 0.0),
    )


def run_rules_grid_search(
    bars: list[BacktestBarInput],
    *,
    param_points: Sequence[Mapping[str, Any]],
    template: DefinitionTemplate,
    initial_cash: float = 10000.0,
    max_trials: int = 200,
    on_progress: ProgressCallback | None = None,
    execution_model: Literal["next_open"] = "next_open",
) -> list[RulesGridTrial]:
    """Recorre ``param_points`` y evalúa cada definición materializada.

    Fail-closed: un punto cuya plantilla devuelve ``None`` o que no genera
    operaciones se descarta (no se inventa evidencia). Devuelve los trials ordenados
    por ``score`` descendente.
    """
    if not bars:
        raise ValueError("bars must not be empty")

    trials: list[RulesGridTrial] = []
    total = max(1, min(len(param_points), int(max_trials)))
    if on_progress is not None:
        on_progress(0, total, None)
    best_score: float | None = None
    for point in param_points:
        if len(trials) >= max_trials:
            break
        definition = template(point)
        if definition is None:
            continue
        try:
            metrics = _simulate_rules_strategy(
                bars,
                definition,
                initial_cash=initial_cash,
                execution_model=execution_model,
            )
        except ValueError:
            continue
        score = float(metrics["score"])
        trials.append(
            RulesGridTrial(
                params=dict(point),
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
