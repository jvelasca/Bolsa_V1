"""V2.31 / A11 — tests del grid genérico de reglas declarativas (Discovery).

Certifica que ``run_rules_grid_search`` evalúa plantillas ``StrategyDefinitionV1``
sobre barras con el motor de reglas real, que los trials salen ordenados por score y
que es fail-closed (plantillas que no materializan o no generan operaciones no
inventan evidencia).
"""

from __future__ import annotations

import math

import pytest

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.rules_grid import run_rules_grid_search


def _cycle_bars(count: int = 300) -> list[BacktestBarInput]:
    """Serie con tendencia + ciclo: dispara cruces de SMA y osciladores."""
    bars: list[BacktestBarInput] = []
    for i in range(count):
        price = 100 + 20 * math.sin(i / 12.0) + i * 0.05
        bars.append(
            BacktestBarInput(
                timestamp=f"2026-{i:04d}",
                close=price,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                volume=1000.0,
            )
        )
    return bars


def _sma_definition(fast: int, slow: int) -> dict:
    fast_spec = {"definitionId": "sma", "parameters": {"period": fast}}
    slow_spec = {"definitionId": "sma", "parameters": {"period": slow}}
    return {
        "presetKey": "sma_crossover",
        "indicatorSpecs": [fast_spec, slow_spec],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_cross",
                    "leftSpec": fast_spec,
                    "rightSpec": slow_spec,
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
                    "leftSpec": fast_spec,
                    "rightSpec": slow_spec,
                    "direction": "bearish",
                    "signalKind": "exit",
                }
            ],
        },
    }


def test_rules_grid_search_produces_sorted_trials() -> None:
    bars = _cycle_bars()
    trials = run_rules_grid_search(
        bars,
        param_points=[{"fast": 5, "slow": 20}, {"fast": 10, "slow": 30}],
        template=lambda p: _sma_definition(int(p["fast"]), int(p["slow"])),
        max_trials=10,
    )
    assert trials
    scores = [trial.score for trial in trials]
    assert scores == sorted(scores, reverse=True)
    assert "sharpeRatio" in trials[0].is_metrics


def test_rules_grid_search_skips_unbuildable_points() -> None:
    bars = _cycle_bars()
    trials = run_rules_grid_search(
        bars,
        param_points=[{"fast": 5}, {"fast": 10}],
        template=lambda p: None if p["fast"] == 5 else _sma_definition(10, 30),
        max_trials=10,
    )
    # El punto que no materializa no se convierte en trial.
    assert len(trials) <= 1


def test_rules_grid_search_fails_closed_without_trades() -> None:
    bars = _cycle_bars()
    trials = run_rules_grid_search(
        bars,
        param_points=[{"x": 1}],
        # Nunca hay cruce (misma serie) ⇒ sin operaciones ⇒ sin trial.
        template=lambda p: _sma_definition(5, 5),
        max_trials=10,
    )
    assert trials == []


def test_rules_grid_search_rejects_empty_bars() -> None:
    with pytest.raises(ValueError):
        run_rules_grid_search([], param_points=[{}], template=lambda p: None)
