"""Unit tests CORE-R server tick (no DB)."""

from datetime import UTC, datetime, timedelta

from bolsa_application.core_r_server_tick import (
    apply_server_tick,
    core_r_needs_action,
    enqueue_from_report,
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
