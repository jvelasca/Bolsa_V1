"""P4 — RecordSessionVerdict → journal session_verdict."""

from __future__ import annotations

import pytest

from bolsa_application.record_session_verdict import RecordSessionVerdict


class _FakeJournal:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    async def append(self, entry: object) -> object:
        self.entries.append(
            {
                "event_type": getattr(entry, "event_type", None),
                "decision_id": getattr(entry, "decision_id", None),
                "account_id": getattr(entry, "account_id", None),
                "actor": getattr(entry, "actor", None),
                "payload": getattr(entry, "payload", None),
            }
        )
        return entry


@pytest.mark.asyncio
async def test_record_no_trade_session_verdict() -> None:
    journal = _FakeJournal()
    uc = RecordSessionVerdict(journal_writer=journal)
    result = await uc.execute(account_id="acc-1", verdict="no_trade", note="Mercado sin edge")
    assert result["sessionVerdict"] == "no_trade"
    assert result["decisionId"].startswith("SESSION-acc-1-")
    assert len(journal.entries) == 1
    row = journal.entries[0]
    assert row["event_type"] == "session_verdict"
    assert row["account_id"] == "acc-1"
    assert row["actor"] == "human"
    payload = row["payload"]
    assert isinstance(payload, dict)
    assert payload.get("sessionVerdict") == "no_trade"
    assert payload.get("note") == "Mercado sin edge"


@pytest.mark.asyncio
async def test_record_unsupported_verdict_raises() -> None:
    uc = RecordSessionVerdict(journal_writer=_FakeJournal())
    with pytest.raises(ValueError, match="no soportado"):
        await uc.execute(account_id="acc-1", verdict="buy_anyway")
