"""V1.55 GP-GOLDEN-DAY-01 — full PAPER day EXPECTED=ACTUAL."""

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

from bolsa_analytics.cognitive.position_state import position_state_from_dict
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_daily_report import build_paper_daily_report
from bolsa_application.paper_desk_cycle import PaperDeskCycleInput


@pytest.mark.asyncio
async def test_gp_golden_day_01_full_operating_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """09:00 Estudio → protect → trail → T1 → trail → exit → report."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")

    store = SessionStore()
    sell = Sell()
    birth_cycle, position_cycle = build_cycles(store, sell)

    # 09:00 — entry
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
    expected = {
        "entry_executed": 1,
        "entry_proposed": 1,
        "quantity": 10.0,
        "entry_price": 100.0,
        "decision_id": "tp-A",
    }
    assert open_.entry.executed_count == expected["entry_executed"]
    assert open_.entry.proposed_count == expected["entry_proposed"]
    assert store.row is not None
    candidate_id = open_.entry.candidates[0].decision_id
    assert_identities(store.row, candidate_id=candidate_id)
    assert_birth_invariants(store.row)
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.quantity == expected["quantity"]
    assert pos.actual_entry == expected["entry_price"]
    assert pos.trade_plan_id == expected["decision_id"]

    # 10:00 — protect
    await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T10:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 105.0}, trail_hint=True, trail_stop=98.0
            ),
        )
    )

    # 11:00 — T1
    t1_result = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )

    # 12:00–13:00 — trail
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

    # 16:00 — exit
    closed = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 94.0}),
        )
    )

    pos = position_state_from_dict((store.row or {})["position_state"])
    assert pos is not None
    assert pos.status == "CLOSED"
    assert pos.remaining_quantity == 0
    assert_journal_chain(store.row or {}, exit_fill_id="tx-exit-2")

    report = build_paper_daily_report(closed)
    actual = {
        "position_exited": report.position_exited,
        "position_protected": report.position_protected,
        "position_reduced": report.position_reduced,
        "sell_count": sell.execute_count,
    }
    assert open_.entry.executed_count == expected["entry_executed"]
    assert open_.entry.proposed_count == expected["entry_proposed"]
    assert actual["position_exited"] == 1
    assert actual["sell_count"] == 2
    assert t1_result.positions[0].status == "reduced"

    sections = report.to_dict().get("sections")
    assert sections is not None
    assert sections.get("operativa", {}).get("exits") == 1
