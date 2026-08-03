"""Preset → RuleGroupV1 — delega en preset_catalog (strategy-presets.json)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.signals.preset_catalog import (
    enrich_definition_with_preset_rules,
    is_valid_preset_key,
    preset_rule_groups,
    preset_strategy_keys,
    rule_group_has_rules,
)

PresetStrategyType = str

PRESET_STRATEGY_KEYS = preset_strategy_keys()

__all__ = [
    "PRESET_STRATEGY_KEYS",
    "PresetStrategyType",
    "definition_has_rules",
    "enrich_definition_with_preset_rules",
    "is_valid_preset_key",
    "preset_rule_groups",
    "rule_group_has_rules",
]

def definition_has_rules(definition: dict[str, Any]) -> bool:
    """Función pública ``definition_has_rules``."""
    return rule_group_has_rules(definition.get("entries")) or rule_group_has_rules(
        definition.get("exits")
    )
