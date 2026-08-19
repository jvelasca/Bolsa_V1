"""Validación estática de StrategyDefinitionV1 (P11)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.signals.preset_catalog import is_valid_preset_key, rule_group_has_rules

ALLOWED_KINDS = frozenset({"rule_based", "indicator_signals", "ml_model", "hybrid"})
ALLOWED_KERNEL_TIMEFRAMES = frozenset({"1d", "1wk"})
ALLOWED_INDICATOR_IDS = frozenset(
    {
        "sma",
        "ema",
        "rsi",
        "bb",
        "macd",
        "stoch",
        "atr",
        "cci",
        "wma",
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
    },
)
MAX_RULES_PER_GROUP = 12


def validate_strategy_definition(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    kind = definition.get("kind")
    if kind not in ALLOWED_KINDS:
        errors.append(f"kind inválido: {kind!r}")

    timeframe = definition.get("timeframe")
    if timeframe not in ALLOWED_KERNEL_TIMEFRAMES:
        errors.append(f"timeframe no soportado en kernel: {timeframe!r}")

    preset_key = definition.get("presetKey")
    if preset_key is not None and not is_valid_preset_key(str(preset_key)):
        errors.append(f"presetKey desconocido: {preset_key!r}")

    for spec in definition.get("indicatorSpecs") or []:
        definition_id = spec.get("definitionId")
        if definition_id not in ALLOWED_INDICATOR_IDS:
            errors.append(f"indicador no permitido: {definition_id!r}")

        parameters = spec.get("parameters") or {}
        line = parameters.get("line") if isinstance(parameters, dict) else None
        # F-IND-1: rechaza features no causales en backtest/research. La
        # visualización/chart no usa este validador y puede dibujar chikou/fractals.
        if definition_id == "ich" and line == "chikou":
            errors.append(
                "ich line=chikou no es causal: no puede usarse como feature en backtest/research"
            )
        if definition_id == "fr":
            errors.append(
                "fr (fractals) no es causal: no puede usarse como feature en backtest/research"
            )

    for group_name in ("entries", "exits"):
        group = definition.get(group_name)
        if not group:
            continue
        rules = group.get("rules") or []
        if len(rules) > MAX_RULES_PER_GROUP:
            errors.append(f"{group_name}: demasiadas reglas ({len(rules)} > {MAX_RULES_PER_GROUP})")

    if kind == "hybrid":
        hybrid = definition.get("hybrid")
        if not isinstance(hybrid, dict):
            errors.append("hybrid: bloque obligatorio ausente")
        else:
            rule_gate = hybrid.get("ruleGate")
            if not rule_group_has_rules(rule_gate if isinstance(rule_gate, dict) else None):
                errors.append("hybrid.ruleGate debe tener al menos una regla")
            ai_scorer = hybrid.get("aiScorer")
            if not isinstance(ai_scorer, dict):
                errors.append("hybrid.aiScorer obligatorio")
            else:
                min_score = ai_scorer.get("minScore")
                if min_score is None or not (0 <= float(min_score) <= 100):
                    errors.append("hybrid.aiScorer.minScore debe estar entre 0 y 100")
                model_id = ai_scorer.get("modelId")
                if model_id != "technical_rating_v1":
                    errors.append(f"hybrid.aiScorer.modelId no soportado: {model_id!r}")

    elif kind == "indicator_signals":
        has_rules = rule_group_has_rules(definition.get("entries")) or rule_group_has_rules(
            definition.get("exits")
        )
        if not has_rules and not is_valid_preset_key(str(preset_key or "")):
            errors.append("indicator_signals requiere reglas o presetKey válido")

    return errors
