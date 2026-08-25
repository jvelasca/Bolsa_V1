"""Ciclo 4.9 — Board session TradePlan / anchor echo (spine battery thin)."""

from __future__ import annotations

from typing import Any

import pytest
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

from bolsa_application.decision_board import (
    GetDecisionBoard,
    extract_session_trade_plan,
    extract_session_thesis_health,
    extract_session_wyckoff_anchor,
)


def _session(
    *,
    session_id: str,
    status: str = "open",
    payload: dict[str, Any] | None = None,
) -> DecisionSessionRecord:
    return DecisionSessionRecord(
        id=session_id,
        kind="propose",
        status=status,
        instrument_id="inst-1",
        created_at="2026-08-24T09:00:00Z",
        account_id="acc-1",
        symbol="AAA",
        decision_id="DEC-1",
        payload=payload,
    )


class _FakeCognitive:
    def __init__(self, sessions: list[DecisionSessionRecord]) -> None:
        self._sessions = sessions

    async def list_decision_sessions(
        self, *, limit: int = 50, account_id: str | None = None, instrument_id: str | None = None
    ) -> list[DecisionSessionRecord]:
        return self._sessions


class _FakeF3:
    async def get(self, account_id: str) -> None:
        return None


@pytest.mark.asyncio
async def test_board_echoes_runtime_trade_plan_and_anchor() -> None:
    plan = {
        "decisionId": "DEC-1",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "BLOCKED",
        "quantity": 0,
        "riskPct": 0,
        "whyNot": ["regime"],
        "executionAllowed": False,
        "entrySetup": "wyckoff",
    }
    anchor = {
        "direction": "long",
        "ice": 90.0,
        "springLow": 90.0,
        "springHigh": 92.0,
        "phase": "lps",
        "effort": "result_ok",
    }
    health = {
        "hint": "reduce",
        "status": "review",
        "why": ["confidence_degraded", "stop_intact"],
        "confidence": 0.3,
    }
    sessions = [
        _session(
            session_id="s-plan",
            payload={
                "compliance_check": {"passed": True},
                "runtime": {
                    "tradePlan": plan,
                    "wyckoffSpringAnchor": anchor,
                    "thesisHealth": health,
                },
            },
        ),
        _session(
            session_id="s-empty",
            payload={"compliance_check": {"passed": True}, "runtime": {}},
        ),
    ]
    uc = GetDecisionBoard(
        _FakeCognitive(sessions),  # type: ignore[arg-type]
        _FakeF3(),  # type: ignore[arg-type]
    )
    bundle = await uc.execute("acc-1")
    by_id = {s.session_id: s for s in bundle.decision_sessions}
    assert by_id["s-plan"].trade_plan == plan
    assert by_id["s-plan"].wyckoff_spring_anchor == anchor
    assert by_id["s-plan"].thesis_health == health
    dumped = by_id["s-plan"].to_dict()
    assert dumped["tradePlan"]["status"] == "BLOCKED"
    assert dumped["wyckoffSpringAnchor"]["phase"] == "lps"
    assert dumped["thesisHealth"]["status"] == "review"
    assert "tradePlan" not in by_id["s-empty"].to_dict()
    assert "wyckoffSpringAnchor" not in by_id["s-empty"].to_dict()
    assert "thesisHealth" not in by_id["s-empty"].to_dict()


def test_extract_session_trade_plan_helpers() -> None:
    assert extract_session_trade_plan(None) is None
    assert extract_session_trade_plan({}) is None
    assert extract_session_trade_plan({"runtime": {"tradePlan": {}}}) is None
    assert extract_session_trade_plan({"runtime": {"trade_plan": {"status": "WATCH"}}}) == {
        "status": "WATCH"
    }
    assert extract_session_wyckoff_anchor(
        {"runtime": {"wyckoff_spring_anchor": {"phase": "sos"}}}
    ) == {"phase": "sos"}
    assert extract_session_thesis_health(
        {"runtime": {"thesis_health": {"status": "review", "hint": "exit"}}}
    ) == {"status": "review", "hint": "exit"}
