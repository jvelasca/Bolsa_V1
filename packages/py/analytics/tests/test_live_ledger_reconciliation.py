"""LiveLedgerReconciliation LR-1 — detect/report (ADR-034)."""

from bolsa_analytics.cognitive.live_ledger_reconciliation import (
    LiveHoldingSnap,
    LivePositionSnap,
    build_live_ledger_reconciliation,
    live_ledger_reconciliation_status_copy,
)


def test_clean_aligned() -> None:
    report = build_live_ledger_reconciliation(
        account_id="acc-1",
        ledger_cash=1000.0,
        live_cash=1000.0,
        holdings=[LiveHoldingSnap("inst-1", 10.0)],
        live_positions=[LivePositionSnap("inst-1", 10.0)],
    )
    assert report.status == "clean"
    assert all(c.outcome != "mismatch" for c in report.checks)
    assert report.to_dict()["status"] == "clean"


def test_cash_mismatch_drift() -> None:
    report = build_live_ledger_reconciliation(
        account_id="acc-1",
        ledger_cash=1000.0,
        live_cash=900.0,
        holdings=[],
        live_positions=[],
    )
    assert report.status == "drift"
    cash = next(c for c in report.checks if c.id == "live_cash_vs_ledger")
    assert cash.outcome == "mismatch"


def test_unavailable() -> None:
    report = build_live_ledger_reconciliation(
        account_id="acc-1",
        ledger_cash=1.0,
        live_cash=0.0,
        holdings=[],
        live_positions=[],
        unavailable=True,
    )
    assert report.status == "unavailable"
    assert any(c.outcome == "unknown" for c in report.checks)


def test_holding_without_live_expected() -> None:
    report = build_live_ledger_reconciliation(
        account_id="acc-1",
        ledger_cash=1.0,
        live_cash=1.0,
        holdings=[LiveHoldingSnap("legacy", 3.0)],
        live_positions=[],
    )
    assert report.status == "clean"
    legacy = next(c for c in report.checks if c.id == "holding_without_live")
    assert legacy.outcome == "expected"


def test_live_without_holding_mismatch() -> None:
    report = build_live_ledger_reconciliation(
        account_id="acc-1",
        ledger_cash=1.0,
        live_cash=1.0,
        holdings=[],
        live_positions=[LivePositionSnap("inst-1", 5.0)],
    )
    assert report.status == "drift"
    orphan = next(c for c in report.checks if c.id == "live_without_holding")
    assert orphan.outcome == "mismatch"


def test_qty_mismatch_drift() -> None:
    report = build_live_ledger_reconciliation(
        account_id="acc-1",
        ledger_cash=1.0,
        live_cash=1.0,
        holdings=[LiveHoldingSnap("inst-1", 10.0)],
        live_positions=[LivePositionSnap("inst-1", 7.0)],
    )
    assert report.status == "drift"
    qty = next(c for c in report.checks if c.id == "live_qty_vs_holding")
    assert qty.outcome == "mismatch"


def test_copy_covers_statuses() -> None:
    assert "disponible" in live_ledger_reconciliation_status_copy(
        "unavailable"
    ).lower()
    assert "auto-heal" in live_ledger_reconciliation_status_copy("drift").lower()
    assert "alineados" in live_ledger_reconciliation_status_copy("clean").lower()
