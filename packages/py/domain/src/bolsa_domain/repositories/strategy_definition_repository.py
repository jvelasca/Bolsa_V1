from typing import Any, Protocol

from bolsa_domain.entities.strategy_definition import StrategyDefinitionRecord


class StrategyDefinitionRepository(Protocol):
    async def list_definitions(self, limit: int = 50) -> list[StrategyDefinitionRecord]: ...

    async def get_definition(self, definition_id: str) -> StrategyDefinitionRecord | None: ...

    async def create_definition(
        self,
        *,
        name: str,
        definition: dict[str, Any],
        preset_key: str | None,
        origin: str,
        timeframe: str,
    ) -> StrategyDefinitionRecord: ...

    async def update_definition(
        self,
        definition_id: str,
        *,
        name: str | None = None,
        definition: dict[str, Any] | None = None,
        preset_key: str | None = None,
        origin: str | None = None,
        timeframe: str | None = None,
    ) -> StrategyDefinitionRecord | None: ...

    async def delete_definition(self, definition_id: str) -> bool: ...
