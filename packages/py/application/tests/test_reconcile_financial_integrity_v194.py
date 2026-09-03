"""V1.94 — unit tests for financial integrity compose + fill links + operationalState."""

from __future__ import annotations

from bolsa_application.reconcile_financial_integrity import (
    FillLinkIssue,
    build_fill_link_issues,
    compose_financial_integrity,
    compute_operational_state,
)
from bolsa_application.reconcile_lifecycle_integrity import (
    LifecycleReconciliation,
    PositionStateSnap,
)


def _lc(
    *,
    status: str = "clean",
    drift: int = 0,
    lag: int = 0,
    blocked: int = 0,
) -> LifecycleReconciliation:
    return LifecycleReconciliation(
        account_id="acc-1",
        status=status,  # type: ignore[arg-type]
        checked=1,
        drift_count=drift,
        lag_count=lag,
        blocked_count=blocked,
        issues=(),
    )


def test_operational_state_sla_ok_with_dead_is_degraded() -> None:
    assert (
        compute_operational_state(integrity_status="clean", outbox_dead=1) == "DEGRADED"
    )
    assert (
        compute_operational_state(integrity_status="clean", sla_breached=True)
        == "DEGRADED"
    )
    assert compute_operational_state(integrity_status="clean") == "OK"
    assert compute_operational_state(integrity_status="drift") == "BLOCKED"
    assert compute_operational_state(integrity_status="blocked") == "BLOCKED"
    assert compute_operational_state(integrity_status="lag") == "DEGRADED"


def test_compose_fill_drift_overrides_clean_lifecycle() -> None:
    report = compose_financial_integrity(
        account_id="acc-1",
        lifecycle=_lc(status="clean"),
        fill_link_issues=(
            FillLinkIssue(
                code="open_tx_mismatch",
                position_id="pos-1",
                detail="mismatch",
            ),
        ),
    )
    assert report.status == "drift"
    assert report.operational_state == "BLOCKED"


def test_compose_portfolio_drift() -> None:
    report = compose_financial_integrity(
        account_id="acc-1",
        lifecycle=_lc(status="clean"),
        portfolio_status="drift",
    )
    assert report.status == "drift"


def test_open_tx_mismatch() -> None:
    issues = build_fill_link_issues(
        positions=[
            PositionStateSnap(
                position_id="pos-1",
                status="OPEN",
                remaining=10.0,
                open_transaction_id="tx-a",
            )
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [
                    {"kind": "POSITION_OPENED", "fillId": "tx-b"},
                ],
            }
        },
        ledger_reference_ids={"tx-a", "tx-b"},
    )
    assert len(issues) == 1
    assert issues[0].code == "open_tx_mismatch"


def test_missing_fill_in_ledger() -> None:
    issues = build_fill_link_issues(
        positions=[
            PositionStateSnap(
                position_id="pos-1",
                status="OPEN",
                remaining=10.0,
                open_transaction_id="tx-a",
            )
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [
                    {"kind": "POSITION_OPENED", "fillId": "tx-a"},
                ],
            }
        },
        ledger_reference_ids=set(),
    )
    assert any(i.code == "missing_fill_in_ledger" for i in issues)
