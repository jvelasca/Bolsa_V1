"""Contrato/Puerto de repositorio para políticas de posición (Protocol)."""
from typing import Any, Protocol

from bolsa_domain.entities.position_policy import PositionPolicyRecord


class PositionPolicyRepository(Protocol):
    async def list_policies(
        self,
        *,
        account_id: str | None = None,
        limit: int = 100,
    ) -> list[PositionPolicyRecord]: ...

    async def get_policy(self, policy_id: str) -> PositionPolicyRecord | None: ...

    async def get_by_account_instrument(
        self,
        account_id: str,
        instrument_id: str,
    ) -> PositionPolicyRecord | None: ...

    async def create_policy(
        self,
        *,
        account_id: str,
        instrument_id: str,
        definition: dict[str, Any],
        mode: str,
        exit_strategy_definition_id: str | None,
        execution_policy_id: str | None,
    ) -> PositionPolicyRecord: ...

    async def update_policy(
        self,
        policy_id: str,
        *,
        definition: dict[str, Any] | None = None,
        mode: str | None = None,
        exit_strategy_definition_id: str | None = None,
        execution_policy_id: str | None = None,
    ) -> PositionPolicyRecord | None: ...

    async def delete_policy(self, policy_id: str) -> bool: ...
