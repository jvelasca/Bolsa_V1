"""R2 — ledger durable del disparador gobernado del embudo AUTO.

Reutiliza ``platform_events`` (tabla ya existente, append-only por convención) para
guardar el RECIBO de cada ejecución y, con él, la idempotencia: el ``run_id`` es
determinista a partir de la clave ``(instrumentId, accountId, snapshot, cycle, dryRun)``
y viaja como ``correlation_id``, así que buscar por correlación ES buscar el recibo.

Sin migración nueva: la auditoría y la idempotencia comparten la misma fila, y esa fila
es exactamente lo que exige el contrato («un evento por ejecución con actor, dryRun,
fase alcanzada, gates evaluados y resultado»).
"""

from __future__ import annotations

from typing import Any

from bolsa_application.orchestrator_trigger import TRIGGER_AUDIT_EVENT_TYPE
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.repositories.platform_event_repository import (
    SqlAlchemyPlatformEventRepository,
)


class SqlAlchemyTriggerLedger:
    """Implementación del puerto ``TriggerLedger`` sobre ``platform_events``."""

    def __init__(self, session: AsyncSession) -> None:
        self._events = SqlAlchemyPlatformEventRepository(session)

    async def find(self, *, run_id: str) -> dict[str, Any] | None:
        """Recibo ya persistido para ``run_id`` (o ``None`` si no hay ejecución)."""
        events = await self._events.list_events(
            event_type=TRIGGER_AUDIT_EVENT_TYPE,
            correlation_id=run_id,
            # El índice de la consulta lo pone la correlación; 1 fila basta porque el
            # run_id es determinista (una ejecución por clave).
            limit=1,
        )
        if not events:
            return None
        payload = dict(events[0].payload or {})
        # Defensa: una correlación reutilizada por otro evento no es este recibo.
        if str(payload.get("runId") or "") != run_id:
            return None
        return payload

    async def append(self, *, run_id: str, payload: dict[str, Any]) -> str:
        record = await self._events.append(
            event_type=TRIGGER_AUDIT_EVENT_TYPE,
            payload=payload,
            correlation_id=run_id,
            # F7c: la visibilidad del evento es del principal que disparó el embudo.
            user_id=(str(payload.get("actor") or "") or None),
        )
        return record.id


__all__ = ["SqlAlchemyTriggerLedger"]
