"""F4→live — live_auto dry-run statuses (sin broker)."""

from __future__ import annotations

from bolsa_application.execution_router import ExecutionActionResult


def test_live_dry_run_status_literals():
    # Smoke: tipos de resultado aceptados por el contrato
    r = ExecutionActionResult(
        instrument_id="i1",
        signal_kind="entry_long",
        status="live_dry_run_pass",
        reason="Gate+auto_live PASS — broker no cableado (F6); sin orden real",
    )
    assert r.status == "live_dry_run_pass"
    v = ExecutionActionResult(
        instrument_id="i1",
        signal_kind="entry_long",
        status="live_dry_run_veto",
        reason="live dry-run VETO: edge_report_missing",
    )
    assert v.status == "live_dry_run_veto"
