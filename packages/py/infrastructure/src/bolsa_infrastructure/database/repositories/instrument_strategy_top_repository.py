"""Repository: instrument_strategy_tops (TOP-3 AT por valor)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InstrumentStrategyTopRow


@dataclass(slots=True)
class InstrumentStrategyTopRecord:
    id: str
    instrument_id: str
    symbol: str | None
    timeframe: str
    period_label: str | None
    status: str
    version: int
    evidence_level: str
    slots: list[dict[str, Any]]
    coach_headline: str | None
    coach_facts: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


def _map(row: InstrumentStrategyTopRow) -> InstrumentStrategyTopRecord:
    return InstrumentStrategyTopRecord(
        id=row.id,
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        timeframe=row.timeframe,
        period_label=row.period_label,
        status=row.status,
        version=row.version,
        evidence_level=row.evidence_level,
        slots=list(row.slots or []),
        coach_headline=row.coach_headline,
        coach_facts=dict(row.coach_facts) if row.coach_facts else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyInstrumentStrategyTopRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, instrument_id: str, timeframe: str = "1d") -> InstrumentStrategyTopRecord | None:
        stmt = select(InstrumentStrategyTopRow).where(
            InstrumentStrategyTopRow.instrument_id == instrument_id,
            InstrumentStrategyTopRow.timeframe == timeframe,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _map(row) if row else None

    async def list_for_instrument(self, instrument_id: str) -> list[InstrumentStrategyTopRecord]:
        stmt = (
            select(InstrumentStrategyTopRow)
            .where(InstrumentStrategyTopRow.instrument_id == instrument_id)
            .order_by(InstrumentStrategyTopRow.updated_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map(r) for r in rows]

    async def upsert(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        slots: list[dict[str, Any]],
        symbol: str | None = None,
        period_label: str | None = None,
        status: str = "semifinal",
        evidence_level: str = "in_sample_only",
        coach_headline: str | None = None,
        coach_facts: dict[str, Any] | None = None,
    ) -> InstrumentStrategyTopRecord:
        if not (1 <= len(slots) <= 3):
            raise ValueError("slots debe tener entre 1 y 3 entradas")
        now = datetime.now(UTC)
        existing = await self.get(instrument_id, timeframe)
        if existing is None:
            row = InstrumentStrategyTopRow(
                id=f"ist_{uuid4().hex}",
                instrument_id=instrument_id,
                symbol=symbol,
                timeframe=timeframe,
                period_label=period_label,
                status=status,
                version=1,
                evidence_level=evidence_level,
                slots=slots,
                coach_headline=coach_headline,
                coach_facts=coach_facts,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
            return _map(row)

        stmt = select(InstrumentStrategyTopRow).where(InstrumentStrategyTopRow.id == existing.id)
        row = (await self._session.execute(stmt)).scalar_one()
        row.symbol = symbol if symbol is not None else row.symbol
        row.period_label = period_label
        row.status = status
        row.version = int(row.version or 1) + 1
        row.evidence_level = evidence_level
        row.slots = slots
        row.coach_headline = coach_headline
        row.coach_facts = coach_facts
        row.updated_at = now
        await self._session.commit()
        await self._session.refresh(row)
        return _map(row)

    async def list_for_instruments(
        self,
        instrument_ids: list[str],
        timeframe: str = "1d",
    ) -> list[InstrumentStrategyTopRecord]:
        ids = [i for i in instrument_ids if i]
        if not ids:
            return []
        stmt = select(InstrumentStrategyTopRow).where(
            InstrumentStrategyTopRow.instrument_id.in_(ids),
            InstrumentStrategyTopRow.timeframe == timeframe,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map(r) for r in rows]

    async def delete(self, instrument_id: str, timeframe: str = "1d") -> bool:
        stmt = select(InstrumentStrategyTopRow).where(
            InstrumentStrategyTopRow.instrument_id == instrument_id,
            InstrumentStrategyTopRow.timeframe == timeframe,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True
