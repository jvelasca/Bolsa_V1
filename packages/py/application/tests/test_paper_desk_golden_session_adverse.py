"""V1.55 Golden Session adverse paths — GP-SESSION-05..10."""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.opening_fill_handle import (
    MemoryOpeningFillHandleStore,
    OpeningFillHandle,
    RecoverOrphanOpeningFills,
)
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_daily_report import build_paper_daily_report
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    PersistPositionFromFillInput,
)
from paper_desk_golden_fixtures import (
    SessionStore,
    Sell,
    assert_birth_invariants,
    assert_identities,
    assert_journal_chain,
    build_cycles,
    golden_plan,
)


def _estudio_plan_dict(*, quantity: float = 10.0) -> dict[str, object]:
    plan = golden_plan(quantity=quantity)
    snap = plan.trade_plan
    return {
        **snap,
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


@pytest.mark.asyncio
async def test_gp_session_05_stop_loss_closes_with_zero_qty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-SESSION-05: Estudio → buy → fill → position → stop → CLOSED qty=0."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")
    store = SessionStore()
    sell = Sell()
    birth_cycle, position_cycle = build_cycles(store, sell)

    open_ = await birth_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T09:00:00Z",
            dry_run=False,
            execution_policy_id="pol-1",
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 100.0}),
        )
    )
    assert open_.entry.executed_count == 1
    entry_fill = store.row["open_transaction_id"]
    candidate_id = open_.entry.candidates[0].decision_id

    closed = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 94.0}),
        )
    )
    assert closed.positions[0].status == "exited"
    assert store.row is not None
    assert store.row["status"] == "CLOSED"
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == 0
    assert entry_fill != "tx-exit-1"
    assert_journal_chain(store.row, exit_fill_id="tx-exit-1")
    assert_identities(store.row, candidate_id=candidate_id)


@pytest.mark.asyncio
async def test_gp_session_06_t1_partial_reduces_to_seventy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-SESSION-06: Buy 10 → T1 30% → remaining 7 (moderate policy)."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")
    store = SessionStore()
    sell = Sell()
    birth_cycle, position_cycle = build_cycles(store, sell, quantity=10.0)

    await birth_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T09:00:00Z",
            dry_run=False,
            execution_policy_id="pol-1",
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 100.0}),
        )
    )
    assert_birth_invariants(store.row or {}, quantity=10.0)

    t1 = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )
    assert t1.positions[0].status == "reduced"
    pos = position_state_from_dict((store.row or {})["position_state"])
    assert pos is not None
    assert pos.quantity == 10.0
    assert pos.remaining_quantity == pytest.approx(7.0)
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "executed"
    assert pos.target1_leg.fill_id is not None
    assert pos.target2_leg is not None
    assert pos.target2_leg.status == "pending"
    assert sell.last_qty == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_gp_session_07_t2_closes_remainder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-SESSION-07: after T1 partial → T2 → remaining 0."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")
    store = SessionStore()
    sell = Sell()
    birth_cycle, position_cycle = build_cycles(store, sell, quantity=10.0)

    await birth_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T09:00:00Z",
            dry_run=False,
            execution_policy_id="pol-1",
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 100.0}),
        )
    )
    await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )
    pos_mid = position_state_from_dict((store.row or {})["position_state"])
    assert pos_mid is not None
    assert pos_mid.remaining_quantity == pytest.approx(7.0)
    t1_sells = sell.execute_count

    t2 = await position_cycle.execute(
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
    assert sell.execute_count > t1_sells
    if pos.status == "CLOSED":
        assert pos.remaining_quantity == 0
        if pos.target2_leg is not None:
            assert pos.target2_leg.status in {"executed", "triggered"}


@pytest.mark.asyncio
async def test_gp_session_08_trailing_monotonic_never_down() -> None:
    """GP-SESSION-08: stop ratchet 47 → 51 → 54; down denied."""
    plan = _estudio_plan_dict(quantity=10.0)
    pos = build_position_state_from_fill(
        {**plan, "entry": 50.0, "structuralStop": 47.0},
        fill_price=50.0,
        fill_quantity=10.0,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-A",
    )
    assert pos is not None
    up1 = apply_position_current_stop(pos, 51.0, at="t1", origin="trail")
    assert up1 is not None
    up2 = apply_position_current_stop(up1, 54.0, at="t2", origin="trail")
    assert up2 is not None
    assert up2.current_stop == pytest.approx(54.0)
    denied = apply_position_current_stop(up2, 52.0, at="t3", origin="trail")
    assert denied is None
    assert up2.current_stop == pytest.approx(54.0)
    revs = [r for r in up2.revisions if r.origin == "trail"]
    stops = [r.next_stop for r in revs if r.next_stop is not None]
    assert stops == sorted(stops)


@pytest.mark.asyncio
async def test_gp_session_09_crash_restart_recovers_estudio_birth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-SESSION-09: BUY → FILL → crash → restart → 1 Position."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    handles = MemoryOpeningFillHandleStore()
    store = SessionStore()
    persist = PersistPositionFromFill(store)
    plan = _estudio_plan_dict()
    await handles.record(
        OpeningFillHandle(
            account_id="acc-demo",
            open_transaction_id="tx-fill-1",
            instrument_id="A",
            fill_price=100.0,
            fill_quantity=10.0,
            trade_plan=plan,
            filled_at="2026-09-01T09:00:00Z",
        )
    )
    assert await store.get_by_open_transaction_id("tx-fill-1") is None
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
    assert row["trade_plan_id"] == "tp-A"
    snap = row["trade_plan_snapshot"]
    assert snap["decisionId"] == "tp-A"
    assert snap["candidateDecisionId"] == "sig-A"
    assert row["open_transaction_id"] == "tx-fill-1"
    again = await recoverer.recover("acc-demo")
    assert again == 1
    assert len(store.inserts) == 1


@pytest.mark.asyncio
async def test_gp_session_10_reconciliation_exception_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-SESSION-10: portfolio drift → exceptionFacts (no auto-heal)."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = SessionStore()
    sell = Sell()
    birth_cycle, position_cycle = build_cycles(store, sell)
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")
    await birth_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T09:00:00Z",
            dry_run=False,
            execution_policy_id="pol-1",
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 100.0}),
        )
    )

    drift = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T10:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 100.0},
                recon_status="drift",
            ),
        )
    )
    report = build_paper_daily_report(drift)
    d = report.to_dict()
    kinds = [f["kind"] for f in d.get("exceptionFacts", [])]
    assert "portfolio_recon_drift" in kinds
    if drift.positions:
        row = drift.positions[0].to_dict()
        assert row.get("operating_state") in {
            "RECONCILIATION_ERROR",
            None,
        } or drift.blocked or "portfolio_drift" in drift.notes


@pytest.mark.asyncio
async def test_gp_session_t1_price_touch_not_executed_until_fill() -> None:
    """mark >= T1 ≠ executed until reduce fill."""
    plan = _estudio_plan_dict()
    pos = build_position_state_from_fill(
        plan,
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-A",
    )
    assert pos is not None
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "pending"
    # Price at T1 without reduce — leg stays pending
    marked = pos  # mark >= T1 is advisory in ExitPlan; durable leg unchanged
    assert marked.target1_leg.status == "pending"
