"""ConfirmRecommendationIntent echoes TradePlan (PLAN layer; no permiso)."""

from __future__ import annotations

from typing import Any

import pytest
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent

_PLAN_STATUSES = {"WATCH", "ARMED", "TRIGGERED", "BLOCKED", "EXPIRED"}


class _FakeCognitiveStore:
    """Store en memoria para ConfirmRecommendationIntent (get/update/append)."""

    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    async def get_decision_session(self, session_id: str) -> Any | None:
        return self._session

    async def update_decision_session(self, record: Any) -> Any:
        self._session = record
        return record

    async def append_decision_session(self, record: Any) -> Any:
        return record


def _session_record(
    *,
    decision_id: str,
    instrument_id: str,
    action: str = "recommend_long",
    trade_plan: dict[str, Any] | None = None,
    combined_score: float | None = 72.0,
) -> DecisionSessionRecord:
    """Sesión `propose` persistida; opcionalmente con ``runtime.tradePlan``."""
    runtime: dict[str, Any] = {
        "decisionPackage": {
            "decisionId": decision_id,
            "instrumentId": instrument_id,
            "action": action,
        },
        "combinedScore": combined_score,
    }
    if trade_plan is not None:
        runtime["tradePlan"] = trade_plan
    return DecisionSessionRecord(
        id="DSS-PLAN",
        kind="propose",
        status="open",
        instrument_id=instrument_id,
        created_at="2026-08-24T00:00:00Z",
        decision_id=decision_id,
        payload={"decisionId": decision_id, "runtime": runtime},
    )


def _raw(*, decision_id: str = "DEC-1", **extra: Any) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 5.0,
        "suggestedPrice": 12.0,
        **extra,
    }


@pytest.mark.asyncio
async def test_confirm_echoes_session_trade_plan() -> None:
    """Con execute=False, confirm reenvía ``runtime.tradePlan`` de la sesión."""
    plan = {
        "decisionId": "DEC-1",
        "instrumentId": "inst-1",
        "status": "WATCH",
        "whyNot": ["no_stop"],
        "executionAllowed": False,
    }
    store = _FakeCognitiveStore(
        _session_record(decision_id="DEC-1", instrument_id="inst-1", trade_plan=plan)
    )
    use_case = ConfirmRecommendationIntent(cognitive_store=store)  # type: ignore[arg-type]

    result = await use_case.execute(
        recommendation_raw=_raw(),
        account_id="acc-1",
        execute=False,
        session_id="DSS-PLAN",
    )

    assert result["trade"] is None
    assert result["tradePlan"] == plan
    assert result["tradePlan"]["status"] in _PLAN_STATUSES
    assert isinstance(result["tradePlan"]["whyNot"], list)
    assert result["tradePlan"]["decisionId"] == "DEC-1"


@pytest.mark.asyncio
async def test_confirm_raw_trade_plan_wins_over_session() -> None:
    """``raw.tradePlan`` tiene prioridad sobre la sesión propose."""
    raw_plan = {
        "decisionId": "DEC-1",
        "status": "BLOCKED",
        "whyNot": ["fit"],
        "executionAllowed": False,
    }
    session_plan = {
        "decisionId": "DEC-1",
        "status": "WATCH",
        "whyNot": ["no_stop"],
        "executionAllowed": False,
    }
    store = _FakeCognitiveStore(
        _session_record(
            decision_id="DEC-1", instrument_id="inst-1", trade_plan=session_plan
        )
    )
    use_case = ConfirmRecommendationIntent(cognitive_store=store)  # type: ignore[arg-type]

    result = await use_case.execute(
        recommendation_raw=_raw(tradePlan=raw_plan),
        account_id="acc-1",
        execute=False,
        session_id="DSS-PLAN",
    )

    assert result["trade"] is None
    assert result["tradePlan"] == raw_plan


@pytest.mark.asyncio
async def test_confirm_rebuilds_v0_trade_plan_when_absent() -> None:
    """Sin tradePlan en raw ni sesión → rebuild v0 (WATCH por no_stop; no fill)."""
    store = _FakeCognitiveStore(
        _session_record(decision_id="DEC-1", instrument_id="inst-1")
    )
    use_case = ConfirmRecommendationIntent(cognitive_store=store)  # type: ignore[arg-type]

    result = await use_case.execute(
        recommendation_raw=_raw(),
        account_id="acc-1",
        execute=False,
        session_id="DSS-PLAN",
    )

    plan = result["tradePlan"]
    assert result["trade"] is None
    assert isinstance(plan, dict)
    assert plan["status"] in _PLAN_STATUSES
    assert isinstance(plan["whyNot"], list)
    assert plan["decisionId"] == "DEC-1"
    assert plan["status"] == "WATCH"
    assert "no_stop" in plan["whyNot"]
    assert plan["executionAllowed"] is False


@pytest.mark.asyncio
async def test_confirm_rebuilds_expired_when_ttl_past() -> None:
    """``expiresAt`` en el pasado → rebuild con status EXPIRED (sin fill)."""
    use_case = ConfirmRecommendationIntent()

    result = await use_case.execute(
        recommendation_raw=_raw(expiresAt="2020-01-01T00:00:00Z"),
        account_id="acc-1",
        execute=False,
    )

    plan = result["tradePlan"]
    assert result["trade"] is None
    assert plan["status"] == "EXPIRED"
    assert "expired" in plan["whyNot"]
    assert plan["decisionId"] == "DEC-1"
    assert plan["executionAllowed"] is False
