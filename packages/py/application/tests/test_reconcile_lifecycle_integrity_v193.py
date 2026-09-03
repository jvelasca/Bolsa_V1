"""V1.93 — unit tests for PositionState ↔ Lifecycle recon (detect/report)."""

from __future__ import annotations

from bolsa_application.reconcile_lifecycle_integrity import (
    OutboxSnap,
    PositionStateSnap,
    build_lifecycle_reconciliation,
)


def test_recon_clean_open() -> None:
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[
            PositionStateSnap(position_id="pos-1", status="OPEN", remaining=10.0)
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [{"kind": "POSITION_OPENED"}],
                "accounting": {"remaining": 10.0},
            }
        },
        outbox=[],
    )
    assert report.status == "clean"
    assert report.checked == 1
    assert report.issues == ()


def test_recon_missing_open_is_drift() -> None:
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[
            PositionStateSnap(position_id="pos-1", status="OPEN", remaining=10.0)
        ],
        snapshots_by_position={"pos-1": {"events": [], "accounting": None}},
        outbox=[],
    )
    assert report.status == "drift"
    assert report.drift_count == 1
    assert report.issues[0].code == "missing_open_event"


def test_recon_close_pending_is_lag() -> None:
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[
            PositionStateSnap(position_id="pos-1", status="CLOSED", remaining=0.0)
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [{"kind": "POSITION_OPENED"}],
                "accounting": {"remaining": 0.0},
            }
        },
        outbox=[
            OutboxSnap(
                position_id="pos-1", kind="POSITION_CLOSED", status="pending"
            )
        ],
    )
    assert report.status == "lag"
    assert report.lag_count == 1


def test_recon_dead_head_is_blocked() -> None:
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[
            PositionStateSnap(position_id="pos-1", status="OPEN", remaining=10.0)
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [{"kind": "POSITION_OPENED"}],
                "accounting": {"remaining": 10.0},
            }
        },
        outbox=[
            OutboxSnap(position_id="pos-1", kind="T1_EXECUTED", status="dead")
        ],
    )
    assert report.status == "blocked"
    assert report.blocked_count == 1


def test_recon_qty_mismatch_is_drift() -> None:
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[
            PositionStateSnap(position_id="pos-1", status="OPEN", remaining=10.0)
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [{"kind": "POSITION_OPENED"}],
                "accounting": {"remaining": 7.0},
            }
        },
        outbox=[],
    )
    assert report.status == "drift"
    assert any(i.code == "qty_mismatch" for i in report.issues)
