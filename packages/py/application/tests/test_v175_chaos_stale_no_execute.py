"""V1.75 GP-V175-05..07 — stale dryRun · ENTRY_STALE_DATA · adversarial smoke."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_state import (
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.paper_desk_entry import map_estudio_propose_to_entry_tick
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect
from bolsa_application.position_event_log import claim_durable_event


def _plan(instrument_id: str = "MSFT") -> dict[str, object]:
    return {
        "decisionId": "dec-v175",
        "instrumentId": instrument_id,
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
        "quantity": 10.0,
        "riskAmount": 50.0,
        "initialRiskR": 5.0,
    }


def _open_row(*, instrument_id: str = "MSFT", qty: float = 10.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _plan(instrument_id),
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-09-02T15:00:00Z",
        position_id=f"pos-{instrument_id}",
    )
    assert pos is not None
    return {
        "id": f"pos-{instrument_id}",
        "account_id": "acc-v175",
        "instrument_id": instrument_id,
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _DeskStore:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    async def list_open(self, account_id: str) -> list[dict[str, Any]]:
        _ = account_id
        if self.row.get("status") == "CLOSED":
            return []
        return [self.row]

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        _ = account_id
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
        _ = position_id
        self.row = {**self.row, "status": status, "position_state": position_state}
        return self.row

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        _ = expected_stop
        return await self.update_state(
            position_id=position_id, status=status, position_state=position_state
        )


class _IdempotentSell:
    def __init__(self) -> None:
        self.execute_count = 0
        self.replay_count = 0
        self.by_key: dict[str, PaperPositionSellResult] = {}

    async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
        key = str(kwargs.get("idempotency_key") or "")
        if key in self.by_key:
            self.replay_count += 1
            return self.by_key[key]
        self.execute_count += 1
        qty = float(kwargs.get("quantity") or 0)
        result = PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=qty,
            fill_price=float(kwargs.get("price") or 0),
            transaction_id=f"tx-v175-{self.execute_count}",
        )
        self.by_key[key] = result
        return result


def _cycle(store: _DeskStore, sell: _IdempotentSell) -> PaperDeskCycle:
    auto = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=sell,
    )
    return PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        execute_auto=auto,
    )


@pytest.mark.asyncio
async def test_gp_v175_05_stale_dry_run_no_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-V175-05: dryRun + STALE → held/data_stale · 0 sells."""
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    store = _DeskStore(_open_row())
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-v175",
            dry_run=True,
            context=build_test_operational_context(
                marks={"MSFT": 110.0}, permission="STALE"
            ),
        )
    )
    row = result.positions[0]
    assert row.status == "held"
    assert row.reason == "data_stale"
    assert sell.execute_count == 0
    assert result.dry_run is True


def test_gp_v175_06_entry_stale_data_maps_reason_code() -> None:
    """GP-V175-06: gate freshness/stale → ENTRY_STALE_DATA + humanMessage."""
    tick = map_estudio_propose_to_entry_tick(
        {
            "hitCount": 1,
            "hits": [
                {
                    "instrumentId": "MSFT",
                    "symbol": "MSFT",
                    "signal": {"id": "dec-stale-1", "instrumentId": "MSFT"},
                    "tradePlan": {
                        "status": "TRIGGERED",
                        "quantity": 5,
                        "entry": 100,
                        "structuralStop": 95,
                        "executionAllowed": True,
                    },
                }
            ],
            "skipped": [],
            "executeStatus": "executed",
            "execution": {
                "actions": [
                    {
                        "instrumentId": "MSFT",
                        "status": "skipped",
                        "reason": "data_freshness:stale:age_s=9999",
                    }
                ]
            },
            "notes": [],
            "generatedAt": "2026-09-02T12:00:00Z",
        },
        dry_run=False,
        template_id="moderate",
    )
    assert tick.candidates
    cand = tick.candidates[0]
    assert cand.reason_code == "ENTRY_STALE_DATA"
    assert cand.freshness == "stale"
    assert cand.human_message
    assert "stale" in cand.human_message.lower()
    assert tick.executed_count == 0


@pytest.mark.asyncio
async def test_gp_v175_07_adversarial_crash_replay_no_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-V175-07: crash replay smoke — same eventId → no second fill (V1.58 pattern)."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row(qty=10.0))
    sell = _IdempotentSell()
    blob = dict(store.row["position_state"])
    next_blob, event, _created = claim_durable_event(
        blob,
        position_id="pos-MSFT",
        event_type="T1",
        action="reduce",
        as_of="2026-09-02T16:00:00Z",
        quantity=3.0,
    )
    store.row["position_state"] = next_blob
    accepted = await sell.sell(
        account_id="acc-v175",
        instrument_id="MSFT",
        quantity=3.0,
        price=110.0,
        full_exit=False,
        idempotency_key=event.event_id,
    )
    assert accepted.status == "trade_executed"
    assert sell.execute_count == 1

    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-v175",
            as_of="2026-09-02T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 110.0}),
        )
    )
    assert result.positions[0].status in {"reduced", "held", "sell_skipped"}
    assert sell.execute_count == 1
    assert sell.replay_count == 1
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == pytest.approx(7.0)
