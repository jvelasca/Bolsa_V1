"""ADR-029 F2 — Decision Journal: vista SOLO LECTURA del audit trail append-only.

Lista paginada de ``DecisionJournalEntryV1`` por cuenta con filtros opcionales.
No muta estado ni invoca propose/confirm/router.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord


@dataclass(frozen=True, slots=True)
class DecisionJournalEntryView:
    """Entrada del journal expuesta en wire (alineada con ``DecisionJournalEntryV1``)."""

    entry_id: str
    decision_id: str
    event_type: str
    actor: str
    created_at: str
    session_id: str | None = None
    account_id: str | None = None
    instrument_id: str | None = None
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": "ART-DECISION-JOURNAL-ENTRY",
            "schemaVersion": "1.0.0",
            "entryId": self.entry_id,
            "decisionId": self.decision_id,
            "sessionId": self.session_id,
            "accountId": self.account_id,
            "instrumentId": self.instrument_id,
            "eventType": self.event_type,
            "actor": self.actor,
            "payload": self.payload,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class DecisionJournalListResult:
    """Resultado paginado del use-case (la ruta mapea a DTO HTTP)."""

    account_id: str
    entries: list[DecisionJournalEntryView]
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "entries": [e.to_dict() for e in self.entries],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


class JournalReader(Protocol):
    """Puerto de lectura del audit trail append-only."""

    async def list_entries(
        self,
        *,
        account_id: str,
        instrument_id: str | None = None,
        since: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DecisionJournalEntryRecord], int]: ...


def _record_to_view(record: DecisionJournalEntryRecord) -> DecisionJournalEntryView:
    return DecisionJournalEntryView(
        entry_id=record.id,
        decision_id=record.decision_id,
        event_type=record.event_type,
        actor=record.actor,
        created_at=record.created_at,
        session_id=record.session_id,
        account_id=record.account_id,
        instrument_id=record.instrument_id,
        payload=record.payload,
    )


class GetDecisionJournal:
    """Lista paginada de entradas del journal para una cuenta (solo lectura)."""

    def __init__(
        self,
        journal_reader: JournalReader,
        *,
        default_limit: int = 50,
        max_limit: int = 200,
    ) -> None:
        self._journal_reader = journal_reader
        self._default_limit = default_limit
        self._max_limit = max_limit

    async def execute(
        self,
        account_id: str,
        *,
        instrument_id: str | None = None,
        since: str | None = None,
        event_type: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> DecisionJournalListResult:
        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(1, effective_limit), self._max_limit)
        effective_offset = max(0, offset)

        rows, total = await self._journal_reader.list_entries(
            account_id=account_id,
            instrument_id=instrument_id,
            since=since,
            event_type=event_type,
            limit=effective_limit,
            offset=effective_offset,
        )
        return DecisionJournalListResult(
            account_id=account_id,
            entries=[_record_to_view(r) for r in rows],
            total=total,
            limit=effective_limit,
            offset=effective_offset,
        )


__all__ = [
    "DecisionJournalEntryView",
    "DecisionJournalListResult",
    "GetDecisionJournal",
    "JournalReader",
]
