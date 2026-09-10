"""V2.29 / A10 — definición ejecutable de la estrategia promocionada.

El LAB produce un **campeón** por familia (parámetros ganadores del grid), pero la
versión inmutable (``strategy_versions.definition``) solo guardaba la *rejilla* de
búsqueda (``candidate.params``), no los parámetros del campeón. Sin ellos la estrategia
ACTIVE no puede evaluar su propia señal en el motor SIM (P2 "SignalEvaluator real").

Este módulo cierra ese hueco de forma **aditiva y determinista**:

* ``champion_params_from_result(result)`` extrae los parámetros ganadores del
  ``LabOptimizeResult`` (el trial de mayor ``score``) tal y como los emite el LAB
  (camelCase: ``fastPeriod``/``slowPeriod``, ``period``/``oversold``/``overbought``,
  ``fastPeriod``/``slowPeriod``/``signalPeriod``).
* ``build_executable_definition(family, champion_params)`` traduce esos parámetros al
  esquema declarativo ``StrategyDefinitionV1`` (``presetKey`` + ``indicatorSpecs`` +
  ``entries``/``exits``) que consume ``evaluate_strategy_last_bar``.

Sin red, sin IA, sin DB: funciones puras. Un campeón ausente o una familia no soportada
devuelven ``None`` (fail-closed: la ACTIVE no inventa una señal ejecutable).
"""

from __future__ import annotations

from typing import Any

from bolsa_application.optimize import (
    STRATEGY_FAMILY_MACD,
    STRATEGY_FAMILY_RSI,
    STRATEGY_FAMILY_SMA,
    normalize_strategy_family,
)

__all__ = [
    "build_executable_definition",
    "champion_params_from_result",
]


def champion_params_from_result(result: Any) -> dict[str, Any] | None:
    """Parámetros del trial campeón (mayor ``score``) del resultado de optimización.

    Devuelve ``None`` cuando no hay trials o el campeón no trae ``params`` (no se
    inventan parámetros).
    """
    trials = list(getattr(result, "trials", None) or [])
    if not trials:
        return None
    champion = max(trials, key=lambda t: float(getattr(t, "score", 0.0) or 0.0))
    params = getattr(champion, "params", None)
    if not isinstance(params, dict) or not params:
        return None
    return {str(k): v for k, v in params.items()}


def _sma_definition(fast: int, slow: int) -> dict[str, Any]:
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


def _rsi_definition(period: int, oversold: float, overbought: float) -> dict[str, Any]:
    spec = {"definitionId": "rsi", "parameters": {"period": period}}
    return {
        "presetKey": "rsi_mean_reversion",
        "indicatorSpecs": [spec],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_compare",
                    "leftSpec": spec,
                    "operator": "lt",
                    "rightValue": oversold,
                    "signalKind": "entry_long",
                }
            ],
        },
        "exits": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_compare",
                    "leftSpec": spec,
                    "operator": "gt",
                    "rightValue": overbought,
                    "signalKind": "exit",
                }
            ],
        },
    }


def _macd_definition(fast: int, slow: int, signal: int) -> dict[str, Any]:
    main_spec = {
        "definitionId": "macd",
        "parameters": {
            "fastPeriod": fast,
            "slowPeriod": slow,
            "signalPeriod": signal,
            "line": "main",
        },
    }
    signal_spec = {
        "definitionId": "macd",
        "parameters": {
            "fastPeriod": fast,
            "slowPeriod": slow,
            "signalPeriod": signal,
            "line": "signal",
        },
    }
    return {
        "presetKey": "macd_signal_cross",
        "indicatorSpecs": [main_spec, signal_spec],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_cross",
                    "leftSpec": main_spec,
                    "rightSpec": signal_spec,
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
                    "leftSpec": main_spec,
                    "rightSpec": signal_spec,
                    "direction": "bearish",
                    "signalKind": "exit",
                }
            ],
        },
    }


def _as_int(params: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = params.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return None


def _as_float(params: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = params.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def build_executable_definition(
    family: str | None,
    champion_params: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Traduce ``(familia, params del campeón)`` al esquema ejecutable.

    Devuelve ``None`` (fail-closed) si faltan parámetros, la familia no es soportada o
    faltan los periodos mínimos para construir las reglas. Nunca inventa valores por
    defecto: una definición a medias sería peor que no tener ninguna.
    """
    if not champion_params:
        return None
    try:
        normalized = normalize_strategy_family(family)
    except ValueError:
        return None
    params = dict(champion_params)

    if normalized == STRATEGY_FAMILY_SMA:
        fast = _as_int(params, "fastPeriod", "fast_period", "fast")
        slow = _as_int(params, "slowPeriod", "slow_period", "slow")
        if fast is None or slow is None or fast <= 0 or slow <= 0:
            return None
        return _sma_definition(fast, slow)

    if normalized == STRATEGY_FAMILY_RSI:
        period = _as_int(params, "period", "rsiPeriod", "rsi_period")
        oversold = _as_float(params, "oversold", "oversoldLevel", "oversold_level")
        overbought = _as_float(params, "overbought", "overboughtLevel", "overbought_level")
        if period is None or period <= 0 or oversold is None or overbought is None:
            return None
        return _rsi_definition(period, oversold, overbought)

    if normalized == STRATEGY_FAMILY_MACD:
        fast = _as_int(params, "fastPeriod", "fast_period", "fast")
        slow = _as_int(params, "slowPeriod", "slow_period", "slow")
        signal = _as_int(params, "signalPeriod", "signal_period", "signal")
        if (
            fast is None
            or slow is None
            or signal is None
            or fast <= 0
            or slow <= 0
            or signal <= 0
        ):
            return None
        return _macd_definition(fast, slow, signal)

    return None
