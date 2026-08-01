"""Validación de borradores de indicador contra catálogo fijo."""

from __future__ import annotations

from typing import Any

ALLOWED_INDICATOR_DEFINITION_IDS = frozenset(
    {
        "volume",
        "sma",
        "ema",
        "rsi",
        "wma",
        "bb",
        "macd",
        "stoch",
        "atr",
        "cci",
        "willr",
        "mom",
        "sd",
        "dc",
        "adx",
        "srsi",
        "st",
        "vwap",
        "obv",
        "roc",
        "mfi",
        "aroon",
        "sar",
        "bears",
        "bulls",
        "ali",
        "fr",
        "ich",
        "technical_rating_v1",
        "bar_data_quality_v1",
        "ai_global_score_v1",
        "strategy_hybrid_score_v1",
    },
)

AI_INDICATOR_IDS = frozenset(
    {
        "technical_rating_v1",
        "bar_data_quality_v1",
        "ai_global_score_v1",
        "strategy_hybrid_score_v1",
    },
)

_PARAM_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    "sma": {"period": (2, 200)},
    "ema": {"period": (2, 200)},
    "wma": {"period": (2, 200)},
    "rsi": {"period": (2, 100)},
    "bb": {"period": (2, 200), "stdDev": (0.5, 4)},
    "atr": {"period": (2, 100)},
    "cci": {"period": (2, 100)},
    "willr": {"period": (2, 100)},
    "mom": {"period": (1, 100)},
    "sd": {"period": (2, 200)},
    "dc": {"period": (2, 200)},
    "adx": {"period": (2, 100)},
    "srsi": {
        "rsiPeriod": (2, 100),
        "stochPeriod": (2, 100),
        "kPeriod": (1, 20),
        "dPeriod": (1, 20),
    },
    "st": {"atrPeriod": (2, 100), "multiplier": (0.5, 10)},
    "roc": {"period": (1, 200)},
    "mfi": {"period": (2, 100)},
    "aroon": {"period": (2, 100)},
    "sar": {"step": (0.001, 0.2), "maxAf": (0.01, 1)},
    "bears": {"period": (2, 100)},
    "bulls": {"period": (2, 100)},
    "ich": {
        "tenkanPeriod": (2, 50),
        "kijunPeriod": (2, 100),
        "senkouBPeriod": (2, 200),
        "displacement": (1, 100),
    },
    "stoch": {"kPeriod": (2, 100), "dPeriod": (1, 20)},
    "macd": {"fastPeriod": (2, 50), "slowPeriod": (2, 100), "signalPeriod": (2, 50)},
    "technical_rating_v1": {"warmupBars": (30, 200)},
    "bar_data_quality_v1": {"gapLookback": (20, 250)},
    "ai_global_score_v1": {"setupWeight": (0, 100), "dataWeight": (0, 100), "warmupBars": (30, 200)},
    "strategy_hybrid_score_v1": {
        "minScore": (0, 100),
        "warmupBars": (30, 200),
    },
}


def validate_indicator_draft(
    *,
    definition_id: str,
    parameters: dict[str, Any],
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if definition_id not in ALLOWED_INDICATOR_DEFINITION_IDS:
        errors.append(f"definitionId no soportado: {definition_id}")
        return False, errors

    bounds = _PARAM_BOUNDS.get(definition_id, {})
    for key, value in parameters.items():
        if key in {"color", "linkedStrategyId", "strategyName", "gatePresetKey"}:
            continue
        if isinstance(value, bool):
            continue
        if key not in bounds:
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            errors.append(f"Parámetro {key} debe ser numérico")
            continue
        low, high = bounds[key]
        if num < low or num > high:
            errors.append(f"Parámetro {key} fuera de rango ({low}–{high})")

    if definition_id == "ai_global_score_v1":
        setup = float(parameters.get("setupWeight") or 0)
        data = float(parameters.get("dataWeight") or 0)
        if setup + data <= 0:
            errors.append("setupWeight + dataWeight debe ser > 0")

    return len(errors) == 0, errors
