"""Unit tests CORE-R server tick (no DB)."""

from datetime import UTC, datetime, timedelta

from bolsa_application.core_r_server_tick import (
    account_return_pct,
    apply_server_tick,
    build_paper_pnl_review_row,
    core_r_needs_action,
    enqueue_from_report,
    find_paper_for_top_slots,
    paper_pnl_degradation,
    scheduler_due,
)


def test_needs_action() -> None:
    assert core_r_needs_action("review_lab")
    assert core_r_needs_action("consider_replace")
    assert not core_r_needs_action("keep")
    assert not core_r_needs_action("fresh_ok")


def test_scheduler_due() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
    assert scheduler_due(
        {"enabled": True, "listId": "ibex35", "intervalMinutes": 60, "lastTickAt": None},
        now=now,
    )
    recent = (now - timedelta(minutes=10)).isoformat()
    assert not scheduler_due(
        {
            "enabled": True,
            "listId": "ibex35",
            "intervalMinutes": 60,
            "lastTickAt": recent,
        },
        now=now,
    )
    old = (now - timedelta(hours=2)).isoformat()
    assert scheduler_due(
        {"enabled": True, "listId": "ibex35", "intervalMinutes": 60, "lastTickAt": old},
        now=now,
    )


def test_account_return_and_degradation() -> None:
    assert account_return_pct(10_000, 9_500) == -5.0
    assert account_return_pct(0, 100) is None
    assert paper_pnl_degradation(-5)["level"] == "review_lab"
    assert paper_pnl_degradation(-10)["level"] == "consider_replace"
    assert paper_pnl_degradation(-4.9) is None


def test_find_paper_prefers_simulated() -> None:
    accounts = [
        {
            "id": "paper1",
            "type": "paper",
            "status": "active",
            "strategyDefinitionId": "strat-a",
        },
        {
            "id": "demo1",
            "type": "simulated",
            "status": "active",
            "strategyDefinitionId": "strat-a",
        },
    ]
    assert find_paper_for_top_slots(accounts, ["strat-a"])["id"] == "demo1"
    assert find_paper_for_top_slots(accounts, ["missing"]) is None


def test_build_paper_pnl_review_row() -> None:
    row = build_paper_pnl_review_row(
        instrument_id="i1",
        symbol="ACS",
        timeframe="1d",
        return_pct=-6.2,
        slot1_run_id="run-1",
    )
    assert row is not None
    assert row["verdict"] == "review_lab"
    assert any(a["id"] == "lab" for a in row["actions"])
    assert build_paper_pnl_review_row(
        instrument_id="i1",
        symbol="ACS",
        timeframe="1d",
        return_pct=-1.0,
    ) is None


def test_enqueue_merges_extra_rows() -> None:
    report = {
        "engine": "core-r-v0",
        "listId": "ibex35",
        "timeframe": "1d",
        "rows": [
            {
                "instrumentId": "i1",
                "symbol": "ACS",
                "verdict": "review_lab",
                "reason": "x",
                "actions": [],
            },
        ],
    }
    extras = [
        {
            "instrumentId": "i2",
            "symbol": "TEF",
            "verdict": "consider_replace",
            "reason": "pnl",
            "actions": [],
        },
        {
            "instrumentId": "i1",
            "symbol": "ACS",
            "verdict": "consider_replace",
            "reason": "pnl-dup",
            "actions": [],
        },
    ]
    q1, added = enqueue_from_report([], list_id="ibex35", report=report, extra_rows=extras)
    assert added == 2
    symbols = {item["symbol"] for item in q1 if item["status"] == "open"}
    assert symbols == {"ACS", "TEF"}


def test_enqueue_dedupes_open() -> None:
    report = {
        "engine": "core-r-v0",
        "listId": "ibex35",
        "timeframe": "1d",
        "rows": [
            {
                "instrumentId": "i1",
                "symbol": "ACS",
                "verdict": "review_lab",
                "reason": "x",
                "actions": [],
            },
            {
                "instrumentId": "i2",
                "symbol": "TEF",
                "verdict": "keep",
                "reason": "ok",
                "actions": [],
            },
        ],
    }
    q1, added = enqueue_from_report([], list_id="ibex35", report=report)
    assert added == 1
    assert q1[0]["symbol"] == "ACS"
    q2, added2 = enqueue_from_report(q1, list_id="ibex35", report=report)
    assert added2 == 0
    assert len(q2) == 1


def test_apply_server_tick_with_pnl_extras() -> None:
    state = {
        "queue": [],
        "reports": {"ibex35": {"listId": "ibex35", "rows": []}},
        "scheduler": {
            "enabled": True,
            "listId": "ibex35",
            "intervalMinutes": 60,
            "lastTickAt": None,
            "scope": "shell",
        },
    }
    extras = [
        {
            "instrumentId": "i9",
            "symbol": "IBE",
            "verdict": "review_lab",
            "reason": "Demo/paper PnL -5.0%",
            "actions": [],
        }
    ]
    new_state, meta = apply_server_tick(state, force=True, extra_rows=extras)
    assert meta["skipped"] is False
    assert meta["added"] == 1
    assert new_state["queue"][0]["symbol"] == "IBE"
    assert new_state["scheduler"]["lastTickSource"] == "server_cron"


def test_apply_server_tick_marks_last() -> None:
    state = {
        "queue": [],
        "reports": {
            "ibex35": {
                "listId": "ibex35",
                "rows": [
                    {
                        "instrumentId": "i1",
                        "symbol": "ACS",
                        "verdict": "consider_replace",
                        "reason": "pnl",
                        "actions": [],
                    }
                ],
            }
        },
        "scheduler": {
            "enabled": True,
            "listId": "ibex35",
            "intervalMinutes": 60,
            "lastTickAt": None,
            "scope": "shell",
        },
    }
    new_state, meta = apply_server_tick(state, force=True)
    assert meta["skipped"] is False
    assert meta["added"] == 1
    assert new_state["scheduler"]["lastTickSource"] == "server_cron"
    assert new_state["scheduler"]["lastTickAt"]
