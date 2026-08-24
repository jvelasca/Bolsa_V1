"""DecisionJournal — puerto append-only + helper best-effort (ADR-029 F1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord


class JournalWriter(Protocol):
    """Puerto append-only para eventos del spine."""

    async def append(self, entry: DecisionJournalEntryRecord) -> DecisionJournalEntryRecord: ...


async def append_journal_event(
    writer: JournalWriter | None,
    *,
    event_type: str,
    decision_id: str,
    actor: str = "system",
    session_id: str | None = None,
    account_id: str | None = None,
    instrument_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Best-effort: nunca tumba propose/confirm/router."""
    if writer is None or not decision_id:
        return
    try:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        entry = DecisionJournalEntryRecord(
            id=f"JNL-{uuid4().hex[:12]}",
            decision_id=decision_id,
            event_type=event_type,
            actor=actor,
            created_at=now,
            session_id=session_id,
            account_id=account_id,
            instrument_id=instrument_id,
            payload=payload,
        )
        await writer.append(entry)
    except Exception:  # noqa: BLE001 — audit best-effort
        pass
