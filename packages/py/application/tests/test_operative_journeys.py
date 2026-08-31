"""V1.35 — Operative Journey Tests (J01–J06).

Recorridos de negocio end-to-end sobre PositionState + ExitPlan + Confirm.
Reutiliza stores en memoria del decision spine; ≠ browser.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.position_decision import build_position_decision
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.evaluate_exit_plan import semi_exit_permission
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
        "decisionId": "dec-journey",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "quantity": 10.0,
        "riskAmount": 50.0,
    }
    base.update(overrides)
    return base


def _open_raw(*, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "decisionId": "dec-journey",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 10.0,
        "suggestedPrice": 100.0,
        "tradePlan": plan,
    }


class _OkExecute:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("Trade", (), {"transaction_id": "tx-journey"})()


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
            "id": kwargs.get("position_id") or "pos-journey",
            "account_id": kwargs["account_id"],
            "instrument_id": kwargs["instrument_id"],
            "status": kwargs["status"],
            "position_state": kwargs["position_state"],
            "trade_plan_snapshot": kwargs.get("trade_plan_snapshot"),
            "open_transaction_id": kwargs["open_transaction_id"],
            "position_id": kwargs.get("position_id") or "pos-journey",
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


def _filled_position(**overrides: object) -> Any:
    pos = build_position_state_from_fill(
        _triggered(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-28T10:00:00Z",
        position_id="pos-journey",
    )
    assert pos is not None
    blob = {**pos.to_dict(), **overrides}
    return position_state_from_dict(blob)


@pytest.mark.asyncio
async def test_journey_01_buy_confirm_fill_position() -> None:
    """J01 — TradePlan TRIGGERED → Confirm → Fill → Position OPEN."""
    store = _Store()
    uc = ConfirmRecommendationIntent(
        execute_trade=_OkExecute(),
        position_from_fill=PersistPositionFromFill(store),
    )
    result = await uc.execute(
        recommendation_raw=_open_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
        signed_stop=95.0,
    )
    assert result["trade"]["status"] == "executed"
    row = store.open_by_instrument[("acc-1", "inst-1")]
    st = row["position_state"]
    assert row["status"] == "OPEN"
    assert st["currentStop"] == 95.0
    assert st["target1"] == 105.0
    assert st["target2"] == 110.0
    assert st["remainingQuantity"] == 10.0


@pytest.mark.asyncio
async def test_journey_02_t1_reduce_partial() -> None:
    """J02 — T1 alcanzado → reduce 30% (moderate) → PARTIAL."""
    pos = _filled_position()
    decision = build_position_decision(
        pos,
        mark_price=105.0,
        template_id="moderate",
        portfolio_recon_status="clean",
    )
    assert decision is not None
    assert decision.action == "TAKE_PROFIT"
    assert decision.suggested_qty == 3.0

    store = _Store()
    store.open_by_instrument[("acc-1", "inst-1")] = {
        "id": "pos-journey",
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "status": "OPEN",
        "position_state": pos.to_dict(),
    }
    reduced = await PersistPositionFromExit(store).persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=3.0,
            fill_price=105.0,
            exit_transaction_id="tx-t1",
            filled_at="2026-08-28T12:00:00Z",
            mark_target1_achieved=True,
        )
    )
    assert reduced is not None
    st = reduced["position_state"]
    assert st["remainingQuantity"] == 7.0
    assert st["target1AchievedAt"]
    assert reduced["status"] == "PARTIAL"


@pytest.mark.asyncio
async def test_journey_03_t2_does_not_re_emit_t1() -> None:
    """J03 — T2 alcanzado no re-ejecuta política T1."""
    pos = _filled_position(
        target1AchievedAt="2026-08-28T12:00:00Z",
        remainingQuantity=7.0,
        quantity=10.0,
    )
    plan = build_exit_plan_from_position(
        pos,
        mark_price=110.0,
        exit_policy=None,
        at="2026-08-28T13:00:00Z",
    )
    assert plan is not None
    assert plan.primary_reason == "TARGET_2"
    assert plan.primary_reason != "TARGET_1"

    decision = build_position_decision(
        pos,
        mark_price=110.0,
        template_id="moderate",
        portfolio_recon_status="clean",
    )
    assert decision is not None
    assert decision.next_event == "T2"
    assert decision.suggested_qty == pytest.approx(2.1, rel=1e-3)


@pytest.mark.asyncio
async def test_journey_04_structural_stop_exit() -> None:
    """J04 — mark ≤ stop → STRUCTURAL_STOP → EXIT permitido."""
    pos = _filled_position()
    decision = build_position_decision(
        pos,
        mark_price=94.0,
        template_id="moderate",
        portfolio_recon_status="clean",
    )
    assert decision is not None
    assert decision.action == "EXIT"
    assert decision.next_event == "STOP"
    assert decision.primary_reason == "STRUCTURAL_STOP"

    perm = semi_exit_permission(pos.to_dict(), mark_price=94.0)
    assert perm.allowed is True


@pytest.mark.asyncio
async def test_journey_05_trail_protect_revision() -> None:
    """J05 — trail/protect mejora stop → revision auditada."""
    pos = _filled_position()
    updated = apply_position_current_stop(
        pos,
        98.0,
        at="2026-08-28T11:00:00Z",
        origin="protect",
        reason="trail ratchet",
    )
    assert updated is not None
    assert updated.current_stop == 98.0
    revisions = updated.revisions or []
    assert len(revisions) >= 1
    assert revisions[-1].origin == "protect"

    store = _Store()
    store.open_by_instrument[("acc-1", "inst-1")] = {
        "id": "pos-journey",
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "status": "OPEN",
        "position_state": pos.to_dict(),
    }
    applied = await PersistPositionFromProtect(store).persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="inst-1",
            suggested_stop=98.0,
        )
    )
    assert applied is not None
    assert applied["position_state"]["currentStop"] == 98.0


@pytest.mark.asyncio
async def test_journey_06_recon_drift_blocks() -> None:
    """J06 — drift → CRITICAL → BLOCKED → REVIEW / RECONCILIATION."""
    pos = _filled_position()
    decision = build_position_decision(
        pos,
        mark_price=102.0,
        template_id="moderate",
        portfolio_recon_status="drift",
    )
    assert decision is not None
    assert decision.recon_health == "CRITICAL"
    assert decision.attention == "BLOCKED"
    assert decision.action == "REVIEW"
    assert decision.next_event == "RECONCILIATION"
    assert decision.reason == "reconciliation:portfolio_drift"
