"""Contrato/Puerto de repositorio para eventos de plataforma (Protocol)."""
from typing import Any, Protocol

from bolsa_domain.entities.platform_event import PlatformEventRecord


class PlatformEventRepository(Protocol):
    async def append(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        user_id: str | None = None,
    ) -> PlatformEventRecord: ...

    async def list_events(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
        correlation_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[PlatformEventRecord]: ...
