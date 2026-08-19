"""Causality Layer (F-IND-1): guardias contra look-ahead en backtest/research.

Cubre:
- `_series_for_spec` no resuelve salidas no causales (`ich:chikou`, fractals).
- `validate_strategy_definition` rechaza features no causales.
- Indicadores causales (p. ej. `sma`) siguen resolviéndose y validándose.
"""

from __future__ import annotations

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.research.strategy_definition_validator import validate_strategy_definition
from bolsa_analytics.signals.rules_engine import _series_for_spec


def _bars(n: int = 80) -> list[OhlcvBar]:
    return [
        OhlcvBar(
            timestamp=f"2024-01-{i + 1:02d}",
            open=100.0 + i,
            high=105.0 + i,
            low=95.0 + i,
            close=101.0 + i,
            volume=1000.0,
        )
        for i in range(n)
    ]


def _closes(bars: list[OhlcvBar]) -> list[float]:
    return [bar.close for bar in bars]


def test_chikou_not_a_causal_feature() -> None:
    bars = _bars()
    series = _series_for_spec(
        bars,
        _closes(bars),
        "ich",
        {"line": "chikou", "tenkanPeriod": 9, "kijunPeriod": 26},
    )
    assert series is None


def test_rules_reject_noncausal_ich_chikou() -> None:
    definition = {
        "kind": "rule_based",
        "timeframe": "1d",
        "indicatorSpecs": [
            {"definitionId": "ich", "parameters": {"line": "chikou", "tenkanPeriod": 9}}
        ],
        "entries": {"operator": "all", "rules": []},
        "exits": {"operator": "all", "rules": []},
    }
    errors = validate_strategy_definition(definition)
    assert any("chikou" in error and "no es causal" in error for error in errors)


def test_fractals_not_wired_into_backtest() -> None:
    bars = _bars()
    # No se resuelve `fr` como feature de señal en backtest.
    assert _series_for_spec(bars, _closes(bars), "fr", {}) is None
    # Y la validación de estrategias lo rechaza explícitamente.
    definition = {
        "kind": "rule_based",
        "timeframe": "1d",
        "indicatorSpecs": [{"definitionId": "fr", "parameters": {}}],
        "entries": {"operator": "all", "rules": []},
        "exits": {"operator": "all", "rules": []},
    }
    errors = validate_strategy_definition(definition)
    assert any("fr (fractals)" in error for error in errors)


def test_validator_allows_chikou_for_visualization() -> None:
    # La validación de estrategias NO rechaza un indicador causal (sma) y la
    # guardia `ich:chikou` solo aplica cuando el line es chikou (el chart sigue
    # pudiendo dibujar chikou porque no pasa por este validador).
    definition = {
        "kind": "rule_based",
        "timeframe": "1d",
        "indicatorSpecs": [{"definitionId": "sma", "parameters": {"period": 20}}],
        "entries": {"operator": "all", "rules": []},
        "exits": {"operator": "all", "rules": []},
    }
    assert validate_strategy_definition(definition) == []

    # Un ich con line causal (tenkan) tampoco se rechaza.
    ich_causal = {
        "kind": "rule_based",
        "timeframe": "1d",
        "indicatorSpecs": [
            {"definitionId": "ich", "parameters": {"line": "tenkan", "tenkanPeriod": 9}}
        ],
        "entries": {"operator": "all", "rules": []},
        "exits": {"operator": "all", "rules": []},
    }
    assert validate_strategy_definition(ich_causal) == []


def test_ich_causal_lines_still_resolvable() -> None:
    # Las líneas causales del Ichimoku (tenkan/kijun/spanA/spanB) SÍ se resuelven
    # como feature: spanA/spanB se dibujan desplazados pero usan datos de i-26.
    bars = _bars()
    for line in ("tenkan", "kijun", "spanA", "spanB"):
        series = _series_for_spec(
            bars,
            _closes(bars),
            "ich",
            {"line": line, "tenkanPeriod": 9, "kijunPeriod": 26, "senkouBPeriod": 52},
        )
        assert series is not None
