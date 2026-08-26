"""OE-1 — build_ops_self_eval_report unit tests (mocks; no Docker)."""

from __future__ import annotations

from bolsa_application.ops_self_eval import build_ops_self_eval_report


def test_semi_warn_when_zero_confirms_and_buys() -> None:
    report = build_ops_self_eval_report(
        account_id="default-account-seed",
        lookback_days=120,
        paper_d_execute_env=False,
        kill_switch_effective=False,
        broker_venue="paper",
        days_with_opinions=28,
        buy_precision_5d=None,
        buy_recall_5d=0.0,
        confirm_seed=0,
        journal_seed=0,
        buys_seed=0,
        trade_like=0,
        cash_max_dd_frac=0.002,
    )
    assert report["schemaVersion"] == "ops_self_eval_v0"
    assert report["lanes"]["semi"]["mark"] == "WARN"
    assert report["lanes"]["auto"]["mark"] == "FAIL"
    assert report["lanes"]["auto"]["strictAcceptReady"] is False
    assert report["runtime"]["paperDExecuteEnv"] is False
    assert report["portfolioReconciliation"]["status"] == "not_wired"
    # OR-6: AUTO FAIL no se promedia; recon gap → PAPER_DEGRADED (no %)
    assert report["operationalReadiness"]["state"] == "PAPER_DEGRADED"
    assert "recon_not_certified" in report["operationalReadiness"]["reasons"]
    assert "%" not in report["operationalReadiness"]["rule"]


def test_auto_pass_when_all_strict_gates_green() -> None:
    report = build_ops_self_eval_report(
        account_id="default-account-seed",
        lookback_days=120,
        paper_d_execute_env=True,
        kill_switch_effective=False,
        broker_venue="paper",
        days_with_opinions=60,
        buy_precision_5d=0.75,
        buy_recall_5d=0.6,
        alarma_buy_count=10,
        mature_buy_sample=8,
        confirm_seed=50,
        journal_seed=50,
        buys_seed=40,
        trade_like=40,
        cash_max_dd_frac=0.05,
        portfolio_reconciliation_status="ok",
        portfolio_reconciliation={"ok": True, "issues": []},
    )
    assert report["lanes"]["auto"]["mark"] == "PASS"
    assert report["lanes"]["auto"]["strictAcceptReady"] is True
    assert report["lanes"]["semi"]["mark"] == "PASS"
    assert report["portfolioReconciliation"]["ok"] is True
    assert report["operationalReadiness"]["state"] == "PAPER_READY"
    assert report["operationalReadiness"]["reasons"] == []


def test_unavailable_when_telemetry_missing() -> None:
    report = build_ops_self_eval_report(
        account_id="acc",
        lookback_days=90,
        paper_d_execute_env=False,
        kill_switch_effective=True,
        broker_venue="live",
        days_with_opinions=None,
        confirm_seed=1,
        journal_seed=8,
        buys_seed=0,
        trade_like=0,
        cash_max_dd_frac=0.002,
    )
    assert report["lanes"]["auto"]["mark"] == "UNAVAILABLE"
    assert report["lanes"]["auto"]["p1"]["mark"] == "UNAVAILABLE"
    assert report["lanes"]["semi"]["mark"] == "PASS"  # confirmSeed=1 → evidencia mínima
    assert report["operationalReadiness"]["state"] == "LIVE_BLOCKED"
    assert "kill_switch" in report["operationalReadiness"]["reasons"]
    assert "recon_not_certified" in report["operationalReadiness"]["reasons"]


def test_or6_auto_fail_does_not_average_away_paper_ready() -> None:
    """AUTO FAIL (P1–P5) no tumba PAPER_READY si recon está ok."""
    report = build_ops_self_eval_report(
        account_id="acc",
        lookback_days=120,
        paper_d_execute_env=False,
        kill_switch_effective=False,
        broker_venue="paper",
        days_with_opinions=28,
        buy_precision_5d=None,
        buy_recall_5d=0.0,
        confirm_seed=3,
        journal_seed=8,
        buys_seed=2,
        trade_like=2,
        cash_max_dd_frac=0.002,
        portfolio_reconciliation_status="ok",
        portfolio_reconciliation={"ok": True, "issues": []},
    )
    assert report["lanes"]["auto"]["mark"] == "FAIL"
    assert report["lanes"]["semi"]["mark"] == "PASS"
    assert report["operationalReadiness"]["state"] == "PAPER_READY"
    assert report["operationalReadiness"]["reasons"] == []
