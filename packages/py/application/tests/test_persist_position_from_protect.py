"""OI-1 — persist protect stop (ADR-034)."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.persist_position_from_protect import (
    PersistPositionFromProtect,
    PersistPositionFromProtectInput,
)


def _open_row(*, current_stop: float = 95.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": current_stop,
        },
        fill_price=100.0,
        fill_quantity=10.0,
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


class _ProtectStore:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.updates: list[dict[str, Any]] = []

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        if self.row is None:
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


@pytest.mark.asyncio
async def test_protect_improves_stop() -> None:
    store = _ProtectStore(_open_row(current_stop=95.0))
    uc = PersistPositionFromProtect(store)
    row = await uc.persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="inst-1",
            suggested_stop=98.0,
        )
    )
    assert row is not None
    assert store.updates[0]["position_state"]["currentStop"] == 98.0
    revisions = store.updates[0]["position_state"]["revisions"]
    assert len(revisions) == 1
    assert revisions[0]["origin"] == "protect"
    assert revisions[0]["previousStop"] == 95.0
    assert revisions[0]["nextStop"] == 98.0


@pytest.mark.asyncio
async def test_trail_origin_improves_stop() -> None:
    store = _ProtectStore(_open_row(current_stop=95.0))
    uc = PersistPositionFromProtect(store)
    row = await uc.persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="inst-1",
            suggested_stop=98.0,
            origin="trail",
        )
    )
    assert row is not None
    revisions = store.updates[0]["position_state"]["revisions"]
    assert len(revisions) == 1
    assert revisions[0]["origin"] == "trail"
    assert revisions[0]["reason"] == "trail_confirm"
    assert store.updates[0]["position_state"]["currentStop"] == 98.0


@pytest.mark.asyncio
async def test_protect_same_stop_no_revision() -> None:
    store = _ProtectStore(_open_row(current_stop=95.0))
    uc = PersistPositionFromProtect(store)
    row = await uc.persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="inst-1",
            suggested_stop=95.0,
            applied_at="2026-08-26T02:00:00Z",
        )
    )
    assert row is not None
    assert store.updates[0]["position_state"]["revisions"] == []


@pytest.mark.asyncio
async def test_protect_worsens_without_override_returns_none() -> None:
    store = _ProtectStore(_open_row(current_stop=98.0))
    uc = PersistPositionFromProtect(store)
    row = await uc.persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="inst-1",
            suggested_stop=95.0,
        )
    )
    assert row is None
    assert store.updates == []
