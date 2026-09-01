"""V1.48 Golden Session — one PAPER day: protect → T1 → trail×2 → exit."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import (
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_daily_report import build_paper_daily_report
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect
from bolsa_application.position_event_log import events_from_blob


def _plan() -> dict[str, object]:
    return {
        "decisionId": "dec-gold",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
    }


def _open_row() -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-MSFT",
    )
    assert pos is not None
    return {
        "id": "pos-MSFT",
        "account_id": "acc-1",
        "instrument_id": "MSFT",
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _Store:
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
        self.row = {**self.row, "id": position_id, "status": status, "position_state": position_state}
        return self.row

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        blob = self.row.get("position_state")
        current = float(blob.get("currentStop")) if isinstance(blob, dict) else None
        if current is None or abs(current - float(expected_stop)) > 1e-9:
            return None
        return await self.update_state(
            position_id=position_id, status=status, position_state=position_state
        )


class _Sell:
    def __init__(self) -> None:
        self.execute_count = 0
        self.by_key: dict[str, PaperPositionSellResult] = {}

    async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
        key = str(kwargs.get("idempotency_key") or "")
        if key in self.by_key:
            return self.by_key[key]
        self.execute_count += 1
        qty = float(kwargs.get("quantity") or 0)
        result = PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=qty,
            fill_price=float(kwargs.get("price") or 0),
            transaction_id=f"tx-{self.execute_count}",
        )
        self.by_key[key] = result
        return result


@pytest.mark.asyncio
async def test_golden_session_protect_t1_trails_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Store(_open_row())
    sell = _Sell()
    cycle = PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        execute_auto=ExecutePositionPolicyAuto(
            protect=PersistPositionFromProtect(store),
            exit_persist=PersistPositionFromExit(store),
            sell=sell,
        ),
    )

    protect = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T10:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 105.0}, trail_hint=True, trail_stop=98.0
            ),
        )
    )
    assert protect.entry.status == "skipped"
    assert protect.positions[0].status == "protected"
    assert protect.positions[0].executed_action == "APPLIED"
    assert protect.positions[0].next_action == "MONITOR"
    assert protect.positions[0].operating_state in {"PROTECTED", "TRAILING"}

    t1 = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 110.0}),
        )
    )
    assert t1.positions[0].status == "reduced"
    assert t1.positions[0].operating_state == "PARTIALLY_REDUCED"
    assert sell.execute_count == 1

    trail1 = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T12:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 112.0}, trail_hint=True, trail_stop=102.0
            ),
        )
    )
    assert trail1.positions[0].status == "protected"

    trail2 = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T13:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 115.0}, trail_hint=True, trail_stop=108.0
            ),
        )
    )
    assert trail2.positions[0].status == "protected"
    events = [e for e in events_from_blob(store.row["position_state"]) if e.event_type == "TRAIL"]
    assert len(events) >= 2
    revs = [r for r in revisions_from_raw(store.row["position_state"].get("revisions")) if r.origin == "trail"]
    assert len(revs) >= 2

    closed = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 94.0}),
        )
    )
    assert closed.positions[0].status == "exited"
    assert store.row["status"] == "CLOSED"
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.status == "CLOSED"
    report = build_paper_daily_report(closed)
    assert report.position_exited == 1
    assert report.entry_status in {"skipped", "blocked"}
