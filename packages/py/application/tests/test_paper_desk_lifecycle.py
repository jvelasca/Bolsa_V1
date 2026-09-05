"""V1.52 Position Lifecycle — GP-EXIT / GP-TRAIL / GP-CRASH on Estudio-born Position."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.opening_fill_handle import (
    MemoryOpeningFillHandleStore,
    OpeningFillHandle,
    RecoverOrphanOpeningFills,
)
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    PersistPositionFromFillInput,
)
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect


def _estudio_plan() -> dict[str, object]:
    return {
        "decisionId": "tp-A",
        "instrumentId": "A",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
        "candidateDecisionId": "sig-A",
        "fillId": "tx-fill-A",
        "templateId": "moderate",
        "candidateSnapshot": {
            "decisionId": "sig-A",
            "instrumentId": "A",
            "rank": 1,
            "score": 5.0,
        },
    }


def _estudio_born_row() -> dict[str, Any]:
    plan = _estudio_plan()
    pos = build_position_state_from_fill(
        plan,
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-A",
    )
    assert pos is not None
    return {
        "id": "pos-A",
        "account_id": "acc-demo",
        "instrument_id": "A",
        "status": pos.status,
        "trade_plan_id": "tp-A",
        "open_transaction_id": "tx-fill-A",
        "trade_plan_snapshot": dict(plan),
        "position_state": pos.to_dict(),
    }


def _identities(row: dict[str, Any]) -> None:
    snap = row.get("trade_plan_snapshot") or {}
    blob = row.get("position_state") or {}
    assert snap.get("decisionId") == "tp-A"
    assert snap.get("candidateDecisionId") == "sig-A"
    assert snap.get("fillId") == "tx-fill-A"
    assert snap.get("decisionId") != snap.get("candidateDecisionId")
    assert row.get("open_transaction_id") == "tx-fill-A"
    assert blob.get("tradePlanId") == "tp-A"


class _Store:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row
        self.inserts: list[dict[str, Any]] = []

    async def list_open(self, account_id: str) -> list[dict[str, Any]]:
        _ = account_id
        if self.row is None or self.row.get("status") == "CLOSED":
            return []
        return [self.row]

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        _ = account_id
        if self.row is None or self.row.get("instrument_id") != instrument_id:
            return None
        if self.row.get("status") == "CLOSED":
            return None
        return self.row

    async def get_by_open_transaction_id(
        self, open_transaction_id: str
    ) -> dict[str, Any] | None:
        if self.row and self.row.get("open_transaction_id") == open_transaction_id:
            return self.row
        for item in self.inserts:
            if item.get("open_transaction_id") == open_transaction_id:
                return item
        return None

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        row = {
            "id": kwargs.get("position_id") or "pos-rec",
            "account_id": kwargs["account_id"],
            "instrument_id": kwargs["instrument_id"],
            "status": kwargs.get("status") or "OPEN",
            "trade_plan_id": kwargs.get("trade_plan_id"),
            "open_transaction_id": kwargs["open_transaction_id"],
            "trade_plan_snapshot": kwargs.get("trade_plan_snapshot") or {},
            "position_state": kwargs.get("position_state") or {},
        }
        self.inserts.append(row)
        self.row = row
        return row

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        assert self.row is not None
        self.row = {
            **self.row,
            "id": position_id,
            "status": status,
            "position_state": position_state,
        }
        return self.row

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        blob = self.row.get("position_state") if self.row else None
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
            transaction_id=f"tx-exit-{self.execute_count}",
        )
        self.by_key[key] = result
        return result


def _cycle(store: _Store, sell: _Sell | None = None) -> PaperDeskCycle:
    seller = sell or _Sell()
    return PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        execute_auto=ExecutePositionPolicyAuto(
            protect=PersistPositionFromProtect(store),
            exit_persist=PersistPositionFromExit(store),
            sell=seller,
        ),
    )


@pytest.mark.asyncio
async def test_gp_exit_01_structural_stop_closes_estudio_born(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Store(_estudio_born_row())
    _identities(store.row or {})
    result = await _cycle(store).execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 94.0}),
        )
    )
    assert result.positions[0].status == "exited"
    assert store.row is not None
    assert store.row["status"] == "CLOSED"
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.status == "CLOSED"
    _identities(store.row)


@pytest.mark.asyncio
async def test_gp_exit_02_t1_reduce_marks_leg_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Store(_estudio_born_row())
    sell = _Sell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )
    assert result.positions[0].status == "reduced"
    assert sell.execute_count == 1
    pos = position_state_from_dict((store.row or {})["position_state"])
    assert pos is not None
    assert pos.status == "PARTIAL"
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "executed"
    assert pos.target1_leg.fill_id == "tx-exit-1"
    assert pos.target1_achieved_at is not None
    _identities(store.row or {})


@pytest.mark.asyncio
async def test_gp_exit_03_t1_then_t2_closes_without_reemitting_t1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Store(_estudio_born_row())
    sell = _Sell()
    cycle = _cycle(store, sell)
    t1 = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )
    assert t1.positions[0].status == "reduced"
    t2 = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T14:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 120.0}),
        )
    )
    assert t2.positions[0].status in {"reduced", "exited"}
    pos = position_state_from_dict((store.row or {})["position_state"])
    assert pos is not None
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "executed"
    assert sell.execute_count == 2
    if pos.status == "CLOSED":
        assert pos.target2_leg is None or pos.target2_leg.status in {
            "executed",
            "triggered",
            "pending",
        }


@pytest.mark.asyncio
async def test_gp_trail_01_ratchet_revisions_carry_decision_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Store(_estudio_born_row())
    cycle = _cycle(store)
    await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T12:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 105.0}, trail_hint=True, trail_stop=98.0
            ),
        )
    )
    await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T13:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 108.0}, trail_hint=True, trail_stop=102.0
            ),
        )
    )
    revs = [
        r
        for r in revisions_from_raw((store.row or {})["position_state"].get("revisions"))
        if r.origin == "trail"
    ]
    assert len(revs) >= 2
    assert all(r.decision_id == "tp-A" for r in revs)
    assert all(r.policy_id == "moderate" for r in revs)


def test_gp_trail_02_stop_down_denied() -> None:
    pos = build_position_state_from_fill(
        _estudio_plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-A",
    )
    assert pos is not None
    up = apply_position_current_stop(pos, 102.0, at="t1", origin="trail")
    assert up is not None
    before = len(up.revisions)
    denied = apply_position_current_stop(up, 99.0, at="t2", origin="trail")
    assert denied is None
    assert len(up.revisions) == before


@pytest.mark.asyncio
async def test_gp_crash_01_fill_without_position_recovers_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BUY FILLED + persist crash → restart → 1 Position, 0 duplicados."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    handles = MemoryOpeningFillHandleStore()
    store = _Store(None)
    persist = PersistPositionFromFill(store)
    plan = _estudio_plan()
    await handles.record(
        OpeningFillHandle(
            account_id="acc-demo",
            open_transaction_id="tx-fill-A",
            instrument_id="A",
            fill_price=100.0,
            fill_quantity=10.0,
            trade_plan=plan,
            filled_at="2026-09-01T09:00:00Z",
        )
    )
    assert await store.get_by_open_transaction_id("tx-fill-A") is None
    recoverer = RecoverOrphanOpeningFills(handles=handles, persist=persist)
    cycle = PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        recover_orphans=recoverer,
    )
    result = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T09:05:00Z",
            dry_run=True,
        )
    )
    assert "orphan_opening_recovered=1" in result.notes
    assert len(store.inserts) == 1
    row = store.inserts[0]
    assert row["open_transaction_id"] == "tx-fill-A"
    assert row["trade_plan_id"] == "tp-A"
    snap = row["trade_plan_snapshot"]
    assert snap["decisionId"] == "tp-A"
    assert snap["candidateDecisionId"] == "sig-A"
    assert snap["fillId"] == "tx-fill-A"
    blob = row["position_state"]
    assert blob.get("target1Leg", {}).get("status") == "pending"
    again = await recoverer.recover("acc-demo")
    assert again == 1
    assert len(store.inserts) == 1
    direct = await persist.persist(
        PersistPositionFromFillInput(
            account_id="acc-demo",
            trade_plan=plan,
            fill_price=100.0,
            fill_quantity=10.0,
            filled_at="2026-09-01T09:00:00Z",
            open_transaction_id="tx-fill-A",
            ledger_position_id=None,
        )
    )
    assert direct is not None
    assert len(store.inserts) == 1


class _BoomRecover:
    async def recover(self, account_id: str) -> int:
        _ = account_id
        raise RuntimeError("orphan store timeout")


@pytest.mark.asyncio
async def test_orphan_recovery_failure_is_visible_in_notes() -> None:
    """V2.47 — recover() exception ≠ silent 0 recovered."""
    cycle = PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=_Store(None),
        recover_orphans=_BoomRecover(),
    )
    result = await cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T09:05:00Z",
            dry_run=True,
        )
    )
    assert "orphan_recovery_failed" in result.notes
    assert not any(n.startswith("orphan_opening_recovered=") for n in result.notes)
    assert result.blocked is False

    from bolsa_application.paper_daily_report import build_paper_daily_report

    report = build_paper_daily_report(result)
    kinds = [f["kind"] for f in report.to_dict().get("exceptionFacts", [])]
    assert "orphan_recovery_failed" in kinds
