"""V1.26 — nacimiento SEMI: TradePlan TRIGGERED → Confirm → Fill → PositionState.

La posición conserva identidad del plan y los niveles firmados.
``POST /portfolio/trade`` (HTTP) no es este camino: nace HUMAN_MANUAL.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.persist_position_from_fill import PersistPositionFromFill


def _triggered(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-v126-birth",
        "thesisId": "th-v126",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "quantity": 10.0,
        "riskAmount": 50.0,
        "initialRiskR": 5.0,
        "riskPct": 0.5,
    }
    base.update(overrides)
    return base


def _open_raw(*, plan: dict[str, Any], qty: float = 10.0, price: float = 100.0) -> dict[str, Any]:
    return {
        "decisionId": "dec-v126-birth",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": qty,
        "suggestedPrice": price,
        "tradePlan": plan,
    }


class _OkExecute:
    def __init__(self, tx_id: str = "tx-v126-birth") -> None:
        self.tx_id = tx_id
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("Trade", (), {"transaction_id": self.tx_id})()


class _Store:
    def __init__(self) -> None:
        self.by_tx: dict[str, dict[str, Any]] = {}
        self.open_by_instrument: dict[tuple[str, str], dict[str, Any]] = {}
        self.inserts: list[dict[str, Any]] = []

    async def get_by_open_transaction_id(self, open_transaction_id: str) -> dict[str, Any] | None:
        return self.by_tx.get(open_transaction_id)

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        self.inserts.append(kwargs)
        row = {
            "id": kwargs.get("position_id") or "pos-v126",
            "account_id": kwargs["account_id"],
            "instrument_id": kwargs["instrument_id"],
            "status": kwargs["status"],
            "position_state": kwargs["position_state"],
            "trade_plan_snapshot": kwargs["trade_plan_snapshot"],
            "open_transaction_id": kwargs["open_transaction_id"],
            "position_id": kwargs.get("position_id") or "pos-v126",
        }
        self.by_tx[kwargs["open_transaction_id"]] = row
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        return row


class _Sessions:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_decision_session_by_decision_id(
        self,
        decision_id: str,
        *,
        account_id: str | None = None,
        kind: str | None = "propose",
    ) -> Any | None:
        self.calls.append(decision_id)
        return type(
            "S",
            (),
            {
                "payload": {
                    "runtime": {
                        "decisionPackage": {
                            "instrumentId": "inst-1",
                            "action": "recommend_long",
                            "overallConfidence": 8.0,
                        }
                    }
                }
            },
        )()


@pytest.mark.asyncio
async def test_semi_triggered_confirm_fill_keeps_plan_identity_and_signed_stop() -> None:
    store = _Store()
    sessions = _Sessions()
    fake = _OkExecute()
    uc = ConfirmRecommendationIntent(
        execute_trade=fake,
        position_from_fill=PersistPositionFromFill(store, sessions=sessions),
    )

    result = await uc.execute(
        recommendation_raw=_open_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
        signed_stop=96.0,
    )
    assert result["trade"]["status"] == "executed"
    assert result["positionPersist"]["status"] == "applied"
    assert len(store.inserts) == 1

    snap = store.inserts[0]["trade_plan_snapshot"]
    for key in (
        "decisionId",
        "thesisId",
        "status",
        "entry",
        "structuralStop",
        "target1",
        "target2",
        "riskAmount",
        "initialRiskR",
        "quantity",
        "direction",
    ):
        assert key in snap, f"missing {key} in tradePlanSnapshot"
    assert snap["decisionId"] == "dec-v126-birth"
    assert snap["thesisId"] == "th-v126"
    assert snap["status"] == "TRIGGERED"
    assert snap["entry"] == 100.0
    assert snap["structuralStop"] == 96.0
    assert snap["target1"] == 105.0
    assert snap["target2"] == 110.0
    assert snap["riskAmount"] == 50.0
    assert snap["initialRiskR"] == 5.0
    assert snap["quantity"] == 10.0
    assert snap["direction"] == "long"

    state = store.inserts[0]["position_state"]
    assert state["plannedEntry"] == 100.0
    assert state["actualEntry"] == 100.0
    assert state["initialStop"] == 96.0
    assert state["currentStop"] == 96.0

    origin = state["originDecisionPackage"]
    assert origin["decisionId"] == "dec-v126-birth"
    assert sessions.calls == ["dec-v126-birth"]
