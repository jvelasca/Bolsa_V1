"""PortfolioReconciliation OI-6 — detect/report (ADR-034)."""

from bolsa_analytics.cognitive.portfolio_reconciliation import (
    HoldingSnap,
    OpenPositionSnap,
    build_portfolio_reconciliation,
    reconciliation_status_copy,
)


def test_clean_aligned() -> None:
    report = build_portfolio_reconciliation(
        account_id="acc-1",
        portfolio_cash=1000.0,
        ledger_cash_sum=1000.0,
        holdings=[HoldingSnap("inst-1", 10.0)],
        open_positions=[
            OpenPositionSnap("inst-1", 10.0, "tx-1", "OPEN"),
        ],
        known_transaction_ids=["tx-1"],
    )
    assert report.status == "clean"
    assert all(c.outcome != "mismatch" for c in report.checks)
    assert report.to_dict()["status"] == "clean"


def test_cash_mismatch_drift() -> None:
    report = build_portfolio_reconciliation(
        account_id="acc-1",
        portfolio_cash=1000.0,
        ledger_cash_sum=900.0,
        holdings=[],
        open_positions=[],
    )
    assert report.status == "drift"
    cash = next(c for c in report.checks if c.id == "cash_ledger")
    assert cash.outcome == "mismatch"


def test_addon_expected_not_mismatch() -> None:
    report = build_portfolio_reconciliation(
        account_id="acc-1",
        portfolio_cash=1.0,
        ledger_cash_sum=1.0,
        holdings=[HoldingSnap("inst-1", 15.0)],
        open_positions=[
            OpenPositionSnap("inst-1", 10.0, "tx-1", "OPEN"),
        ],
        known_transaction_ids=["tx-1"],
    )
    assert report.status == "clean"
    qty = next(c for c in report.checks if c.id == "holding_qty_vs_position")
    assert qty.outcome == "expected"


def test_holding_without_open_expected() -> None:
    report = build_portfolio_reconciliation(
        account_id="acc-1",
        portfolio_cash=1.0,
        ledger_cash_sum=1.0,
        holdings=[HoldingSnap("legacy", 3.0)],
        open_positions=[],
    )
    assert report.status == "clean"
    legacy = next(c for c in report.checks if c.id == "holding_without_open")
    assert legacy.outcome == "expected"


def test_open_without_holding_mismatch() -> None:
    report = build_portfolio_reconciliation(
        account_id="acc-1",
        portfolio_cash=1.0,
        ledger_cash_sum=1.0,
        holdings=[],
        open_positions=[
            OpenPositionSnap("inst-1", 5.0, "tx-1", "OPEN"),
        ],
        known_transaction_ids=["tx-1"],
    )
    assert report.status == "drift"
    orphan = next(c for c in report.checks if c.id == "open_without_holding")
    assert orphan.outcome == "mismatch"


def test_open_tx_unknown_when_omitted() -> None:
    report = build_portfolio_reconciliation(
        account_id="acc-1",
        portfolio_cash=1.0,
        ledger_cash_sum=1.0,
        holdings=[HoldingSnap("inst-1", 1.0)],
        open_positions=[
            OpenPositionSnap("inst-1", 1.0, "tx-1", "OPEN"),
        ],
        known_transaction_ids=None,
    )
    assert report.status == "clean"
    link = next(c for c in report.checks if c.id == "open_tx_link")
    assert link.outcome == "unknown"


def test_copy_no_heal() -> None:
    assert "auto-heal" in reconciliation_status_copy("drift").lower()
    assert "alineadas" in reconciliation_status_copy("clean").lower()
