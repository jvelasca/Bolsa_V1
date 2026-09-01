"""V1.53/V1.55 Golden Session — 09:00 Estudio entry → protect → T1 → trail×2 → exit → Journal."""

from __future__ import annotations

import pytest
from paper_desk_golden_fixtures import (
    Sell,
    SessionStore,
    assert_birth_invariants,
    assert_identities,
    assert_journal_chain,
    build_cycles,
)

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import position_state_from_dict
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_daily_report import build_paper_daily_report
from bolsa_application.paper_desk_cycle import PaperDeskCycleInput
from bolsa_application.position_event_log import events_from_blob


@pytest.mark.asyncio
async def test_golden_session_estudio_0900_birth_to_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-SESSION-01..04: Estudio 09:00 → protect → T1 → TRAIL×2 → exit → report."""
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
    assert open_.entry.status == "executed"
    assert len(store.inserts) == 1
    assert store.row is not None
    candidate_id = open_.entry.candidates[0].decision_id
    _assert_identities = assert_identities
    _assert_identities(store.row, candidate_id=candidate_id)
    assert_birth_invariants(store.row)
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "pending"
    entry_fill_id = store.row["open_transaction_id"]

    protect = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T10:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 105.0}, trail_hint=True, trail_stop=98.0
            ),
        )
    )
    assert protect.entry.status == "skipped"
    assert protect.positions[0].status == "protected"
    assert protect.positions[0].executed_action == "APPLIED"
    pos = position_state_from_dict((store.row or {})["position_state"])
    assert pos is not None
    assert pos.current_stop == 98.0

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
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "executed"
    assert pos.target1_leg.fill_id is not None
    assert pos.remaining_quantity < pos.quantity
    assert sell.execute_count == 1

    await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T12:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 112.0}, trail_hint=True, trail_stop=102.0
            ),
        )
    )
    await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T13:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 115.0}, trail_hint=True, trail_stop=108.0
            ),
        )
    )
    events = [
        e for e in events_from_blob((store.row or {})["position_state"]) if e.event_type == "TRAIL"
    ]
    assert len(events) >= 2
    revs = [
        r
        for r in revisions_from_raw((store.row or {})["position_state"].get("revisions"))
        if r.origin == "trail"
    ]
    assert len(revs) >= 2
    assert all(r.decision_id == "tp-A" for r in revs)
    assert all(r.policy_id == "moderate" for r in revs)
    trail_stops = [r.next_stop for r in revs if r.next_stop is not None]
    assert trail_stops == sorted(trail_stops)
    for i in range(1, len(trail_stops)):
        assert trail_stops[i] > trail_stops[i - 1]

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
    assert pos.status == "CLOSED"
    assert pos.remaining_quantity == 0
    _assert_identities(store.row, candidate_id=candidate_id)
    assert_journal_chain(store.row, exit_fill_id="tx-exit-2")
    assert store.row["open_transaction_id"] == entry_fill_id

    report = build_paper_daily_report(closed)
    assert report.position_exited == 1
    assert report.entry_status in {"skipped", "blocked"}
    assert sell.execute_count == 2
    report_dict = report.to_dict()
    assert report_dict["positions"]["exited"] == 1
