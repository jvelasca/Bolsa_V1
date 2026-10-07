"""V2.88 — sink durable del TOP3 cross-asset (glue aplicación → infraestructura).

Adapta los ``Top3OpportunityRecord`` (puros, del selector) al repositorio de la tabla
``top3_opportunities`` (migración 052). El ``regime`` del run se inyecta en el sink: es
una propiedad del CÓMPUTO del TOP3, no de cada slot, y sin él se persiste ``None``
(nunca se inventa un régimen).
"""

from __future__ import annotations

from typing import Any

from bolsa_infrastructure.database.repositories.top3_opportunity_repository import (
    SqlAlchemyTop3OpportunityRepository,
    Top3OpportunityInput,
)

from bolsa_application.top3_opportunities import Top3OpportunityRecord

__all__ = ["PostgresTop3OpportunitySink"]


class PostgresTop3OpportunitySink:
    """Implementación DB del ``Top3OpportunitySink`` (Protocol, módulo ``top3_opportunities``).

    ``save`` es idempotente por identidad determinista del slot; una lista vacía es un
    no-op (no se escribe un run sin TOP3).
    """

    def __init__(self, session: Any, *, regime: str | None = None) -> None:
        self._repository = SqlAlchemyTop3OpportunityRepository(session)
        self._regime = regime

    async def save(self, records: list[Top3OpportunityRecord]) -> None:
        if not records:
            return
        inputs = [
            Top3OpportunityInput(
                run_id=record.run_id,
                rank=record.rank,
                asset_id=record.instrument_id,
                combined=record.combined,
                components=dict(record.components),
                regime=self._regime,
                reasons=[record.reason] if record.reason else [],
            )
            for record in records
        ]
        await self._repository.save(inputs)
