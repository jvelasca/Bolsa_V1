"""Contrato/Puerto de repositorio para políticas de ejecución (Protocol)."""
from typing import Any, Protocol

from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord


class ExecutionPolicyRepository(Protocol):
    async def list_policies(self, *, limit: int = 50, enabled_only: bool = False) -> list[ExecutionPolicyRecord]: ...

    async def get_policy(self, policy_id: str) -> ExecutionPolicyRecord | None: ...

    async def create_policy(
        self,
        *,
        name: str,
        definition: dict[str, Any],
        mode: str,
        account_id: str | None,
        strategy_definition_id: str | None,
        origin: str,
        enabled: bool,
        user_id: str | None = None,
    ) -> ExecutionPolicyRecord: ...

    async def update_policy(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        definition: dict[str, Any] | None = None,
        mode: str | None = None,
        account_id: str | None = None,
        strategy_definition_id: str | None = None,
        origin: str | None = None,
        enabled: bool | None = None,
    ) -> ExecutionPolicyRecord | None: ...

    async def delete_policy(self, policy_id: str) -> bool: ...
