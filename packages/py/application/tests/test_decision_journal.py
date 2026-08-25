"""ADR-029 F1 — DecisionJournal + OrderProposal mapper/writer/hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from bolsa_domain.entities.cognitive_artifacts import (
    DecisionJournalEntryRecord,
    DecisionSessionRecord,
)

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.journal_writer import append_journal_event
from bolsa_application.order_proposal_mapper import session_to_order_proposal
from bolsa_application.propose_recommendation import ProposeRecommendationFromTa


class InMemoryJournalWriter:
    def __init__(self) -> None:
        self.entries: list[DecisionJournalEntryRecord] = []

    async def append(self, entry: DecisionJournalEntryRecord) -> DecisionJournalEntryRecord:
        self.entries.append(entry)
        return entry


def _propose_session_record(**overrides: Any) -> DecisionSessionRecord:
    base = {
        "id": "sess-propose-1",
        "kind": "propose",
        "status": "open",
        "instrument_id": "inst-1",
        "created_at": "2026-08-24T10:00:00Z",
        "account_id": "acct-demo",
        "recommendation_id": "rec-1",
        "decision_id": "dec-1",
        "payload": {
            "sessionId": "sess-propose-1",
            "decisionId": "dec-1",
            "recommendationId": "rec-1",
            "recommendation": {"status": "awaiting_human", "recommendationId": "rec-1"},
        },
    }
    base.update(overrides)
    return DecisionSessionRecord(**base)


def test_session_to_order_proposal_open():
    proposal = session_to_order_proposal(_propose_session_record())
    assert proposal is not None
    assert proposal["proposalId"] == "sess-propose-1"
    assert proposal["decisionId"] == "dec-1"
    assert proposal["recommendationId"] == "rec-1"
    assert proposal["status"] == "open"
    assert proposal["closedAt"] is None


def test_session_to_order_proposal_rejected_from_recommendation():
    rec = _propose_session_record(
        status="closed",
        payload={
            "recommendation": {"status": "rejected", "recommendationId": "rec-1"},
            "decisionId": "dec-1",
        },
    )
    proposal = session_to_order_proposal(rec)
    assert proposal is not None
    assert proposal["status"] == "rejected"


def test_session_to_order_proposal_non_propose_returns_none():
    rec = _propose_session_record(kind="confirm")
    assert session_to_order_proposal(rec) is None


def test_session_to_order_proposal_missing_ids_returns_none():
    rec = _propose_session_record(decision_id=None, recommendation_id=None, payload={})
    assert session_to_order_proposal(rec) is None


@pytest.mark.asyncio
async def test_journal_writer_append():
    writer = InMemoryJournalWriter()
    entry = DecisionJournalEntryRecord(
        id="JNL-test",
        decision_id="dec-1",
        event_type="proposal_recorded",
        actor="system",
        created_at="2026-08-24T10:00:00Z",
        account_id="acct-demo",
        instrument_id="inst-1",
    )
    await writer.append(entry)
    assert len(writer.entries) == 1
    assert writer.entries[0].event_type == "proposal_recorded"


@pytest.mark.asyncio
async def test_append_journal_event_best_effort_swallows_errors():
    class _BrokenWriter:
        async def append(self, entry: DecisionJournalEntryRecord) -> DecisionJournalEntryRecord:
            raise RuntimeError("db down")

    await append_journal_event(
        _BrokenWriter(),
        event_type="proposal_recorded",
        decision_id="dec-1",
    )


@pytest.mark.asyncio
async def test_append_journal_event_noop_without_writer():
    await append_journal_event(
        None,
        event_type="proposal_recorded",
        decision_id="dec-1",
    )


@dataclass
class _FakeCognitiveStore:
    sessions: list[Any] = field(default_factory=list)

    async def append_decision_session(self, record: Any) -> Any:
        self.sessions.append(record)
        return record


@pytest.mark.asyncio
async def test_propose_hook_records_proposal_journal(monkeypatch: pytest.MonkeyPatch):
    """Smoke: propose best-effort journal tras append_decision_session."""
    from datetime import UTC, datetime

    from bolsa_analytics.features.models import FeatureSnapshot

    import bolsa_application.propose_recommendation as mod

    bars = []
    for _i in range(80):
        bars.append(
            type(
                "Bar",
                (),
                {
                    "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1_000_000,
                },
            )()
        )

    class _Ohlcv:
        async def get_bars(self, instrument_id: str, *, timeframe, limit: int):
            return bars[:limit]

    class _Port:
        _snap = None

        def put_latest(self, snap) -> None:
            self._snap = snap

        def get_latest(self, instrument_id: str, feature_set_id: str):
            return self._snap

    port = _Port()
    journal = InMemoryJournalWriter()
    cognitive = _FakeCognitiveStore()

    def fake_materialize(feature_port, *, instrument_id, bars, feature_set_id):
        snap = FeatureSnapshot(
            instrument_id=instrument_id,
            timestamp=datetime(2026, 3, 20, tzinfo=UTC),
            feature_set_id=feature_set_id,
            composition_hash="test",
            values={
                "rsi_14_close": 62.0,
                "adx_14": 28.0,
                "plus_di_14": 28.0,
                "minus_di_14": 12.0,
                "obv_slope": 1.0,
                "price_slope": 0.5,
                "bb_width_pct": 4.0,
                "atr_14": 1.2,
                "atr_percentile": 40.0,
                "close": 100.5,
                "sma_20_close": 99.0,
                "sma_50_close": 98.0,
            },
        )
        feature_port.put_latest(snap)
        return snap

    monkeypatch.setattr(mod, "materialize_feature_snapshot", fake_materialize)

    uc = ProposeRecommendationFromTa(
        _Ohlcv(),
        port,
        cognitive_store=cognitive,
        journal_writer=journal,
    )
    result = await uc.execute(
        instrument_id="inst-1",
        suggested_quantity=10,
        suggested_price=100.0,
        account_id="acct-demo",
    )
    assert result.recommendation.decision_id
    assert len(cognitive.sessions) == 1
    assert any(e.event_type == "proposal_recorded" for e in journal.entries)


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)

        class _Txn:
            id = "txn-123"

        return type("Result", (), {"transaction": _Txn()})()


@pytest.mark.asyncio
async def test_confirm_hook_contract_and_executed_journal():
    journal = InMemoryJournalWriter()
    fake_trade = _FakeExecuteTrade()
    uc = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        journal_writer=journal,
    )
    raw = {
        "recommendationId": "rec-1",
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 5,
        "suggestedPrice": 100.0,
        "metrics": {
            "confidence": 0.8,
            "consensus": 0.7,
            "evidenceStrength": 0.6,
            "stability": 0.5,
            "conviction": 0.4,
        },
        "createdAt": "2026-08-24T10:00:00Z",
    }
    await uc.execute(
        recommendation_raw=raw,
        account_id="acct-demo",
        execute=True,
        session_id=None,
    )
    event_types = [e.event_type for e in journal.entries]
    assert "contract_absent" in event_types
    assert "human_confirm" in event_types
    assert "executed" in event_types
    executed = next(e for e in journal.entries if e.event_type == "executed")
    assert executed.payload is not None
    assert executed.payload.get("status") == "executed"


@pytest.mark.asyncio
async def test_confirm_hook_risk_veto_journal():
    journal = InMemoryJournalWriter()

    class _Summary:
        total_equity = 10_000.0
        positions = []

    class _PortfolioSummary:
        async def execute(self, *, account_id: str) -> _Summary:
            return _Summary()

    class _Instruments:
        async def get_by_id(self, instrument_id: str) -> Any:
            return None

    uc = ConfirmRecommendationIntent(
        execute_trade=_FakeExecuteTrade(),
        portfolio_summary=_PortfolioSummary(),
        instruments=_Instruments(),
        journal_writer=journal,
    )

    async def deny_risk(*args: Any, **kwargs: Any) -> bool:
        return False

    uc._risk_allows_opening = deny_risk  # type: ignore[method-assign]

    raw = {
        "recommendationId": "rec-1",
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 5,
        "suggestedPrice": 100.0,
        "metrics": {
            "confidence": 0.8,
            "consensus": 0.7,
            "evidenceStrength": 0.6,
            "stability": 0.5,
            "conviction": 0.4,
        },
        "createdAt": "2026-08-24T10:00:00Z",
    }
    await uc.execute(
        recommendation_raw=raw,
        account_id="acct-demo",
        execute=True,
        session_id=None,
    )
    assert any(e.event_type == "risk_veto" for e in journal.entries)
    assert any(e.event_type == "gate_evaluated" for e in journal.entries)
    assert any(e.event_type == "human_confirm" for e in journal.entries)


def test_attribution_setup_payload_from_plan_and_anchor():
    from bolsa_application.journal_writer import attribution_setup_payload

    snap = attribution_setup_payload(
        {
            "entrySetup": "wyckoff",
            "status": "ARMED",
        },
        anchor={"phase": "lps", "effort": "result_ok"},
        base={"status": "open"},
    )
    assert snap["status"] == "open"
    assert snap["entrySetup"] == "wyckoff"
    assert snap["tradePlanStatus"] == "ARMED"
    assert snap["phase"] == "lps"
    assert snap["effort"] == "result_ok"
    assert attribution_setup_payload(None) == {}
    assert attribution_setup_payload({"status": "WATCH"}) == {
        "tradePlanStatus": "WATCH"
    }
