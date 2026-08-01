from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PositionPolicyRecord:
    id: str
    account_id: str
    instrument_id: str
    definition: dict[str, Any]
    mode: str
    exit_strategy_definition_id: str | None
    execution_policy_id: str | None
    created_at: str
    updated_at: str
