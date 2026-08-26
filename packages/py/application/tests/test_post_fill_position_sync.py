"""OI-1 — post-fill position sync (ADR-034)."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
)
from bolsa_application.post_fill_position_sync import (
    HUMAN_MANUAL_OVERRIDE,
    build_human_manual_trade_plan_snapshot,
    classify_ledger_fill,
    sync_position_after_ledger_fill,
    trade_side_closes_position,
)


def _triggered_plan(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
    }
    base.update(overrides)
    return base


def _open_row(*, direction: str = "long", qty: float = 10.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _triggered_plan(direction=direction),
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-08-26T00:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return {
        "id": "pos-1",
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _FillExitStore:
    def __init__(self, row: dict[str, Any] | None) -> None:
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
    ) -> dict[str, Any]:
        self.updates.append({"status": status, "position_state": position_state})
        self.row = {
            **(self.row or {}),
            "id": position_id,
            "status": status,
            "position_state": position_state,
        }
        return self.row


class _FillStore:
    def __init__(self) -> None:
        self.inserts: list[dict[str, Any]] = []
        self.open_by_instrument: dict[tuple[str, str], dict[str, Any]] = {}

    async def get_by_open_transaction_id(self, open_transaction_id: str) -> dict[str, Any] | None:
        return None

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        row = {"id": kwargs.get("position_id") or "pos-new", **kwargs}
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        return row


def test_classify_closing_long_sell() -> None:
    assert classify_ledger_fill(side="sell", open_row=_open_row()) == "closing"


def test_classify_opening_manual_buy_no_row() -> None:
    assert classify_ledger_fill(side="buy", open_row=None) == "opening_manual"


def test_classify_opening_ai_with_triggered_plan() -> None:
    assert (
        classify_ledger_fill(
            side="buy",
            open_row=None,
            trade_plan_snapshot=_triggered_plan(),
        )
        == "opening_ai"
    )


def test_classify_noop_orphan_sell() -> None:
    assert classify_ledger_fill(side="sell", open_row=None) == "noop"


def test_trade_side_closes_short() -> None:
    assert trade_side_closes_position("short", "buy") is True


def test_manual_snapshot_shape() -> None:
    snap = build_human_manual_trade_plan_snapshot(
        instrument_id="inst-1",
        open_transaction_id="tx-1",
        fill_price=42.0,
    )
    assert snap["origin"] == "HUMAN_MANUAL"
    assert snap["decisionId"] == "manual-tx-1"


@pytest.mark.asyncio
async def test_sync_manual_opening_inserts_with_override() -> None:
    store = _FillStore()
    row = await sync_position_after_ledger_fill(
        account_id="acc-1",
        instrument_id="inst-1",
        side="buy",
        fill_price=100.0,
        fill_quantity=5.0,
        trade=type("T", (), {"transaction_id": "tx-manual"})(),
        open_transaction_id="tx-manual",
        position_from_fill=PersistPositionFromFill(store),
        position_from_exit=None,
    )
    assert row is not None
    assert row["birth_override_reason"] == HUMAN_MANUAL_OVERRIDE


@pytest.mark.asyncio
async def test_sync_closing_applies_reduce() -> None:
    exit_store = _FillExitStore(_open_row())
    row = await sync_position_after_ledger_fill(
        account_id="acc-1",
        instrument_id="inst-1",
        side="sell",
        fill_price=101.0,
        fill_quantity=10.0,
        trade=type("T", (), {"transaction_id": "tx-exit"})(),
        open_transaction_id="tx-exit",
        position_from_fill=None,
        position_from_exit=PersistPositionFromExit(exit_store),
    )
    assert row is not None
    assert exit_store.updates
    assert exit_store.updates[0]["status"] == "CLOSED"
