"""ADR-029 F2 — GetDecisionJournal: vista de solo lectura del audit trail."""

from __future__ import annotations

from typing import Any

import pytest
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

from bolsa_application.decision_journal import GetDecisionJournal


def _entry(
    *,
    entry_id: str,
    event_type: str = "proposal_recorded",
    created_at: str = "2026-08-24T10:00:00Z",
    instrument_id: str | None = "inst-1",
    session_id: str | None = "sess-1",
) -> DecisionJournalEntryRecord:
    return DecisionJournalEntryRecord(
        id=entry_id,
        decision_id="dec-1",
        event_type=event_type,
        actor="system",
        created_at=created_at,
        session_id=session_id,
        account_id="acc-1",
        instrument_id=instrument_id,
        payload={"status": "open"},
    )


class _FakeJournalReader:
    def __init__(self, entries: list[DecisionJournalEntryRecord], total: int | None = None) -> None:
        self._entries = entries
        self._total = total if total is not None else len(entries)
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append(
            {
                "account_id": account_id,
                "instrument_id": instrument_id,
                "since": since,
                "event_type": event_type,
                "limit": limit,
                "offset": offset,
            }
        )
        return self._entries, self._total


@pytest.mark.asyncio
async def test_journal_list_maps_entries_and_pagination() -> None:
    entries = [
        _entry(entry_id="JNL-1", event_type="proposal_recorded"),
        _entry(entry_id="JNL-2", event_type="executed", created_at="2026-08-24T11:00:00Z"),
    ]
    reader = _FakeJournalReader(entries, total=42)
    uc = GetDecisionJournal(reader, default_limit=50, max_limit=200)  # type: ignore[arg-type]
    result = await uc.execute(
        "acc-1",
        instrument_id="inst-1",
        since="2026-08-24T09:00:00Z",
        event_type="executed",
        limit=10,
        offset=5,
    )

    assert reader.calls == [
        {
            "account_id": "acc-1",
            "instrument_id": "inst-1",
            "since": "2026-08-24T09:00:00Z",
            "event_type": "executed",
            "limit": 10,
            "offset": 5,
        }
    ]
    assert result.total == 42
    assert result.limit == 10
    assert result.offset == 5
    assert len(result.entries) == 2
    assert result.entries[0].entry_id == "JNL-1"
    assert result.entries[1].event_type == "executed"


@pytest.mark.asyncio
async def test_journal_list_clamps_limit_and_offset() -> None:
    reader = _FakeJournalReader([])
    uc = GetDecisionJournal(reader, default_limit=25, max_limit=100)  # type: ignore[arg-type]
    await uc.execute("acc-1", limit=500, offset=-3)
    assert reader.calls[0]["limit"] == 100
    assert reader.calls[0]["offset"] == 0

    await uc.execute("acc-1", limit=0)
    assert reader.calls[1]["limit"] == 1


@pytest.mark.asyncio
async def test_journal_list_default_limit() -> None:
    reader = _FakeJournalReader([])
    uc = GetDecisionJournal(reader, default_limit=30)  # type: ignore[arg-type]
    await uc.execute("acc-1")
    assert reader.calls[0]["limit"] == 30


def test_journal_entry_to_dict_matches_v1_wire() -> None:
    from bolsa_application.decision_journal import DecisionJournalEntryView

    view = DecisionJournalEntryView(
        entry_id="JNL-abc",
        decision_id="dec-1",
        event_type="contract_absent",
        actor="system",
        created_at="2026-08-24T10:00:00Z",
        session_id="sess-1",
        account_id="acc-1",
        instrument_id="inst-1",
        payload={"reason": "orphan"},
    )
    assert view.to_dict() == {
        "artifactType": "ART-DECISION-JOURNAL-ENTRY",
        "schemaVersion": "1.0.0",
        "entryId": "JNL-abc",
        "decisionId": "dec-1",
        "sessionId": "sess-1",
        "accountId": "acc-1",
        "instrumentId": "inst-1",
        "eventType": "contract_absent",
        "actor": "system",
        "payload": {"reason": "orphan"},
        "createdAt": "2026-08-24T10:00:00Z",
    }


def test_journal_list_result_to_dict() -> None:
    from bolsa_application.decision_journal import (
        DecisionJournalEntryView,
        DecisionJournalListResult,
    )

    result = DecisionJournalListResult(
        account_id="acc-1",
        entries=[
            DecisionJournalEntryView(
                entry_id="JNL-1",
                decision_id="dec-1",
                event_type="proposal_recorded",
                actor="system",
                created_at="2026-08-24T10:00:00Z",
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )
    data = result.to_dict()
    assert data["accountId"] == "acc-1"
    assert data["total"] == 1
    assert data["entries"][0]["entryId"] == "JNL-1"
    assert data["entries"][0]["artifactType"] == "ART-DECISION-JOURNAL-ENTRY"
