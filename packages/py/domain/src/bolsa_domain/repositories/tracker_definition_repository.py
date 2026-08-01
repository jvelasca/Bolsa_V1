from typing import Any, Protocol

from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord


class TrackerDefinitionRepository(Protocol):
    async def list_trackers(self, *, limit: int = 50, enabled_only: bool = False) -> list[TrackerDefinitionRecord]: ...

    async def list_trackers_for_list(
        self, list_id: str, *, limit: int = 50
    ) -> list[TrackerDefinitionRecord]: ...

    async def get_tracker(self, tracker_id: str) -> TrackerDefinitionRecord | None: ...

    async def create_tracker(
        self,
        *,
        name: str,
        definition: dict[str, Any],
        strategy_definition_id: str,
        strategy_version: int | None,
        timeframe: str,
        evaluation_mode: str,
        origin: str,
        enabled: bool,
        user_id: str | None = None,
    ) -> TrackerDefinitionRecord: ...

    async def update_tracker(
        self,
        tracker_id: str,
        *,
        name: str | None = None,
        definition: dict[str, Any] | None = None,
        strategy_definition_id: str | None = None,
        strategy_version: int | None = None,
        timeframe: str | None = None,
        evaluation_mode: str | None = None,
        origin: str | None = None,
        enabled: bool | None = None,
    ) -> TrackerDefinitionRecord | None: ...

    async def delete_tracker(self, tracker_id: str) -> bool: ...
