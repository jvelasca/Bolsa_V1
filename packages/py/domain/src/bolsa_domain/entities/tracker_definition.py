from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TrackerDefinitionRecord:
    id: str
    name: str
    definition: dict[str, Any]
    strategy_definition_id: str
    strategy_version: int | None
    timeframe: str
    evaluation_mode: str
    origin: str
    enabled: bool
    user_id: str | None
    created_at: str
    updated_at: str
