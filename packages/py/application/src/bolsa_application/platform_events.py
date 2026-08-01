from bolsa_domain.entities.platform_event import PlatformEventRecord
from bolsa_domain.repositories.platform_event_repository import PlatformEventRepository


class ListPlatformEvents:
    def __init__(self, repository: PlatformEventRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
        correlation_id: str | None = None,
    ) -> list[PlatformEventRecord]:
        return await self._repository.list_events(
            limit=min(max(limit, 1), 200),
            event_type=event_type,
            correlation_id=correlation_id,
        )
