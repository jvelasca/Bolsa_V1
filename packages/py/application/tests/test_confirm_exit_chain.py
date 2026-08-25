"""P3 — Confirm execute: ExitPlan → ExitPermission (ADR-033 §4)."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.evaluate_exit_plan import advisory_exit_plan, semi_exit_permission
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("Trade", (), {"transaction_id": "tx-exit"})()


class _FakeCognitiveStore:
    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    async def get_decision_session(self, session_id: str) -> Any | None:
        return self._session

    async def update_decision_session(self, record: Any) -> Any:
        return record

    async def append_decision_session(self, record: Any) -> Any:
        return record


class _FakeExitStore:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.updates: list[dict[str, Any]] = []

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        if self.row is None:
            return None
        if self.row.get("status") == "CLOSED":
            return None
        if self.row.get("account_id") != account_id:
            return None
        if self.row.get("instrument_id") != instrument_id:
            return None
        return self.row

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        self.updates.append({"status": status, "position_state": position_state})
        self.row = {
            **(self.row or {}),
            "status": status,
            "position_state": position_state,
            "id": position_id,
        }
        return self.row


def _package_session(*, action: str = "recommend_long") -> DecisionSessionRecord:
    return DecisionSessionRecord(
        id="DSS-1",
        kind="propose",
        status="open",
        instrument_id="inst-1",
        created_at="2026-08-25T00:00:00Z",
        decision_id="dec-1",
        payload={
            "decisionId": "dec-1",
            "runtime": {
                "decisionPackage": {
                    "decisionId": "dec-1",
                    "instrumentId": "inst-1",
                    "action": action,
                }
            },
        },
    )


def _open_row() -> dict[str, Any]:
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 105.0,
            "target2": 110.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-25T15:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return {
        "id": "pos-1",
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "status": "OPEN",
        "position_state": pos.to_dict(),
    }


def _closing_raw(*, qty: float = 10.0, action: str = "exit_hint") -> dict[str, Any]:
    return {
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "action": action,
        "suggestedQuantity": qty,
        "suggestedPrice": 100.0,
    }


@pytest.mark.asyncio
async def test_exit_with_position_no_session_uses_operational_direction() -> None:
    """P4 — cierre desde Consola sin sessionId: side desde Position persistida."""
    fake = _FakeExecuteTrade()
    store = _FakeExitStore(_open_row())
    uc = ConfirmRecommendationIntent(
        cognitive_store=_FakeCognitiveStore(None),
        execute_trade=fake,
        position_from_exit=PersistPositionFromExit(store),
    )
    result = await uc.execute(
        recommendation_raw=_closing_raw(action="exit_hint"),
        account_id="acc-1",
        execute=True,
        session_id=None,
    )
    assert result["trade"]["status"] == "executed"
    assert fake.calls[0]["trade_type"] == "sell"
    assert len(store.updates) == 1


@pytest.mark.asyncio
async def test_exit_without_position_fills_legacy() -> None:
    fake = _FakeExecuteTrade()
    store = _FakeExitStore(None)
    uc = ConfirmRecommendationIntent(
        cognitive_store=_FakeCognitiveStore(_package_session()),
        execute_trade=fake,
        position_from_exit=PersistPositionFromExit(store),
    )
    result = await uc.execute(
        recommendation_raw=_closing_raw(),
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )
    assert result["trade"]["status"] == "executed"
    assert fake.calls[0]["trade_type"] == "sell"
    assert store.updates == []


@pytest.mark.asyncio
async def test_exit_with_position_allows_and_reduces() -> None:
    fake = _FakeExecuteTrade()
    store = _FakeExitStore(_open_row())
    uc = ConfirmRecommendationIntent(
        cognitive_store=_FakeCognitiveStore(_package_session()),
        execute_trade=fake,
        position_from_exit=PersistPositionFromExit(store),
    )
    result = await uc.execute(
        recommendation_raw=_closing_raw(),
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )
    assert result["trade"]["status"] == "executed"
    assert len(store.updates) == 1
    assert store.updates[0]["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_corrupt_position_denied_exit_permission() -> None:
    fake = _FakeExecuteTrade()
    store = _FakeExitStore(
        {
            "id": "pos-bad",
            "account_id": "acc-1",
            "instrument_id": "inst-1",
            "status": "OPEN",
            "position_state": {"direction": "long"},
        }
    )
    uc = ConfirmRecommendationIntent(
        cognitive_store=_FakeCognitiveStore(_package_session()),
        execute_trade=fake,
        position_from_exit=PersistPositionFromExit(store),
    )
    result = await uc.execute(
        recommendation_raw=_closing_raw(),
        account_id="acc-1",
        execute=True,
        session_id="DSS-1",
    )
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "exit_permission"
    assert fake.calls == []
    assert store.updates == []


@pytest.mark.asyncio
async def test_execute_false_skips_exit_gate() -> None:
    fake = _FakeExecuteTrade()
    store = _FakeExitStore(
        {
            "id": "pos-bad",
            "account_id": "acc-1",
            "instrument_id": "inst-1",
            "status": "OPEN",
            "position_state": {"direction": "long"},
        }
    )
    uc = ConfirmRecommendationIntent(
        cognitive_store=_FakeCognitiveStore(_package_session()),
        execute_trade=fake,
        position_from_exit=PersistPositionFromExit(store),
    )
    result = await uc.execute(
        recommendation_raw=_closing_raw(),
        account_id="acc-1",
        execute=False,
        session_id="DSS-1",
    )
    assert result["trade"] is None
    assert fake.calls == []
    assert store.updates == []


def test_advisory_idle_without_mark() -> None:
    row = _open_row()
    adv = advisory_exit_plan(row["position_state"], mark_price=None)
    assert adv is not None
    assert adv["suggestedAction"] == "hold"
    assert adv["status"] == "IDLE"


def test_advisory_target1_reduce() -> None:
    row = _open_row()
    adv = advisory_exit_plan(row["position_state"], mark_price=105.0)
    assert adv is not None
    assert adv["primaryReason"] == "TARGET_1"
    assert adv["suggestedAction"] == "reduce"


def test_semi_manual_allows_full_exit() -> None:
    row = _open_row()
    perm = semi_exit_permission(row["position_state"], mark_price=100.0)
    assert perm.allowed is True
    assert perm.action == "full_exit"
    assert perm.verdict == "ALLOW"
