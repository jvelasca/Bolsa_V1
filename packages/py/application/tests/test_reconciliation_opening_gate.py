"""OR-4 — reconciliation_opening_veto_reason unit tests."""

from __future__ import annotations

from bolsa_application.reconciliation_opening_gate import (
    reconciliation_opening_veto_reason,
)


def test_gate_off_without_require_or_status() -> None:
    assert reconciliation_opening_veto_reason() is None


def test_portfolio_drift_denies() -> None:
    assert (
        reconciliation_opening_veto_reason(portfolio_recon_status="drift")
        == "reconciliation:portfolio_drift"
    )


def test_portfolio_unavailable_denies() -> None:
    assert (
        reconciliation_opening_veto_reason(portfolio_recon_status="unavailable")
        == "reconciliation:portfolio_unavailable"
    )


def test_portfolio_clean_allows() -> None:
    assert (
        reconciliation_opening_veto_reason(
            portfolio_recon_status="clean",
            require=True,
        )
        is None
    )


def test_live_unavailable_denies_only_on_live_venue() -> None:
    assert (
        reconciliation_opening_veto_reason(
            live_recon_status="unavailable",
            broker_venue="live",
            require=True,
        )
        == "reconciliation:live_unavailable"
    )
    assert (
        reconciliation_opening_veto_reason(
            live_recon_status="unavailable",
            broker_venue="paper",
            require=True,
        )
        is None
    )


def test_live_drift_denies_on_live() -> None:
    assert (
        reconciliation_opening_veto_reason(
            live_recon_status="drift",
            broker_venue="live",
        )
        == "reconciliation:live_drift"
    )


def test_live_require_without_status_fail_closed() -> None:
    assert (
        reconciliation_opening_veto_reason(
            broker_venue="live",
            require=True,
        )
        == "reconciliation:live_unavailable"
    )


def test_lifecycle_drift_denies() -> None:
    assert (
        reconciliation_opening_veto_reason(lifecycle_recon_status="drift")
        == "reconciliation:lifecycle_drift"
    )


def test_lifecycle_blocked_denies() -> None:
    assert (
        reconciliation_opening_veto_reason(lifecycle_recon_status="blocked")
        == "reconciliation:lifecycle_blocked"
    )


def test_lifecycle_lag_denies() -> None:
    assert (
        reconciliation_opening_veto_reason(
            lifecycle_recon_status="lag",
            require=True,
        )
        == "reconciliation:lifecycle_lag"
    )


def test_lifecycle_unavailable_denies() -> None:
    assert (
        reconciliation_opening_veto_reason(lifecycle_recon_status="unavailable")
        == "reconciliation:lifecycle_unavailable"
    )
