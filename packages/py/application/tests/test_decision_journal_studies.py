"""ADR-036 — GetDecisionJournalStudies: proyección de tesis, sin duplicar TradePlan."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from bolsa_application.decision_journal_studies import (
    GetDecisionJournalStudies,
    journal_study_geometry,
    map_journal_study_period,
    map_journal_study_status,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord


def _session(
    *,
    session_id: str = "s1",
    instrument_id: str = "inst-1",
    symbol: str = "AAPL",
    kind: str = "propose",
    action: str = "wait",
    bias: str = "neutral",
    trade_plan: dict[str, Any] | None = None,
    created_at: str = "2026-08-26T09:32:00Z",
) -> DecisionSessionRecord:
    plan = trade_plan if trade_plan is not None else {
        "status": "WATCH",
        "direction": "none",
        "whyNot": ["no_stop"],
        "entry": 12.23,
        "structuralStop": 10.0,
        "target1": 15.34,
        "quantity": 0,
        "executionAllowed": False,
    }
    payload = {
        "sessionId": session_id,
        "kind": kind,
        "timeframe": "1d",
        "assessments": [{"type": "technical", "metadata": {"bias": bias}}],
        "runtime": {
            "decisionPackage": {
                "action": action,
                "overallConfidence": 0.61,
                "timestamp": created_at,
                "notes": ["Sin ventaja suficiente."],
            },
            "tradePlan": plan,
        },
        "recommendation": {"status": "open"},
    }
    return DecisionSessionRecord(
        id=session_id,
        kind=kind,
        status="open",
        instrument_id=instrument_id,
        created_at=created_at,
        account_id="acc-1",
        symbol=symbol,
        decision_id="dec-1",
        payload=payload,
    )


class _FakeSessions:
    def __init__(self, rows: list[DecisionSessionRecord]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    async def list_decision_sessions(
        self,
        *,
        limit: int = 50,
        account_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[DecisionSessionRecord]:
        self.calls.append(
            {"limit": limit, "account_id": account_id, "instrument_id": instrument_id}
        )
        return list(self.rows)


class _Quote:
    def __init__(self, id: str, name: str) -> None:
        self.id = id
        self.name = name


class _FakeInstruments:
    async def get_quotes_by_ids(self, instrument_ids: list[str]) -> list[_Quote]:
        return [_Quote(i, f"Name {i}") for i in instrument_ids]


def test_watch_geometry_hides_levels() -> None:
    geo = journal_study_geometry(
        {
            "status": "WATCH",
            "entry": 12.23,
            "structuralStop": 10.0,
            "target1": 15.34,
            "whyNot": ["no_stop"],
            "direction": "long",
        }
    )
    assert geo["hasOperationalPlan"] is False
    assert geo["stop"] is None
    assert geo["target1"] is None


def test_triggered_geometry_exposes_levels() -> None:
    geo = journal_study_geometry(
        {
            "status": "TRIGGERED",
            "direction": "long",
            "entry": 150,
            "structuralStop": 142.3,
            "target1": 158.4,
            "whyNot": [],
        }
    )
    assert geo["hasOperationalPlan"] is True
    assert geo["stop"] == 142.3
    assert geo["target1"] == 158.4


def test_status_watch_no_stop_directional_is_no_target() -> None:
    assert (
        map_journal_study_status(
            action="recommend_long",
            bias="bullish",
            trade_plan_status="WATCH",
            trade_plan_why_not=["no_stop"],
        )
        == "no_target"
    )


def test_period_refuses_horizon() -> None:
    assert map_journal_study_period("1d") == "daily"
    assert map_journal_study_period("swing") is None


@pytest.mark.asyncio
async def test_latest_propose_per_instrument_and_watch_honesty() -> None:
    older = _session(session_id="s-old", created_at="2026-08-20T09:00:00Z")
    newer = _session(session_id="s-new", created_at="2026-08-26T09:32:00Z")
    confirm = _session(session_id="s-c", kind="confirm")
    other = _session(session_id="s-msft", instrument_id="inst-2", symbol="MSFT")
    uc = GetDecisionJournalStudies(
        _FakeSessions([newer, confirm, older, other]),
        instruments=_FakeInstruments(),
    )
    result = await uc.execute(
        "acc-1",
        now=datetime(2026, 8, 26, 11, 32, tzinfo=UTC),
    )
    assert result.total == 2
    ids = {s.instrument_id: s for s in result.studies}
    aapl = ids["inst-1"]
    assert aapl.session_id == "s-new"
    assert aapl.has_operational_plan is False
    assert aapl.stop is None
    assert aapl.target1 is None
    assert aapl.user_thesis is None
    assert aapl.status == "neutral"
    assert aapl.period == "daily"
    assert aapl.name == "Name inst-1"


@pytest.mark.asyncio
async def test_filters_opinion_and_search() -> None:
    bull = _session(
        session_id="s-bull",
        action="recommend_long",
        bias="bullish",
        trade_plan={
            "status": "ARMED",
            "direction": "long",
            "whyNot": [],
            "entry": 150,
            "structuralStop": 142.3,
            "target1": 158.4,
        },
    )
    wait = _session(session_id="s-wait")
    msft = _session(session_id="s-msft", instrument_id="inst-2", symbol="MSFT")
    uc = GetDecisionJournalStudies(
        _FakeSessions([bull, wait, msft]), instruments=_FakeInstruments()
    )
    result = await uc.execute("acc-1", opinion="bullish")
    assert result.total == 1
    assert result.studies[0].session_id == "s-bull"
    assert result.studies[0].has_operational_plan is True

    by_q = await uc.execute("acc-1", q="msft")
    assert by_q.total == 1
    by_aapl = await uc.execute("acc-1", q="aapl")
    assert by_aapl.total == 1
