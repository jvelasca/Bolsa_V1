"""V2.29 / A10 — definición ejecutable del campeón (tests herméticos).

Certifica que los parámetros ganadores del LAB se traducen al esquema declarativo que
consume ``evaluate_strategy_last_bar``, y que la ausencia de campeón/params devuelve
``None`` (fail-closed) en lugar de una definición inventada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bolsa_application.strategy_executable_definition import (
    build_executable_definition,
    champion_params_from_result,
)


@dataclass
class _Trial:
    score: float
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Result:
    trials: list[_Trial] = field(default_factory=list)


# ── champion_params_from_result ─────────────────────────────────────────────────


def test_champion_params_picks_highest_score() -> None:
    result = _Result(
        trials=[
            _Trial(score=0.5, params={"fastPeriod": 5, "slowPeriod": 20}),
            _Trial(score=2.0, params={"fastPeriod": 10, "slowPeriod": 30}),
            _Trial(score=1.0, params={"fastPeriod": 7, "slowPeriod": 25}),
        ]
    )
    assert champion_params_from_result(result) == {"fastPeriod": 10, "slowPeriod": 30}


def test_champion_params_none_without_trials_or_params() -> None:
    assert champion_params_from_result(_Result(trials=[])) is None
    assert champion_params_from_result(_Result(trials=[_Trial(score=1.0)])) is None


# ── build_executable_definition ─────────────────────────────────────────────────


def test_executable_sma_crossover() -> None:
    definition = build_executable_definition(
        "sma_crossover", {"fastPeriod": 10, "slowPeriod": 30}
    )
    assert definition is not None
    assert definition["presetKey"] == "sma_crossover"
    assert definition["indicatorSpecs"] == [
        {"definitionId": "sma", "parameters": {"period": 10}},
        {"definitionId": "sma", "parameters": {"period": 30}},
    ]
    assert definition["entries"]["rules"][0]["signalKind"] == "entry_long"
    assert definition["exits"]["rules"][0]["signalKind"] == "exit"


def test_executable_rsi_mean_reversion() -> None:
    definition = build_executable_definition(
        "rsi_mean_reversion", {"period": 14, "oversold": 25, "overbought": 75}
    )
    assert definition is not None
    assert definition["presetKey"] == "rsi_mean_reversion"
    entry = definition["entries"]["rules"][0]
    assert entry["operator"] == "lt"
    assert entry["rightValue"] == 25
    exit_rule = definition["exits"]["rules"][0]
    assert exit_rule["operator"] == "gt"
    assert exit_rule["rightValue"] == 75


def test_executable_macd_signal_cross() -> None:
    definition = build_executable_definition(
        "macd_signal_cross",
        {"fastPeriod": 12, "slowPeriod": 26, "signalPeriod": 9},
    )
    assert definition is not None
    assert definition["presetKey"] == "macd_signal_cross"
    specs = definition["indicatorSpecs"]
    assert specs[0]["parameters"]["line"] == "main"
    assert specs[1]["parameters"]["line"] == "signal"


def test_executable_normalizes_family_alias() -> None:
    """Un alias de familia (p.ej. ``ema_crossover``) se normaliza a SMA."""
    definition = build_executable_definition(
        "ema_crossover", {"fastPeriod": 12, "slowPeriod": 26}
    )
    assert definition is not None
    assert definition["presetKey"] == "sma_crossover"


def test_executable_is_fail_closed() -> None:
    assert build_executable_definition(None, None) is None
    assert build_executable_definition("sma_crossover", None) is None
    assert build_executable_definition("sma_crossover", {}) is None
    # Faltan periodos ⇒ no se inventan.
    assert build_executable_definition("sma_crossover", {"fastPeriod": 10}) is None
    assert build_executable_definition("rsi_mean_reversion", {"period": 14}) is None
    # Familia no soportada.
    assert build_executable_definition("familia_inventada", {"period": 1}) is None
