"""Ciclo 4.9 — Board session TradePlan / anchor echo (spine battery thin)."""

from __future__ import annotations

from typing import Any

import pytest
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

from bolsa_application.decision_board import (
    GetDecisionBoard,
    extract_session_exit_radar,
    extract_session_expectancy,
    extract_session_mfe_mae,
    extract_session_protect_plan,
    extract_session_thesis_health,
    extract_session_trade_plan,
    extract_session_trail_plan,
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
    protect = {
        "status": "protect_hint",
        "target1": 110.0,
        "suggestedProtectStop": 100.0,
        "rMultiple": 1.0,
        "why": ["mfe_ge_1r"],
    }
    exit_radar = {
        "status": "trail_hint",
        "suggestedTrailStop": 105.0,
        "target1": 110.0,
        "rMultiple": 1.5,
        "why": ["mfe_ge_1_5r"],
    }
    mfe_mae = {
        "status": "favorable",
        "mfeR": 1.8,
        "maeR": 0.2,
        "currentR": 0.8,
        "why": ["peak_from_bars", "mfe_ge_1_5r"],
    }
    expectancy = {
        "status": "thin",
        "entrySetup": "wyckoff",
        "n": 1,
        "expectancyR": 0.8,
        "winRate": 1.0,
        "avgWinR": 0.8,
        "avgLossR": None,
        "currentR": 0.8,
        "why": ["not_permission", "live_proxy", "thin_sample"],
    }
    trail_plan = {
        "status": "ratchet",
        "suggestedTrailStop": 115.0,
        "lockedR": 1.5,
        "peakMfeR": 2.5,
        "currentR": 2.0,
        "trailDistanceR": 1.0,
        "why": ["not_permission", "hint_only", "ratchet_lock"],
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
                    "protectPlan": protect,
                    "exitRadar": exit_radar,
                    "mfeMae": mfe_mae,
                    "expectancy": expectancy,
                    "trailPlan": trail_plan,
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
    assert by_id["s-plan"].protect_plan == protect
    assert by_id["s-plan"].exit_radar == exit_radar
    assert by_id["s-plan"].mfe_mae == mfe_mae
    assert by_id["s-plan"].expectancy == expectancy
    assert by_id["s-plan"].trail_plan == trail_plan
    dumped = by_id["s-plan"].to_dict()
    assert dumped["tradePlan"]["status"] == "BLOCKED"
    assert dumped["wyckoffSpringAnchor"]["phase"] == "lps"
    assert dumped["thesisHealth"]["status"] == "review"
    assert dumped["protectPlan"]["status"] == "protect_hint"
    assert dumped["exitRadar"]["status"] == "trail_hint"
    assert dumped["mfeMae"]["status"] == "favorable"
    assert dumped["expectancy"]["status"] == "thin"
    assert dumped["trailPlan"]["status"] == "ratchet"
    assert "tradePlan" not in by_id["s-empty"].to_dict()
    assert "wyckoffSpringAnchor" not in by_id["s-empty"].to_dict()
    assert "thesisHealth" not in by_id["s-empty"].to_dict()
    assert "protectPlan" not in by_id["s-empty"].to_dict()
    assert "exitRadar" not in by_id["s-empty"].to_dict()
    assert "mfeMae" not in by_id["s-empty"].to_dict()
    assert "expectancy" not in by_id["s-empty"].to_dict()
    assert "trailPlan" not in by_id["s-empty"].to_dict()


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
    assert extract_session_protect_plan(
        {"runtime": {"protect_plan": {"status": "protect_hint", "target1": 110}}}
    ) == {"status": "protect_hint", "target1": 110}
    assert extract_session_exit_radar(
        {"runtime": {"exit_radar": {"status": "exit_hint", "why": ["thesis_exit"]}}}
    ) == {"status": "exit_hint", "why": ["thesis_exit"]}
    assert extract_session_mfe_mae(
        {"runtime": {"mfe_mae": {"status": "observe", "mfeR": 0.5}}}
    ) == {"status": "observe", "mfeR": 0.5}
    assert extract_session_expectancy(
        {"runtime": {"expectancy": {"status": "thin", "n": 1, "expectancyR": 0.2}}}
    ) == {"status": "thin", "n": 1, "expectancyR": 0.2}
    assert extract_session_trail_plan(
        {"runtime": {"trail_plan": {"status": "tip", "lockedR": 0.5}}}
    ) == {"status": "tip", "lockedR": 0.5}
