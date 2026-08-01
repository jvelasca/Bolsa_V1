from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StrategyDefinitionRecord:
    id: str
    name: str
    definition: dict[str, Any]
    # Full catalog preset key (see strategy-presets.json), or None if custom rules-only.
    preset_key: str | None
    origin: str
    timeframe: str
    created_at: str
    updated_at: str
