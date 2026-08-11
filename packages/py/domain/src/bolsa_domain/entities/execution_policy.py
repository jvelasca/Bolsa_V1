"""Entidad de dominio de política de ejecución de órdenes — sin dependencias externas."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionPolicyRecord:
    id: str
    name: str
    definition: dict[str, Any]
    mode: str
    account_id: str | None
    strategy_definition_id: str | None
    origin: str
    enabled: bool
    user_id: str | None
    created_at: str
    updated_at: str
