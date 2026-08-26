"""OperationalIncident DEX-3 — review → resolve → clear (ADR-035)."""

from datetime import UTC, datetime

import pytest

from bolsa_analytics.cognitive.operational_incident import (
    can_clear,
    clear_incident,
    incident_blocks_opening,
    incident_opening_veto_reason,
    kinds_from_recon,
    mark_in_review,
    open_incident,
    operational_incident_status_copy,
    resolve_incident,
)

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def _open():
    return open_incident(
        incident_id="inc-1",
        account_id="acc-1",
        kind="portfolio_drift",
        snapshot="cash_ledger mismatch",
        now=_NOW,
    )


def test_open_starts_active() -> None:
    inc = _open()
    assert inc.status == "open"
    assert incident_blocks_opening(inc.status) is True
    assert inc.to_dict()["incidentId"] == "inc-1"
    assert inc.to_dict()["openedAt"].startswith("2026-08-26")


def test_full_path_open_review_resolve_clear() -> None:
    inc = mark_in_review(_open(), reviewed_by="op", now=_NOW)
    assert inc.status == "in_review"
    resolved = resolve_incident(
        inc,
        resolution_note="cash aligned after manual deposit",
        resolved_by="op",
        now=_NOW,
    )
    assert resolved.status == "resolved"
    assert resolved.resolution_note is not None
    assert can_clear(resolved, recon_status="clean") is True
    cleared = clear_incident(resolved, recon_status="clean", now=_NOW)
    assert cleared.status == "cleared"
    assert incident_blocks_opening(cleared.status) is False


def test_resolve_from_open_skips_review() -> None:
    resolved = resolve_incident(_open(), resolution_note="ack")
    assert resolved.status == "resolved"


def test_resolve_requires_note() -> None:
    with pytest.raises(ValueError, match="resolution_note_required"):
        resolve_incident(_open(), resolution_note="   ")


def test_clear_while_drift_fails() -> None:
    resolved = resolve_incident(_open(), resolution_note="looking")
    assert can_clear(resolved, recon_status="drift") is False
    with pytest.raises(ValueError, match="recon_not_clean"):
        clear_incident(resolved, recon_status="drift")


def test_clear_before_resolve_fails() -> None:
    with pytest.raises(ValueError, match="not_resolved"):
        clear_incident(_open(), recon_status="clean")


def test_cannot_review_after_resolved() -> None:
    resolved = resolve_incident(_open(), resolution_note="done")
    with pytest.raises(ValueError, match="invalid_transition"):
        mark_in_review(resolved)


def test_kinds_from_recon_paper_ignores_live() -> None:
    assert kinds_from_recon(
        portfolio_recon_status="drift",
        live_recon_status="unavailable",
        broker_venue="paper",
    ) == ("portfolio_drift",)
    assert kinds_from_recon(
        live_recon_status="unavailable",
        broker_venue="live",
    ) == ("live_unavailable",)


def test_veto_gate_off_without_require() -> None:
    assert incident_opening_veto_reason() is None
    assert (
        incident_opening_veto_reason(incident_status="unresolved")
        == "incident:unresolved"
    )
    assert incident_opening_veto_reason(incident_status="clear", require=True) is None


def test_copy_mentions_no_auto_heal() -> None:
    assert "auto-heal" in operational_incident_status_copy("open").lower()
    assert "auto-heal" in operational_incident_status_copy("resolved").lower()
