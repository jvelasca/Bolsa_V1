"""Bus in-process de eventos de plataforma."""

import logging
from typing import Any, Protocol

from bolsa_application.context.principal import get_current_principal
from bolsa_domain.entities.platform_event import PlatformEventRecord
from bolsa_domain.repositories.platform_event_repository import PlatformEventRepository

logger = logging.getLogger(__name__)


class PlatformEventHandler(Protocol):
    """Use-case / tipo: Platform Event Handler."""
    async def handle(self, event: PlatformEventRecord) -> None: ...


class PlatformEventBus:
    """Bus append-only: persiste en platform_events y despacha handlers opcionales."""

    def __init__(
        self,
        repository: PlatformEventRepository,
        handlers: list[PlatformEventHandler] | None = None,
    ) -> None:
        self._repository = repository
        self._handlers = list(handlers or [])

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        user_id: str | None = None,
    ) -> PlatformEventRecord:
        resolved_user_id = user_id if user_id is not None else get_current_principal()
        event = await self._repository.append(
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            user_id=resolved_user_id,
        )
        for handler in self._handlers:
            try:
                await handler.handle(event)
            except Exception:
                logger.exception("PlatformEvent handler failed for %s (%s)", event_type, event.id)
        return event
