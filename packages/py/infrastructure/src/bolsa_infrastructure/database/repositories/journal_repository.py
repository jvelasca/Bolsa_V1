"""Persistencia append-only de decision_journal_entries (ADR-029 F1)."""

from __future__ import annotations

from datetime import UTC, datetime

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import DecisionJournalEntryRow


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


class SqlAlchemyJournalWriter:
    """Implementación SQLAlchemy del puerto JournalWriter."""

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
