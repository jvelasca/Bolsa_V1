"""StrategyDefinitionV1 híbrida — paridad con packages/shared/src/hybrid-strategy.ts."""

from __future__ import annotations

from typing import Any, Literal

from bolsa_analytics.signals.preset_catalog import (
    hybrid_gate_preset_keys,
    is_valid_preset_key,
    preset_indicator_specs,
    preset_rule_groups,
)

TECHNICAL_RATING_V1_VERSION = "1.1.0"
DEFAULT_HYBRID_MIN_SCORE = 60
DEFAULT_HYBRID_MIN_DATA_QUALITY = 0

HYBRID_GATE_PRESET_KEYS: frozenset[str] = hybrid_gate_preset_keys()

TECHNICAL_RATING_INDICATOR_SPECS: list[dict[str, Any]] = [
    {"definitionId": "sma", "parameters": {"period": 20}},
    {"definitionId": "sma", "parameters": {"period": 50}},
    {"definitionId": "sma", "parameters": {"period": 200}},
    {"definitionId": "rsi", "parameters": {"period": 14}},
    {
        "definitionId": "macd",
        "parameters": {"fastPeriod": 12, "slowPeriod": 26, "signalPeriod": 9, "line": "main"},
    },
    {"definitionId": "bb", "parameters": {"period": 20, "stdDev": 2, "line": "mid"}},
    {"definitionId": "bb", "parameters": {"period": 20, "stdDev": 2, "line": "upper"}},
    {"definitionId": "bb", "parameters": {"period": 20, "stdDev": 2, "line": "lower"}},
    {"definitionId": "stoch", "parameters": {"kPeriod": 14}},
    {"definitionId": "cci", "parameters": {"period": 20}},
    {"definitionId": "atr", "parameters": {"period": 14}},
]


def _merge_indicator_specs(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for spec in [item for group in groups for item in group]:
        key = f"{spec['definitionId']}::{spec.get('parameters')}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(spec)
    return merged


def strategy_definition_from_hybrid(
    *,
    name: str,
    gate_preset_key: str,
    min_score: float,
    instrument_ids: list[str],
    timeframe: Literal["1d", "1wk"] = "1d",
    fundamental_gate: dict[str, Any] | None = None,
    min_data_quality: float = DEFAULT_HYBRID_MIN_DATA_QUALITY,
) -> dict[str, Any]:
    if not is_valid_preset_key(gate_preset_key):
        raise ValueError(f"Unsupported gate preset: {gate_preset_key}")

    gate_rules = preset_rule_groups(gate_preset_key)["entries"]
    hybrid_block: dict[str, Any] = {
        "ruleGate": gate_rules,
        "aiScorer": {
            "modelId": "technical_rating_v1",
            "minScore": min_score,
            "version": TECHNICAL_RATING_V1_VERSION,
        },
        "gatePresetKey": gate_preset_key,
    }
    if fundamental_gate:
        hybrid_block["fundamentalGate"] = fundamental_gate
    if min_data_quality > 0:
        hybrid_block["minDataQuality"] = min_data_quality

    return {
        "id": f"hybrid:{gate_preset_key}:{min_score}",
        "version": 1,
        "name": name,
        "kind": "hybrid",
        "universe": {"instrumentIds": instrument_ids},
        "timeframe": timeframe,
        "dataSnapshotPolicy": "latest",
        "entries": {"operator": "all", "rules": []},
        "exits": {"operator": "all", "rules": []},
        "sizing": {"mode": "fixed_cash", "value": 1},
        "risk": {},
        "indicatorSpecs": _merge_indicator_specs(
            preset_indicator_specs(gate_preset_key),
            TECHNICAL_RATING_INDICATOR_SPECS,
        ),
        "execution": {"fillModel": "bar_close", "commissionBps": 0, "slippageBps": 0},
        "origin": "assisted",
        "hybrid": hybrid_block,
    }
