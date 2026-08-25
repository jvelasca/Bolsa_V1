"""P3 — persistir reduce/cierre en PositionState (ADR-033 §4)."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.persist_position_from_exit import (
    LAST_EXIT_TRANSACTION_KEY,
    PersistPositionFromExit,
    PersistPositionFromExitInput,
)


def _triggered_plan(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }
    base.update(overrides)
    return base


class _FakeStore:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row
        self.updates: list[dict[str, Any]] = []

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        if self.row is None:
            return None
        if self.row.get("account_id") != account_id:
            return None
        if self.row.get("instrument_id") != instrument_id:
            return None
        if self.row.get("status") == "CLOSED":
            return None
        return self.row

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        self.updates.append(
            {"position_id": position_id, "status": status, "position_state": position_state}
        )
        if self.row is None:
            return None
        self.row = {
            **self.row,
            "status": status,
            "position_state": position_state,
        }
        return self.row


def _open_row() -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _triggered_plan(),
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


@pytest.mark.asyncio
async def test_reduce_partial_updates_remaining() -> None:
    store = _FakeStore(_open_row())
    uc = PersistPositionFromExit(store)
    row = await uc.persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=4.0,
            fill_price=105.0,
            exit_transaction_id="tx-exit-1",
            filled_at="2026-08-25T16:00:00Z",
        )
    )
    assert row is not None
    assert len(store.updates) == 1
    assert store.updates[0]["status"] == "PARTIAL"
    state = store.updates[0]["position_state"]
    assert state["remainingQuantity"] == 6.0
    assert state[LAST_EXIT_TRANSACTION_KEY] == "tx-exit-1"


@pytest.mark.asyncio
async def test_full_exit_closes() -> None:
    store = _FakeStore(_open_row())
    uc = PersistPositionFromExit(store)
    row = await uc.persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=10.0,
            fill_price=95.0,
            exit_transaction_id="tx-exit-2",
        )
    )
    assert row is not None
    assert store.updates[0]["status"] == "CLOSED"
    assert store.updates[0]["position_state"]["remainingQuantity"] == 0.0


@pytest.mark.asyncio
async def test_same_exit_tx_is_idempotent() -> None:
    store = _FakeStore(_open_row())
    uc = PersistPositionFromExit(store)
    inp = PersistPositionFromExitInput(
        account_id="acc-1",
        instrument_id="inst-1",
        fill_quantity=4.0,
        fill_price=105.0,
        exit_transaction_id="tx-same",
    )
    first = await uc.persist(inp)
    assert first is not None
    second = await uc.persist(inp)
    assert second is not None
    assert len(store.updates) == 1


@pytest.mark.asyncio
async def test_no_open_row_skips() -> None:
    store = _FakeStore(None)
    uc = PersistPositionFromExit(store)
    row = await uc.persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=1.0,
            fill_price=100.0,
            exit_transaction_id="tx-x",
        )
    )
    assert row is None
    assert store.updates == []
