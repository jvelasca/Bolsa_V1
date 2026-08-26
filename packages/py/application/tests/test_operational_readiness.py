"""OR-6 — derive_operational_readiness + execute_cta_label (mocks; no Docker)."""

from __future__ import annotations

from bolsa_application.operational_readiness import (
    derive_operational_readiness,
    execute_cta_label,
)


def test_paper_ready_when_recon_ok_and_semi_path() -> None:
    report = derive_operational_readiness(
        broker_venue="paper",
        kill_switch_effective=False,
        portfolio_reconciliation_status="ok",
        semi_path_mark="PASS",
    )
    assert report["state"] == "PAPER_READY"
    assert report["venue"] == "paper"
    assert report["reasons"] == []


def test_auto_fail_does_not_enter_formula() -> None:
    """AUTO P1–P5 FAIL no es parámetro: no se promedia a degradado."""
    report = derive_operational_readiness(
        broker_venue="paper",
        portfolio_reconciliation_status="ok",
        semi_path_mark="PASS",
    )
    assert report["state"] == "PAPER_READY"


def test_portfolio_drift_is_critical_not_averaged() -> None:
    report = derive_operational_readiness(
        broker_venue="paper",
        portfolio_reconciliation_status="drift",
        semi_path_mark="PASS",
    )
    assert report["state"] == "PAPER_DEGRADED"
    assert "portfolio_drift" in report["reasons"]
    assert "%" not in report["rule"]


def test_recon_gap_degrades_paper() -> None:
    report = derive_operational_readiness(
        broker_venue="paper",
        portfolio_reconciliation_status="not_wired",
        semi_path_mark="PASS",
    )
    assert report["state"] == "PAPER_DEGRADED"
    assert "recon_not_certified" in report["reasons"]


def test_semi_warn_stays_ready_with_note() -> None:
    report = derive_operational_readiness(
        broker_venue="paper",
        portfolio_reconciliation_status="ok",
        semi_path_mark="WARN",
    )
    assert report["state"] == "PAPER_READY"
    assert "thin_semi_evidence" in report["notes"]


def test_semi_unavailable_degrades() -> None:
    report = derive_operational_readiness(
        broker_venue="paper",
        portfolio_reconciliation_status="ok",
        semi_path_mark="UNAVAILABLE",
    )
    assert report["state"] == "PAPER_DEGRADED"
    assert "semi_path_unavailable" in report["reasons"]


def test_kill_switch_degrades_paper() -> None:
    report = derive_operational_readiness(
        broker_venue="paper",
        kill_switch_effective=True,
        portfolio_reconciliation_status="ok",
        semi_path_mark="PASS",
    )
    assert report["state"] == "PAPER_DEGRADED"
    assert "kill_switch" in report["reasons"]


def test_live_clean_is_experimental_never_ready() -> None:
    report = derive_operational_readiness(
        broker_venue="live",
        portfolio_reconciliation_status="ok",
        semi_path_mark="PASS",
    )
    assert report["state"] == "LIVE_EXPERIMENTAL"
    assert "live_not_accepted" in report["notes"]
    assert report["state"] != "PAPER_READY"


def test_live_drift_blocks() -> None:
    report = derive_operational_readiness(
        broker_venue="live",
        portfolio_reconciliation_status="ok",
        live_reconciliation_status="unavailable",
        semi_path_mark="PASS",
    )
    assert report["state"] == "LIVE_BLOCKED"
    assert "live_unavailable" in report["reasons"]


def test_live_adapter_not_wired_blocks() -> None:
    report = derive_operational_readiness(
        broker_venue="live",
        portfolio_reconciliation_status="ok",
        live_adapter_wired=False,
        semi_path_mark="PASS",
    )
    assert report["state"] == "LIVE_BLOCKED"
    assert "live_adapter_not_wired" in report["reasons"]


def test_execute_cta_labels_venue() -> None:
    assert execute_cta_label("paper") == "Ejecutar en PAPER"
    assert execute_cta_label("live") == "Ejecutar en LIVE"
    assert execute_cta_label("paper", kind="protect") == "Confirmar protección"
