"""Use-cases de definiciones de estrategia."""

from typing import Any

from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_domain.entities.strategy_definition import StrategyDefinitionRecord
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository


class ListStrategyDefinitions:
    """Lista Strategy Definitions."""
    def __init__(self, repository: StrategyDefinitionRepository) -> None:
        self._repository = repository

    async def execute(self, limit: int = 50) -> list[StrategyDefinitionRecord]:
        return await self._repository.list_definitions(limit=limit)


class GetStrategyDefinition:
    """Obtiene Strategy Definition."""
    def __init__(self, repository: StrategyDefinitionRepository) -> None:
        self._repository = repository

    async def execute(self, definition_id: str) -> StrategyDefinitionRecord | None:
        return await self._repository.get_definition(definition_id)


class CreateStrategyFromPreset:
    """Crea Strategy From Preset."""
    def __init__(self, repository: StrategyDefinitionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        name: str,
        preset_key: str,
        timeframe: str = "1d",
        commission_bps: int = 0,
        slippage_bps: int = 0,
    ) -> StrategyDefinitionRecord:
        definition = strategy_definition_from_preset(
            preset_key,
            instrument_ids=[],
            timeframe=timeframe,  # type: ignore[arg-type]
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        )
        definition["origin"] = "manual"
        definition["name"] = name
        record = await self._repository.create_definition(
            name=name,
            definition=definition,
            preset_key=preset_key,
            origin="manual",
            timeframe=timeframe,
        )
        patched = {**record.definition, "id": record.id}
        updated = await self._repository.update_definition(record.id, definition=patched)
        return updated or record


class CreateStrategyDefinition:
    """Crea Strategy Definition."""
    def __init__(self, repository: StrategyDefinitionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        name: str,
        definition: dict[str, Any],
    ) -> StrategyDefinitionRecord:
        preset = definition.get("presetKey")
        preset_key: str | None = preset if is_valid_preset_key(preset) else None
        timeframe = str(definition.get("timeframe", "1d"))
        origin = str(definition.get("origin", "manual"))
        definition = {**definition, "name": name}
        return await self._repository.create_definition(
            name=name,
            definition=definition,
            preset_key=preset_key,
            origin=origin,
            timeframe=timeframe,
        )


class UpdateStrategyDefinition:
    """Actualiza Strategy Definition."""
    def __init__(self, repository: StrategyDefinitionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        definition_id: str,
        *,
        name: str | None = None,
        definition: dict[str, Any] | None = None,
    ) -> StrategyDefinitionRecord | None:
        preset_key = None
        origin = None
        timeframe = None
        if definition is not None:
            preset = definition.get("presetKey")
            preset_key = preset if is_valid_preset_key(preset) else None
            origin = str(definition.get("origin", "manual"))
            timeframe = str(definition.get("timeframe", "1d"))
            if name is not None:
                definition = {**definition, "name": name}
        return await self._repository.update_definition(
            definition_id,
            name=name,
            definition=definition,
            preset_key=preset_key,
            origin=origin,
            timeframe=timeframe,
        )


class DeleteStrategyDefinition:
    """Elimina Strategy Definition."""
    def __init__(self, repository: StrategyDefinitionRepository) -> None:
        self._repository = repository

    async def execute(self, definition_id: str) -> bool:
        return await self._repository.delete_definition(definition_id)
