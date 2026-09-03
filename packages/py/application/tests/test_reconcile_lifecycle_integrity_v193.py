"""V1.93/V1.94 — unit tests for PositionState ↔ Lifecycle recon (detect/report)."""

from __future__ import annotations

from datetime import UTC, datetime

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


def test_recon_orphan_lifecycle_is_drift() -> None:
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[],
        snapshots_by_position={
            "orphan-1": {
                "events": [
                    {"kind": "POSITION_OPENED"},
                    {"kind": "POSITION_CLOSED"},
                ],
                "accounting": {"remaining": 0.0},
            }
        },
        outbox=[],
    )
    assert report.status == "drift"
    assert any(i.code == "orphan_lifecycle" for i in report.issues)


def test_recon_orphan_with_pending_outbox_is_lag() -> None:
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[],
        snapshots_by_position={},
        outbox=[
            OutboxSnap(
                position_id="pending-pos",
                kind="POSITION_OPENED",
                status="pending",
            )
        ],
    )
    assert report.status == "lag"
    assert any(i.code == "lifecycle_lag" for i in report.issues)


def test_recon_dead_non_head_not_clean() -> None:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    t1 = datetime(2026, 9, 2, tzinfo=UTC)
    t2 = datetime(2026, 9, 3, tzinfo=UTC)
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[
            PositionStateSnap(position_id="pos-1", status="OPEN", remaining=5.0)
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [
                    {"kind": "POSITION_OPENED"},
                    {"kind": "T1_EXECUTED"},
                ],
                "accounting": {"remaining": 5.0},
            }
        },
        outbox=[
            OutboxSnap(
                position_id="pos-1",
                kind="POSITION_OPENED",
                status="pending",
                created_at=t0,
                id="ox-1",
            ),
            OutboxSnap(
                position_id="pos-1",
                kind="T1_EXECUTED",
                status="dead",
                created_at=t1,
                id="ox-2",
            ),
            OutboxSnap(
                position_id="pos-1",
                kind="POSITION_CLOSED",
                status="pending",
                created_at=t2,
                id="ox-3",
            ),
        ],
    )
    # FIFO head is pending → not dead_head / not blocked; still never clean (V1.95).
    assert report.status != "blocked"
    assert report.status != "clean"
    assert report.blocked_count == 0
    assert any(i.code == "dead_non_head" for i in report.issues)


def test_recon_exit_dead_as_head_is_blocked() -> None:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    report = build_lifecycle_reconciliation(
        account_id="acc-1",
        positions=[
            PositionStateSnap(position_id="pos-1", status="OPEN", remaining=10.0)
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [
                    {"kind": "POSITION_OPENED"},
                    {"kind": "T1_EXECUTED"},
                ],
                "accounting": {"remaining": 10.0},
            }
        },
        outbox=[
            OutboxSnap(
                position_id="pos-1",
                kind="POSITION_CLOSED",
                status="dead",
                created_at=t0,
                id="ox-exit",
            )
        ],
    )
    assert report.status == "blocked"
    assert any(i.code == "dead_head" for i in report.issues)


def test_fifo_outbox_head_none_created_at_with_aware_no_typeerror() -> None:
    """V1.95 P1-B — naive fallback must not TypeError vs TIMESTAMPTZ-aware."""
    from bolsa_application.reconcile_lifecycle_integrity import fifo_outbox_head

    aware = datetime(2026, 9, 2, tzinfo=UTC)
    head = fifo_outbox_head(
        [
            OutboxSnap(
                position_id="pos-1",
                kind="T1_EXECUTED",
                status="dead",
                created_at=aware,
                id="ox-later",
            ),
            OutboxSnap(
                position_id="pos-1",
                kind="POSITION_OPENED",
                status="pending",
                created_at=None,
                id="ox-none",
            ),
        ]
    )
    assert head is not None
    assert head.id == "ox-none"


def test_fifo_outbox_head_naive_promoted_to_utc() -> None:
    from bolsa_application.reconcile_lifecycle_integrity import fifo_outbox_head

    naive = datetime(2026, 9, 1)  # no tz
    aware = datetime(2026, 9, 2, tzinfo=UTC)
    head = fifo_outbox_head(
        [
            OutboxSnap(
                position_id="pos-1",
                kind="T1_EXECUTED",
                status="dead",
                created_at=aware,
                id="ox-later",
            ),
            OutboxSnap(
                position_id="pos-1",
                kind="POSITION_OPENED",
                status="pending",
                created_at=naive,
                id="ox-naive",
            ),
        ]
    )
    assert head is not None
    assert head.id == "ox-naive"


def test_unavailable_lifecycle_reconciliation_is_blocked() -> None:
    from bolsa_application.reconcile_lifecycle_integrity import (
        unavailable_lifecycle_reconciliation,
    )

    report = unavailable_lifecycle_reconciliation("acc-x")
    assert report.status == "blocked"
    d = report.to_dict()
    assert d["accountId"] == "acc-x"
    assert d["status"] == "blocked"
    assert d["issues"] == []
