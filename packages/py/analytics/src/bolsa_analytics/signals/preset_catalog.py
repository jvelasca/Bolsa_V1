"""Catálogo central de presets — lee packages/shared/src/strategy-presets.json."""



from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypeGuard

type PresetStrategyType = str





def _catalog_path() -> Path:

    env_path = os.environ.get("BOLSA_PRESETS_JSON")

    if env_path:

        return Path(env_path)



    start = Path(__file__).resolve()

    for parent in start.parents:

        for relative in (

            Path("shared/src/strategy-presets.json"),

            Path("packages/shared/src/strategy-presets.json"),

        ):

            candidate = parent / relative

            if candidate.is_file():

                return candidate



    raise FileNotFoundError(

        "strategy-presets.json not found; set BOLSA_PRESETS_JSON or run from monorepo root"

    )





@lru_cache(maxsize=1)

def load_preset_catalog() -> dict[str, Any]:

    path = _catalog_path()

    with path.open(encoding="utf-8") as handle:

        return json.load(handle)





@lru_cache(maxsize=1)

def preset_strategy_keys() -> frozenset[str]:

    catalog = load_preset_catalog()

    return frozenset(catalog.get("presets", {}).keys())





PRESET_STRATEGY_KEYS: frozenset[str] = preset_strategy_keys()





@lru_cache(maxsize=1)

def hybrid_gate_preset_keys() -> frozenset[str]:

    catalog = load_preset_catalog()

    presets = catalog.get("presets") or {}

    return frozenset(

        key for key, definition in presets.items() if definition.get("hybridGate") is True

    )





def is_valid_preset_key(value: str | None) -> TypeGuard[PresetStrategyType]:

    return value is not None and value in preset_strategy_keys()




def preset_definition(preset_key: str) -> dict[str, Any]:

    catalog = load_preset_catalog()

    presets = catalog.get("presets") or {}

    if preset_key not in presets:

        raise KeyError(f"Unknown preset: {preset_key}")

    return presets[preset_key]





def preset_rule_groups(preset_key: str) -> dict[str, dict[str, Any]]:

    definition = preset_definition(preset_key)

    return {

        "entries": definition["entries"],

        "exits": definition["exits"],

    }





def preset_indicator_specs(preset_key: str) -> list[dict[str, Any]]:

    definition = preset_definition(preset_key)

    return list(definition.get("indicatorSpecs") or [])





def preset_label(preset_key: str) -> str:

    return str(preset_definition(preset_key).get("label") or preset_key)





def rule_group_has_rules(group: dict[str, Any] | None) -> bool:

    if not group:

        return False

    rules = group.get("rules")

    return bool(rules)





def definition_has_rules(definition: dict[str, Any]) -> bool:

    return rule_group_has_rules(definition.get("entries")) or rule_group_has_rules(

        definition.get("exits")

    )





def enrich_definition_with_preset_rules(definition: dict[str, Any]) -> dict[str, Any]:

    if definition_has_rules(definition):

        return definition

    preset = definition.get("presetKey")

    if not is_valid_preset_key(preset):

        return definition

    groups = preset_rule_groups(preset)

    enriched = {

        **definition,

        "entries": groups["entries"],

        "exits": groups["exits"],

    }

    if not enriched.get("indicatorSpecs"):

        enriched["indicatorSpecs"] = preset_indicator_specs(preset)

    return enriched





def strategy_definition_from_preset(

    preset_key: str,

    instrument_ids: list[str],

    timeframe: Literal["1d", "1wk"] = "1d",

) -> dict[str, Any]:

    if not is_valid_preset_key(preset_key):

        raise ValueError(f"Unsupported preset: {preset_key}")

    definition = preset_definition(preset_key)

    groups = preset_rule_groups(preset_key)

    return {

        "id": f"preset:{preset_key}",

        "version": 1,

        "name": definition.get("label") or preset_key,

        "kind": "indicator_signals",

        "presetKey": preset_key,

        "universe": {"instrumentIds": instrument_ids},

        "timeframe": timeframe,

        "dataSnapshotPolicy": "latest",

        "entries": groups["entries"],

        "exits": groups["exits"],

        "sizing": {"mode": "fixed_cash", "value": 1},

        "risk": {},

        "indicatorSpecs": preset_indicator_specs(preset_key),

        "execution": {"fillModel": "bar_close", "commissionBps": 0, "slippageBps": 0},

        "origin": "preset",

    }

