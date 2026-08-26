"""SEMI E2E — TradePlan TRIGGERED → Confirm execute → protect (ADR-034).

Cadena application (sin browser): apertura SEMI + PositionState OPEN + protect
cero ledger. Honesty OI-1/2/3/4 + PH-1 persist None. ≠ broker live.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect


def _triggered(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-semi-e2e",
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


def _open_raw(*, plan: dict[str, Any] | None, qty: float = 10.0) -> dict[str, Any]:
    return {
        "decisionId": "dec-semi-e2e",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": qty,
        "suggestedPrice": 100.0,
        "tradePlan": plan,
    }


def _protect_raw(*, suggested_stop: float, current_stop: float = 95.0) -> dict[str, Any]:
    return {
        "decisionId": "dec-semi-protect",
        "instrumentId": "inst-1",
        "action": "wait",
        "suggestedQuantity": 10.0,
        "suggestedPrice": suggested_stop,
        "decisionPackage": {
            "operativaIntent": "protect",
            "suggestedStop": suggested_stop,
            "currentStop": current_stop,
            "direction": "long",
            "stopOverrideRequired": False,
        },
    }


class _OkExecute:
    def __init__(self, tx_id: str = "tx-semi-e2e") -> None:
        self.tx_id = tx_id
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("Trade", (), {"transaction_id": self.tx_id})()


class _ChainStore:
    """Store en memoria: fill insert + protect update_state (mismo escenario)."""

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
            "id": kwargs.get("position_id") or "pos-semi",
            "account_id": kwargs["account_id"],
            "instrument_id": kwargs["instrument_id"],
            "status": kwargs["status"],
            "position_state": kwargs["position_state"],
            "open_transaction_id": kwargs["open_transaction_id"],
            "position_id": kwargs.get("position_id") or "pos-semi",
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
        self.updates.append(
            {"position_id": position_id, "status": status, "position_state": position_state}
        )
        # Localizar fila abierta y mutar status/stop.
        for key, row in list(self.open_by_instrument.items()):
            if row.get("id") == position_id or row.get("position_id") == position_id:
                updated = {**row, "status": status, "position_state": position_state}
                self.open_by_instrument[key] = updated
                tx = row.get("open_transaction_id")
                if isinstance(tx, str) and tx in self.by_tx:
                    self.by_tx[tx] = updated
                return updated
        return {
            "id": position_id,
            "status": status,
            "position_state": position_state,
        }


def _uc(store: _ChainStore, execute: _OkExecute) -> ConfirmRecommendationIntent:
    return ConfirmRecommendationIntent(
        execute_trade=execute,
        position_from_fill=PersistPositionFromFill(store),
        position_from_protect=PersistPositionFromProtect(store),
    )


@pytest.mark.asyncio
async def test_triggered_confirm_fill_then_protect_updates_stop() -> None:
    """Happy path: TRIGGERED → OPEN (stop 95) → protect 98 → currentStop 98, OPEN."""
    store = _ChainStore()
    fake = _OkExecute()
    uc = _uc(store, fake)

    open_result = await uc.execute(
        recommendation_raw=_open_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert open_result["trade"]["status"] == "executed"
    assert open_result["executionRecord"]["outcome"] == "executed"
    assert open_result["paperOrder"]["status"] == "FILLED"
    assert open_result["paperOrder"]["venue"] == "PAPER"
    assert open_result["positionPersist"]["status"] == "applied"
    assert len(fake.calls) == 1
    assert len(store.inserts) == 1
    row = store.open_by_instrument[("acc-1", "inst-1")]
    assert row["status"] == "OPEN"
    assert row["position_state"]["currentStop"] == 95.0
    assert row["position_state"]["initialStop"] == 95.0

    protect_result = await uc.execute(
        recommendation_raw=_protect_raw(suggested_stop=98.0, current_stop=95.0),
        account_id="acc-1",
        execute=True,
    )
    assert protect_result["trade"]["status"] == "protect_applied"
    assert protect_result["positionPersist"]["status"] == "applied"
    assert protect_result["intent"]["status"] == "executed"
    assert len(fake.calls) == 1  # protect = cero ledger
    assert "paperOrder" not in protect_result
    assert len(store.updates) == 1
    after = store.open_by_instrument[("acc-1", "inst-1")]
    assert after["position_state"]["currentStop"] == 98.0
    assert after["status"] == "OPEN"


@pytest.mark.asyncio
async def test_triggered_confirm_then_protect_be_becomes_protected() -> None:
    """Protect a break-even (stop ≥ entry) → status PROTECTED."""
    store = _ChainStore()
    fake = _OkExecute("tx-be")
    uc = _uc(store, fake)

    await uc.execute(
        recommendation_raw=_open_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    protect_result = await uc.execute(
        recommendation_raw=_protect_raw(suggested_stop=100.0, current_stop=95.0),
        account_id="acc-1",
        execute=True,
    )
    assert protect_result["trade"]["status"] == "protect_applied"
    after = store.open_by_instrument[("acc-1", "inst-1")]
    assert after["position_state"]["currentStop"] == 100.0
    assert after["status"] == "PROTECTED"
    assert after["position_state"]["status"] == "PROTECTED"


@pytest.mark.asyncio
async def test_without_triggered_plan_no_open_no_protect_target() -> None:
    """OI-2 fail-closed: sin TRIGGERED no abre; store vacío → protect no muta."""
    store = _ChainStore()
    fake = _OkExecute("tx-blocked")
    uc = _uc(store, fake)

    open_result = await uc.execute(
        recommendation_raw=_open_raw(plan=None),
        account_id="acc-1",
        execute=True,
    )
    assert open_result["trade"]["status"] == "rejected_by_gate"
    assert open_result["trade"]["reason"] == "risk_signature"
    assert fake.calls == []
    assert store.inserts == []
    assert "paperOrder" not in open_result
    assert open_result["executionRecord"]["outcome"] == "not_executed"

    watch_result = await uc.execute(
        recommendation_raw=_open_raw(plan=_triggered(status="WATCH")),
        account_id="acc-1",
        execute=True,
    )
    assert watch_result["trade"]["status"] == "rejected_by_gate"
    assert watch_result["trade"]["reason"] == "risk_signature"
    assert store.inserts == []

    protect_result = await uc.execute(
        recommendation_raw=_protect_raw(suggested_stop=98.0),
        account_id="acc-1",
        execute=True,
    )
    # Sin fila OPEN: ExitPermission niega (missing / not actionable).
    assert protect_result["trade"]["status"] == "rejected_by_gate"
    assert protect_result["trade"]["reason"] == "exit_permission"
    assert store.updates == []
    assert fake.calls == []


@pytest.mark.asyncio
async def test_protect_h2_worsen_without_override_is_not_protect_applied() -> None:
    """PH-1: ExitPermission ALLOW + H2 persist None → skipped, stop intacto."""
    store = _ChainStore()
    fake = _OkExecute()
    uc = _uc(store, fake)

    await uc.execute(
        recommendation_raw=_open_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    before = store.open_by_instrument[("acc-1", "inst-1")]
    assert before["position_state"]["currentStop"] == 95.0

    protect_result = await uc.execute(
        recommendation_raw=_protect_raw(suggested_stop=90.0, current_stop=95.0),
        account_id="acc-1",
        execute=True,
    )
    assert protect_result["trade"]["status"] == "skipped"
    assert protect_result["trade"]["reason"] == "stop_not_applied"
    assert protect_result["positionPersist"]["status"] == "skipped"
    assert protect_result["intent"]["status"] == "authorized"
    assert len(fake.calls) == 1
    assert store.updates == []
    after = store.open_by_instrument[("acc-1", "inst-1")]
    assert after["position_state"]["currentStop"] == 95.0
