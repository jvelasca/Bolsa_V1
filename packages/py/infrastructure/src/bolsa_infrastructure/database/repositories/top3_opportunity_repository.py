"""Repository: top3_opportunities (TOP3 cross-asset de oportunidades rankeadas por AUTO).

Read + write del espejo durable del TOP3 (migración 052). No reutiliza
``instrument_strategy_tops`` (per-instrumento): aquí cada ``run_id`` es una foto del
universo rankeado (cross-asset) y ``asset_id`` es un identificador de activo, no una FK
a ``instruments``. El TOP3 describe oportunidades rankeadas, nunca una decisión de cartera.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models.tables import Top3OpportunityRow


@dataclass(slots=True)
class Top3OpportunityInput:
    """Entrada de escritura de un slot (lo que decide el motor)."""

    run_id: str
    rank: int
    asset_id: str
    combined: float
    components: dict[str, Any]
    regime: str | None = None
    reasons: list[str] | None = None


@dataclass(slots=True)
class Top3OpportunityRowRecord:
    """Slot persistido (con identidad e instante)."""

    id: str
    run_id: str
    rank: int
    asset_id: str
    combined: float
    components: dict[str, Any]
    regime: str | None
    reasons: list[str]
    created_at: datetime


def _map(row: Top3OpportunityRow) -> Top3OpportunityRowRecord:
    return Top3OpportunityRowRecord(
        id=row.id,
        run_id=row.run_id,
        rank=row.rank,
        asset_id=row.asset_id,
        combined=float(row.combined),
        components=dict(row.components or {}),
        regime=row.regime,
        reasons=[str(r) for r in (row.reasons or [])],
        created_at=row.created_at,
    )


class SqlAlchemyTop3OpportunityRepository:
    """Persistencia + lectura del TOP3 cross-asset (``AsyncSession``)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, inputs: list[Top3OpportunityInput]) -> list[Top3OpportunityRowRecord]:
        """Inserta los slots de un run (idempotente por ``id`` determinista)."""
        now = datetime.now(UTC)
        records: list[Top3OpportunityRowRecord] = []
        for item in inputs:
            row = Top3OpportunityRow(
                id=f"top3_{uuid4().hex}",
                run_id=item.run_id,
                rank=item.rank,
                asset_id=item.asset_id,
                combined=item.combined,
                components=dict(item.components or {}),
                regime=item.regime,
                reasons=list(item.reasons or []),
                created_at=now,
            )
            self._session.add(row)
            records.append(_map(row))
        await self._session.flush()
        await self._session.commit()
        return records

    async def list_for_run(self, run_id: str) -> list[Top3OpportunityRowRecord]:
        stmt = (
            select(Top3OpportunityRow)
            .where(Top3OpportunityRow.run_id == run_id)
            .order_by(Top3OpportunityRow.rank.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map(r) for r in rows]

    async def latest(self) -> tuple[str, list[Top3OpportunityRowRecord]]:
        """Run más reciente (por ``created_at``) y sus slots ordenados por rank.

        Sin filas devuelve ``("", [])`` (fail-closed: la UI declara «sin TOP3 todavía»).
        """
        stmt = (
            select(Top3OpportunityRow)
            .order_by(Top3OpportunityRow.created_at.desc())
            .limit(1)
        )
        newest = (await self._session.execute(stmt)).scalars().first()
        if newest is None:
            return "", []
        return newest.run_id, await self.list_for_run(newest.run_id)
