"""V1.94 — unit tests for financial integrity compose + fill links + operationalState."""

from __future__ import annotations

import pytest

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


def test_t1_fill_missing_in_ledger() -> None:
    issues = build_fill_link_issues(
        positions=[
            PositionStateSnap(
                position_id="pos-1",
                status="OPEN",
                remaining=5.0,
                open_transaction_id="tx-open",
            )
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [
                    {"kind": "POSITION_OPENED", "fillId": "tx-open"},
                    {"kind": "T1_EXECUTED", "fillId": "tx-t1"},
                ],
            }
        },
        ledger_reference_ids={"tx-open"},
    )
    assert any(
        i.code == "missing_fill_in_ledger" and "T1_EXECUTED" in i.detail
        for i in issues
    )


def test_t2_fill_missing_in_ledger() -> None:
    issues = build_fill_link_issues(
        positions=[
            PositionStateSnap(
                position_id="pos-1",
                status="OPEN",
                remaining=2.0,
                open_transaction_id="tx-open",
            )
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [
                    {"kind": "POSITION_OPENED", "fillId": "tx-open"},
                    {"kind": "T1_EXECUTED", "fillId": "tx-t1"},
                    {"kind": "T2_EXECUTED", "fillId": "tx-t2"},
                ],
            }
        },
        ledger_reference_ids={"tx-open", "tx-t1"},
    )
    assert any(
        i.code == "missing_fill_in_ledger" and "T2_EXECUTED" in i.detail
        for i in issues
    )


def test_exit_fill_missing_in_ledger() -> None:
    issues = build_fill_link_issues(
        positions=[
            PositionStateSnap(
                position_id="pos-1",
                status="CLOSED",
                remaining=0.0,
                open_transaction_id="tx-open",
            )
        ],
        snapshots_by_position={
            "pos-1": {
                "events": [
                    {"kind": "POSITION_OPENED", "fillId": "tx-open"},
                    {"kind": "T1_EXECUTED", "fillId": "tx-t1"},
                    {"kind": "POSITION_CLOSED", "fillId": "tx-exit"},
                ],
            }
        },
        ledger_reference_ids={"tx-open", "tx-t1"},
    )
    assert any(
        i.code == "missing_fill_in_ledger" and "POSITION_CLOSED" in i.detail
        for i in issues
    )


def test_compose_dead_non_head_is_degraded_not_clean() -> None:
    from bolsa_application.reconcile_lifecycle_integrity import LifecycleReconIssue

    lc = LifecycleReconciliation(
        account_id="acc-1",
        status="lag",
        checked=1,
        drift_count=0,
        lag_count=0,
        blocked_count=0,
        issues=(
            LifecycleReconIssue(
                code="dead_non_head",
                position_id="pos-1",
                detail="dead not head",
            ),
        ),
    )
    report = compose_financial_integrity(account_id="acc-1", lifecycle=lc)
    assert report.status == "lag"
    assert report.status != "clean"
    assert report.operational_state == "DEGRADED"


def test_compose_fill_t1_drift_vetoes_clean_lifecycle() -> None:
    report = compose_financial_integrity(
        account_id="acc-1",
        lifecycle=_lc(status="clean"),
        fill_link_issues=(
            FillLinkIssue(
                code="missing_fill_in_ledger",
                position_id="pos-1",
                detail="T1_EXECUTED fill/tx tx-t1 missing from ledger references",
            ),
        ),
    )
    assert report.status == "drift"
    assert report.operational_state == "BLOCKED"
    from bolsa_application.reconciliation_opening_gate import (
        reconciliation_opening_veto_reason,
    )

    assert (
        reconciliation_opening_veto_reason(lifecycle_recon_status=report.status)
        == "reconciliation:lifecycle_drift"
    )


def test_unavailable_financial_integrity_is_blocked() -> None:
    from bolsa_application.reconcile_financial_integrity import (
        unavailable_financial_integrity,
    )

    report = unavailable_financial_integrity("acc-x")
    assert report.status == "blocked"
    assert report.operational_state == "BLOCKED"
    d = report.to_dict()
    assert d["accountId"] == "acc-x"
    assert d["status"] == "blocked"
    assert d["operationalState"] == "BLOCKED"
    assert d["lifecycle"]["status"] == "blocked"
    assert d["fillLinkIssues"] == []


@pytest.mark.asyncio
async def test_financial_lookup_none_is_unavailable_named() -> None:
    from bolsa_application.reconciliation_opening_gate import (
        ReconcileFinancialIntegrityLookup,
        reconciliation_opening_veto_reason,
    )

    class _Uc:
        async def reconcile(self, _inp: object) -> None:
            return None

    status = await ReconcileFinancialIntegrityLookup(_Uc()).lifecycle_recon_status(
        "acc-1"
    )
    assert status == "unavailable"
    assert (
        reconciliation_opening_veto_reason(lifecycle_recon_status=status)
        == "reconciliation:lifecycle_unavailable"
    )


@pytest.mark.asyncio
async def test_lifecycle_lookup_none_is_unavailable_named() -> None:
    from bolsa_application.reconciliation_opening_gate import (
        ReconcileLifecycleIntegrityLookup,
        reconciliation_opening_veto_reason,
    )

    class _Uc:
        async def reconcile(self, _inp: object) -> None:
            return None

    status = await ReconcileLifecycleIntegrityLookup(_Uc()).lifecycle_recon_status(
        "acc-1"
    )
    assert status == "unavailable"
    assert (
        reconciliation_opening_veto_reason(lifecycle_recon_status=status)
        == "reconciliation:lifecycle_unavailable"
    )
