"""Persistencia append-only de decision_journal_entries (ADR-029 F1/F2)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord
from bolsa_infrastructure.database.models import DecisionJournalEntryRow


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _row_to_record(row: DecisionJournalEntryRow) -> DecisionJournalEntryRecord:
    return DecisionJournalEntryRecord(
        id=row.id,
        decision_id=row.decision_id,
        event_type=row.event_type,
        actor=row.actor,
        created_at=_iso(row.created_at),
        session_id=row.session_id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        payload=dict(row.payload) if row.payload else None,
    )


class SqlAlchemyJournalRepository:
    """Implementación SQLAlchemy del puerto JournalWriter + lectura paginada (F2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: DecisionJournalEntryRecord) -> DecisionJournalEntryRecord:
        now = _parse_ts(entry.created_at) or datetime.now(UTC)
        row = DecisionJournalEntryRow(
            id=entry.id,
            decision_id=entry.decision_id,
            session_id=entry.session_id,
            account_id=entry.account_id,
            instrument_id=entry.instrument_id,
            event_type=entry.event_type,
            actor=entry.actor,
            payload=entry.payload,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return entry

    async def list_entries(
        self,
        *,
        account_id: str,
        instrument_id: str | None = None,
        since: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DecisionJournalEntryRecord], int]:
        filters = [DecisionJournalEntryRow.account_id == account_id]
        if instrument_id:
            filters.append(DecisionJournalEntryRow.instrument_id == instrument_id)
        if since:
            since_dt = _parse_ts(since)
            if since_dt is not None:
                filters.append(DecisionJournalEntryRow.created_at >= since_dt)
        if event_type:
            filters.append(DecisionJournalEntryRow.event_type == event_type)

        count_stmt = select(func.count()).select_from(DecisionJournalEntryRow).where(*filters)
        count_result = await self._session.execute(count_stmt)
        total = int(count_result.scalar_one())

        stmt = (
            select(DecisionJournalEntryRow)
            .where(*filters)
            .order_by(DecisionJournalEntryRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_record(row) for row in rows], total


# Alias retrocompatible con F1 (JournalWriter DI).
SqlAlchemyJournalWriter = SqlAlchemyJournalRepository
