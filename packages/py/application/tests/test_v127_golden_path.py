"""GOLDEN-PATH-01 — Confirm open → protect → T1 reduce → exit → recon + identidad."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.portfolio_reconciliation import build_portfolio_reconciliation
from bolsa_analytics.cognitive.position_decision import build_position_decision
from bolsa_analytics.cognitive.position_state import position_state_from_dict
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.persist_position_from_exit import (
    PersistPositionFromExit,
    PersistPositionFromExitInput,
)
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_application.persist_position_from_protect import (
    PersistPositionFromProtect,
    PersistPositionFromProtectInput,
)


def _triggered(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-gp01",
        "thesisId": "th-gp01",
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
        "decisionId": "dec-gp01",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": qty,
        "suggestedPrice": price,
        "tradePlan": plan,
    }


class _OkExecute:
    def __init__(self) -> None:
        self.n = 0
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.n += 1
        self.calls.append(kwargs)
        return type("Trade", (), {"transaction_id": f"tx-gp01-{self.n}"})()


class _Store:
    def __init__(self) -> None:
        self.by_tx: dict[str, dict[str, Any]] = {}
        self.open_by_instrument: dict[tuple[str, str], dict[str, Any]] = {}
        self.inserts: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    async def get_by_open_transaction_id(self, open_transaction_id: str) -> dict[str, Any] | None:
        return self.by_tx.get(open_transaction_id)

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        self.inserts.append(kwargs)
        row = {
            "id": kwargs.get("position_id") or "pos-gp01",
            "account_id": kwargs["account_id"],
            "instrument_id": kwargs["instrument_id"],
            "status": kwargs["status"],
            "position_state": kwargs["position_state"],
            "trade_plan_snapshot": kwargs["trade_plan_snapshot"],
            "open_transaction_id": kwargs["open_transaction_id"],
            "position_id": kwargs.get("position_id") or "pos-gp01",
        }
        self.by_tx[kwargs["open_transaction_id"]] = row
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        return row

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        self.updates.append({"status": status, "position_state": position_state})
        key = None
        for k, row in self.open_by_instrument.items():
            if row.get("id") == position_id or row.get("position_id") == position_id:
                key = k
                break
        if key is None:
            key = ("acc-1", "inst-1")
        row = {
            **(self.open_by_instrument.get(key) or {}),
            "id": position_id,
            "status": status,
            "position_state": position_state,
        }
        self.open_by_instrument[key] = row
        if status == "CLOSED":
            self.open_by_instrument.pop(key, None)
        return row


class _Sessions:
    async def get_decision_session_by_decision_id(
        self,
        decision_id: str,
        *,
        account_id: str | None = None,
        kind: str | None = "propose",
    ) -> Any | None:
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
                            "decisionId": decision_id,
                        }
                    }
                }
            },
        )()


@pytest.mark.asyncio
async def test_golden_path_01_entry_protect_t1_exit_recon_identity() -> None:
    store = _Store()
    sessions = _Sessions()
    fake = _OkExecute()
    plan = _triggered()
    uc = ConfirmRecommendationIntent(
        execute_trade=fake,
        position_from_fill=PersistPositionFromFill(store, sessions=sessions),
    )
    opened = await uc.execute(
        recommendation_raw=_open_raw(plan=plan),
        account_id="acc-1",
        execute=True,
        signed_stop=96.0,
    )
    assert opened["trade"]["status"] == "executed"
    snap = store.inserts[0]["trade_plan_snapshot"]
    assert snap["decisionId"] == "dec-gp01"
    assert snap["structuralStop"] == 96.0
    birth = store.inserts[0]["position_state"]
    assert birth["initialStop"] == 96.0
    assert birth["originDecisionPackage"]["decisionId"] == "dec-gp01"

    protected = await PersistPositionFromProtect(store).persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="inst-1",
            suggested_stop=99.0,
        )
    )
    assert protected is not None
    assert protected["position_state"]["currentStop"] == 99.0
    assert protected["position_state"]["initialStop"] == 96.0

    pos = position_state_from_dict(protected["position_state"])
    decision_t1 = build_position_decision(
        pos,
        mark_price=105.0,
        template_id="moderate",
        portfolio_recon_status="clean",
    )
    assert decision_t1 is not None
    assert decision_t1.action == "TAKE_PROFIT"
    assert decision_t1.suggested_qty == 3.0

    reduced = await PersistPositionFromExit(store).persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=3.0,
            fill_price=105.0,
            exit_transaction_id="tx-gp01-t1",
            filled_at="2026-08-28T12:00:00Z",
            mark_target1_achieved=True,
        )
    )
    assert reduced is not None
    st = reduced["position_state"]
    assert st["remainingQuantity"] == 7.0
    assert st["target1AchievedAt"]
    assert st["tradePlanId"] == "dec-gp01"
    assert st["originDecisionPackage"]["decisionId"] == "dec-gp01"
    assert any(r.get("origin") == "reduce" for r in (st.get("revisions") or []))

    pos2 = position_state_from_dict(st)
    decision_t2 = build_position_decision(
        pos2,
        mark_price=110.0,
        template_id="conservative",
        portfolio_recon_status="clean",
    )
    assert decision_t2 is not None
    assert decision_t2.action == "EXIT"

    closed = await PersistPositionFromExit(store).persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=7.0,
            fill_price=110.0,
            exit_transaction_id="tx-gp01-exit",
            filled_at="2026-08-28T13:00:00Z",
            mark_target2_achieved=True,
        )
    )
    assert closed is not None
    final = closed["position_state"]
    assert final["status"] == "CLOSED"
    assert final["remainingQuantity"] == 0.0
    assert final["target2AchievedAt"]
    assert final["originDecisionPackage"]["decisionId"] == "dec-gp01"

    recon = build_portfolio_reconciliation(
        account_id="acc-1",
        portfolio_cash=1000.0,
        ledger_cash_sum=1000.0,
        holdings=[],
        open_positions=[],
    )
    assert recon.status == "clean"
