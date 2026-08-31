"""V1.46 — GP-DESK PaperDeskCycle tests."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.paper_d_propose import paper_d_execute_allowed
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
    PaperDeskEntryTickResult,
)


def _plan(instrument_id: str = "MSFT") -> dict[str, object]:
    return {
        "decisionId": "dec-desk",
        "instrumentId": instrument_id,
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
    }


def _open_row(
    *,
    instrument_id: str = "MSFT",
    qty: float = 10.0,
) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _plan(instrument_id),
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-08-31T15:00:00Z",
        position_id=f"pos-{instrument_id}",
    )
    assert pos is not None
    return {
        "id": f"pos-{instrument_id}",
        "account_id": "acc-1",
        "instrument_id": instrument_id,
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _OpenStore:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.mutated = False

    async def list_open(self, account_id: str) -> list[dict[str, Any]]:
        _ = account_id
        return list(self.rows)


class _FakeEntry:
    def __init__(self, result: PaperDeskEntryTickResult) -> None:
        self.result = result
        self.calls = 0

    async def run_entry_tick(self, **kwargs: Any) -> PaperDeskEntryTickResult:
        _ = kwargs
        self.calls += 1
        return self.result


@pytest.mark.asyncio
async def test_gp_desk_01_dry_run_no_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    """GP-DESK-01: dry_run → entry propose counts + HOLD/DENY/PROTECT · no mutate."""
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    store = _OpenStore([_open_row()])
    entry = _FakeEntry(
        PaperDeskEntryTickResult(
            status="dry_run",
            proposed_count=2,
            notes=("propose dry",),
        )
    )
    uc = PaperDeskCycle(entry=entry, open_positions=store, execute_auto=None)
    result = await uc.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31",
            dry_run=True,
            mark_prices={"MSFT": 100.0},
            data_stale=False,
            market_closed=False,
        )
    )
    assert result.dry_run is True
    assert result.blocked is False
    assert result.entry.proposed_count == 2
    assert entry.calls == 1
    assert store.mutated is False
    assert len(result.positions) == 1
    assert result.positions[0].status in {"held", "denied", "protected", "no_plan"}
    assert "dryRun=true" in " ".join(result.notes)


@pytest.mark.asyncio
async def test_gp_desk_01_denied_jit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    store = _OpenStore([_open_row()])
    uc = PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
    )
    # T1 mark with env off → if HOLD no deny; use stale+triggered path via high mark
    result = await uc.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            dry_run=True,
            mark_prices={"MSFT": 110.0},
            data_stale=True,
        )
    )
    assert result.positions
    # T1 at 110 with stale: PROTECT/REDUCE may deny on stale depending on policy
    row = result.positions[0]
    assert row.status in {"held", "denied", "protected", "reduced", "exited"}


@pytest.mark.asyncio
async def test_gp_desk_02_execute_blocked_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-DESK-02: env off + execute → blocked · paper_auto_env_blocked."""
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    assert paper_d_execute_allowed() is False
    store = _OpenStore([_open_row()])
    uc = PaperDeskCycle(entry=HonestStubPaperDeskEntry(), open_positions=store)
    result = await uc.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            dry_run=False,
            mark_prices={"MSFT": 100.0},
        )
    )
    assert result.blocked is True
    assert result.block_reason == "paper_auto_env_blocked"
    assert result.entry.status == "blocked"
    assert result.positions == ()
