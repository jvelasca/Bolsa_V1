"""V1.34 B-γ — contrato chart drag → Confirm protect (backend fail-closed).

El frontend puede encolar con allowPendingOverride; el backend exige motivo
auditado para empeorar stop. Stop operativo persistido ≠ orden broker.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect


def _triggered() -> dict[str, Any]:
    return {
        "decisionId": "dec-chart-drag",
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


def _open_raw() -> dict[str, Any]:
    return {
        "decisionId": "dec-chart-drag",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 10.0,
        "suggestedPrice": 100.0,
        "tradePlan": _triggered(),
    }


def _chart_drag_protect_raw(*, signed_stop: float) -> dict[str, Any]:
    """Simula payload protect desde chart drag (signedStop en decisionPackage)."""
    return {
        "decisionId": "dec-chart-drag",
        "instrumentId": "inst-1",
        "action": "wait",
        "suggestedQuantity": 10.0,
        "suggestedPrice": signed_stop,
        "decisionPackage": {
            "operativaIntent": "protect",
            "suggestedStop": signed_stop,
            "currentStop": 95.0,
            "direction": "long",
            "stopOverrideRequired": True,
        },
    }


class _OkExecute:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("Trade", (), {"transaction_id": "tx-chart-drag"})()


class _ChainStore:
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
            "id": kwargs.get("position_id") or "pos-chart",
            "account_id": kwargs["account_id"],
            "instrument_id": kwargs["instrument_id"],
            "status": kwargs["status"],
            "position_state": kwargs["position_state"],
            "open_transaction_id": kwargs["open_transaction_id"],
            "position_id": kwargs.get("position_id") or "pos-chart",
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
        for key, row in list(self.open_by_instrument.items()):
            if row.get("id") == position_id or row.get("position_id") == position_id:
                updated = {**row, "status": status, "position_state": position_state}
                self.open_by_instrument[key] = updated
                tx = row.get("open_transaction_id")
                if isinstance(tx, str) and tx in self.by_tx:
                    self.by_tx[tx] = updated
                return updated
        return {"id": position_id, "status": status, "position_state": position_state}


def _uc(store: _ChainStore, execute: _OkExecute) -> ConfirmRecommendationIntent:
    return ConfirmRecommendationIntent(
        execute_trade=execute,
        position_from_fill=PersistPositionFromFill(store),
        position_from_protect=PersistPositionFromProtect(store),
    )


@pytest.mark.asyncio
async def test_b_gamma_worsening_stop_without_override_denied() -> None:
    """Chart drag empeora stop → Confirm execute sin override → DENY, revision intacta."""
    store = _ChainStore()
    fake = _OkExecute()
    uc = _uc(store, fake)

    await uc.execute(
        recommendation_raw=_open_raw(),
        account_id="acc-1",
        execute=True,
    )
    before = store.open_by_instrument[("acc-1", "inst-1")]
    assert before["position_state"]["currentStop"] == 95.0
    revisions_before = list(before["position_state"].get("revisions") or [])

    result = await uc.execute(
        recommendation_raw=_chart_drag_protect_raw(signed_stop=90.0),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "skipped"
    assert result["trade"]["reason"] == "stop_not_applied"
    assert result["positionPersist"]["status"] == "skipped"
    assert store.updates == []
    after = store.open_by_instrument[("acc-1", "inst-1")]
    assert after["position_state"]["currentStop"] == 95.0
    assert list(after["position_state"].get("revisions") or []) == revisions_before


@pytest.mark.asyncio
async def test_b_gamma_worsening_stop_with_override_applied() -> None:
    """Chart drag empeora stop + motivo auditado → ALLOW → revision protect."""
    store = _ChainStore()
    fake = _OkExecute()
    uc = _uc(store, fake)

    await uc.execute(
        recommendation_raw=_open_raw(),
        account_id="acc-1",
        execute=True,
    )

    result = await uc.execute(
        recommendation_raw=_chart_drag_protect_raw(signed_stop=90.0),
        account_id="acc-1",
        execute=True,
        risk_override_reason="acepto más riesgo tras drag chart",
    )
    assert result["trade"]["status"] == "protect_applied"
    assert result["positionPersist"]["status"] == "applied"
    after = store.open_by_instrument[("acc-1", "inst-1")]
    assert after["position_state"]["currentStop"] == 90.0
    revisions = after["position_state"].get("revisions") or []
    assert len(revisions) >= 1
    last = revisions[-1]
    origin = last.get("origin") if isinstance(last, dict) else last.origin
    assert origin == "protect"
