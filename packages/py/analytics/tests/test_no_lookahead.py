"""Anti-look-ahead (P0.1): ningún fill ocurre en la barra donde nace la señal.

El motor H0 (``run_backtest``) y los grids H0 (SMA/RSI/MACD) deben ejecutar las
señales al precio de apertura de la barra siguiente (``next_open``, ``open[t+1]``)
y nunca al cierre de la barra de señal (same-bar). Una señal en la última barra
no se ejecuta.
"""

from __future__ import annotations

import math

from bolsa_analytics.backtest import BacktestBarInput, run_backtest
from bolsa_analytics.optimize.macd_grid import run_macd_signal_cross_grid
from bolsa_analytics.optimize.rsi_grid import run_rsi_mean_reversion_grid
from bolsa_analytics.optimize.sma_grid import run_sma_grid_search

_ENTRY_DEFINITION = {
    "entries": {
        "operator": "all",
        "rules": [
            {
                "type": "indicator_cross",
                "leftSpec": {"definitionId": "sma", "parameters": {"period": 10}},
                "rightSpec": {"definitionId": "sma", "parameters": {"period": 30}},
                "direction": "bullish",
                "signalKind": "entry_long",
            }
        ],
    },
    "exits": {
        "operator": "all",
        "rules": [
            {
                "type": "indicator_cross",
                "leftSpec": {"definitionId": "sma", "parameters": {"period": 10}},
                "rightSpec": {"definitionId": "sma", "parameters": {"period": 30}},
                "direction": "bearish",
                "signalKind": "exit",
            }
        ],
    },
    "indicatorSpecs": [
        {"definitionId": "sma", "parameters": {"period": 10}},
        {"definitionId": "sma", "parameters": {"period": 30}},
    ],
}


def _motor_bars(jump_index: int, n: int = 60) -> list[BacktestBarInput]:
    """Serie con un salto brusco en ``jump_index`` (open ≠ close en todas las barras).

    Antes de ``jump_index`` la serie es plana (SMA10 ≈ SMA30 ≈ 100) y tras el salto
    el SMA10 > SMA30: la cruce bullish ocurre exactamente en la barra ``jump_index``.
    El ``open`` toma valores grandes y distintos del ``close`` para detectar de forma
    inequívoca qué precio se usó en el fill.
    """
    return [
        BacktestBarInput(
            timestamp=f"2024-01-{i + 1:02d}",
            open=1000.0 + i,
            high=1100.0 + i,
            low=990.0 + i,
            close=100.0 if i < jump_index else 200.0,
            volume=1000 + i,
        )
        for i in range(n)
    ]


def test_run_backtest_fills_at_next_open_not_signal_bar() -> None:
    bars = _motor_bars(jump_index=30)
    result = run_backtest(
        bars,
        "sma_crossover",
        10_000.0,
        strategy_definition=_ENTRY_DEFINITION,
    )
    assert result.trade_count >= 1
    entry = next(t for t in result.trades if t.type == "buy")
    # La señal nace en la barra 30 (cruce bullish). El fill cae en open[31].
    assert entry.timestamp == bars[31].timestamp
    assert bars[31].timestamp > bars[30].timestamp
    assert entry.price == bars[31].open
    # Ningún fill puede ocurrir en la propia barra de señal, ni llenarse al close.
    assert all(t.timestamp != bars[30].timestamp for t in result.trades)
    assert all(t.price != bars[30].close and t.price != bars[31].close for t in result.trades)


def test_run_backtest_last_bar_signal_does_not_execute() -> None:
    # El único cruce ocurre en la última barra (index 59): no hay open[60], no se ejecuta.
    bars = _motor_bars(jump_index=59)
    result = run_backtest(
        bars,
        "sma_crossover",
        10_000.0,
        strategy_definition=_ENTRY_DEFINITION,
    )
    assert result.trade_count == 0
    assert result.trades == []


def _grid_bars_pair() -> tuple[list[BacktestBarInput], list[BacktestBarInput]]:
    """Dos sets con close idéntico pero open distinto: prueban fill por open en grids.

    La serie es una onda tipo triángulo con oscilaciones bruscas que ggeneran cruces en
    los tres families (SMA, RSI y MACD). Un open distinto (1.5x) cambia el precio de
    fill de next_open y, por tanto, las métricas; si el grid llenara al close de la
    propia barra (same-bar), ambos sets con close idéntico arrojarían los mismos
    resultados.
    """

    def make(open_scale: float) -> list[BacktestBarInput]:
        bars: list[BacktestBarInput] = []
        for i in range(120):
            close = round(100.0 + 25.0 * math.sin(i / 5.0), 4)
            bars.append(
                BacktestBarInput(
                    timestamp=f"2025-{i // 28 + 1:02d}-{(i % 28) + 1:02d}",
                    open=round(close * open_scale, 4),
                    high=close + 5.0,
                    low=close - 5.0,
                    close=close,
                    volume=1000 + i,
                )
            )
        return bars

    return make(1.0), make(1.5)


def test_sma_grid_uses_open_for_next_open_fill() -> None:
    a, b = _grid_bars_pair()
    ra = run_sma_grid_search(a, fast_periods=[10], slow_periods=[30], max_trials=4)
    rb = run_sma_grid_search(b, fast_periods=[10], slow_periods=[30], max_trials=4)
    assert ra and rb
    assert max(t.trade_count for t in ra) > 0  # el grid genera operaciones (no vacuo)
    # Con next_open el open cambia el fill → los resultados difieren (si fuera fill a
    # close same-bar, ambos sets, con close idéntico, arrojarían el mismo resultado).
    def _signature(trials: list) -> tuple:
        return tuple((t.fast_period, t.slow_period, t.trade_count, round(t.total_return_pct, 6)) for t in trials)

    assert _signature(ra) != _signature(rb)


def test_rsi_grid_uses_open_for_next_open_fill() -> None:
    a, b = _grid_bars_pair()
    ra = run_rsi_mean_reversion_grid(a, max_trials=4)
    rb = run_rsi_mean_reversion_grid(b, max_trials=4)
    assert ra and rb
    assert max(t.trade_count for t in ra) > 0

    def _signature(trials: list) -> tuple:
        return tuple((t.trade_count, round(t.total_return_pct, 6)) for t in trials)

    assert _signature(ra) != _signature(rb)


def test_macd_grid_uses_open_for_next_open_fill() -> None:
    a, b = _grid_bars_pair()
    ra = run_macd_signal_cross_grid(a, max_trials=4)
    rb = run_macd_signal_cross_grid(b, max_trials=4)
    assert ra and rb
    assert max(t.trade_count for t in ra) > 0

    def _signature(trials: list) -> tuple:
        return tuple((t.trade_count, round(t.total_return_pct, 6)) for t in trials)

    assert _signature(ra) != _signature(rb)
