"""Tests puros de ``auto_operational_audit`` (``M2``) — el contrato de la traza durable.

Sin I/O: se comprueba la forma de las entradas append-only (identidad derivada, payload
estable, sesión como dueño/caller) y las reglas de honestidad (un hueco ``None`` con su
medición, nunca un valor de relleno). El ``event_type`` es el que el monitor lee.
"""

from __future__ import annotations

import os

from bolsa_application.auto_operational_audit import (
    AUTO_OPERATIONAL_AUDIT_ENV,
    REASON_GRACE_WINDOW_KEEP,
    REASON_SESSION_OWNED,
    RECONCILIATION_KEEP,
    RECONCILIATION_RELEASE,
    build_reservation_claim_entry,
    build_reservation_reconciliation_entry,
    operational_audit_enabled,
)
from bolsa_application.auto_operational_monitor import (
    AUTO_RESERVATION_CLAIM_EVENT,
    AUTO_RESERVATION_RECONCILIATION_EVENT,
)


def test_operational_audit_flag_is_off_by_default() -> None:
    """La costura inerte: ausente/vacío ⇒ OFF (Δ = 0); sólo un valor explícito la enciende."""
    previous = os.environ.pop(AUTO_OPERATIONAL_AUDIT_ENV, None)
    try:
        assert operational_audit_enabled() is False
        assert operational_audit_enabled("") is False
        assert operational_audit_enabled("0") is False
        assert operational_audit_enabled("false") is False
        assert operational_audit_enabled("1") is True
        assert operational_audit_enabled("ON") is True
    finally:
        if previous is not None:
            os.environ[AUTO_OPERATIONAL_AUDIT_ENV] = previous


def test_claim_entry_derives_decision_id_and_declares_owner() -> None:
    entry = build_reservation_claim_entry(
        reservation_id="RES-dec-abc",
        cycle_id="cyc-abc",
        claimed=True,
        actor="auto-sim",
        session_id="sess-a",
        as_of="2026-01-02T00:00:00Z",
        account_id="acc-1",
        instrument_id="AAPL",
    )
    assert entry is not None
    assert entry.event_type == AUTO_RESERVATION_CLAIM_EVENT
    assert entry.decision_id == "dec-abc"  # derivado del prefijo, sin recalcular digest
    # La columna tiene FK a ``decision_sessions``: la sesión va en ``payload.caller``.
    assert entry.session_id is None
    assert entry.account_id == "acc-1"
    payload = entry.payload or {}
    assert payload["reservation_id"] == "RES-dec-abc"
    assert payload["cycleId"] == "cyc-abc"
    assert payload["claimed"] is True
    assert payload["caller"] == "sess-a"
    assert payload["callerMeasurement"] == "COMPLETE"
    assert payload["cycleIdDerived"] is True


def test_claim_entry_without_reservation_is_a_declared_noop() -> None:
    assert (
        build_reservation_claim_entry(
            reservation_id=None,
            cycle_id="cyc-1",
            claimed=False,
            actor="auto-sim",
            session_id="sess-a",
            as_of="2026-01-02T00:00:00Z",
        )
        is None
    )


def test_lost_claim_is_recorded_as_lost_with_session() -> None:
    entry = build_reservation_claim_entry(
        reservation_id="res-1",
        cycle_id="cyc-1",
        claimed=False,
        actor="auto-sim",
        session_id="sess-loser",
        as_of="2026-01-02T00:00:00Z",
    )
    assert entry is not None
    assert (entry.payload or {})["claimed"] is False
    assert (entry.payload or {})["caller"] == "sess-loser"


def test_release_reconciliation_carries_caller_reason_and_age() -> None:
    entry = build_reservation_reconciliation_entry(
        reservation_id="res-1",
        cycle_id="cyc-1",
        decision=RECONCILIATION_RELEASE,
        reason="fill",
        mine=True,
        aged=True,
        grace_window_seconds=61.0,
        actor="auto-sim",
        session_id="sess-a",
        as_of="2026-01-02T00:00:00Z",
        account_id="acc-1",
        instrument_id="AAPL",
    )
    assert entry is not None
    assert entry.event_type == AUTO_RESERVATION_RECONCILIATION_EVENT
    assert entry.session_id is None  # ver ``test_claim_entry_derives_...`` (FK a decision_sessions)
    payload = entry.payload or {}
    assert payload["caller"] == "sess-a"
    assert payload["decision"] == "RELEASE"
    assert payload["reason"] == "fill"
    assert payload["mine"] is True
    assert payload["aged"] is True
    assert payload["agedMeasurement"] == "COMPLETE"
    assert payload["graceWindowSeconds"] == 61.0
    assert payload["graceWindowMeasurement"] == "COMPLETE"
    assert payload["callerMeasurement"] == "COMPLETE"


def test_grace_window_keep_records_foreign_young_reservation() -> None:
    entry = build_reservation_reconciliation_entry(
        reservation_id="res-1",
        cycle_id="cyc-1",
        decision=RECONCILIATION_KEEP,
        reason=REASON_GRACE_WINDOW_KEEP,
        mine=False,
        aged=False,
        grace_window_seconds=30.0,
        actor="auto-sim",
        session_id="sess-a",
        as_of="2026-01-02T00:00:00Z",
    )
    payload = (entry.payload or {}) if entry else {}
    assert payload["decision"] == "KEEP"
    assert payload["reason"] == REASON_GRACE_WINDOW_KEEP
    assert payload["mine"] is False
    assert payload["aged"] is False


def test_owned_keep_declares_session_owned_reason() -> None:
    entry = build_reservation_reconciliation_entry(
        reservation_id="res-1",
        cycle_id=None,
        decision=RECONCILIATION_KEEP,
        reason=REASON_SESSION_OWNED,
        mine=True,
        aged=None,
        grace_window_seconds=None,
        actor="auto-sim",
        session_id="sess-a",
        as_of="2026-01-02T00:00:00Z",
    )
    assert entry is not None
    payload = entry.payload or {}
    assert payload["reason"] == REASON_SESSION_OWNED
    # Sin ciclo no se finge la derivación: identidad propia y ``cycleIdDerived = False``.
    assert payload["cycleIdDerived"] is False
    assert "cycleId" not in payload
    # Un hueco medible se declara ``UNKNOWN``, nunca un ``0``.
    assert payload["aged"] is None
    assert payload["agedMeasurement"] == "UNKNOWN"
    assert payload["graceWindowSeconds"] is None
    assert payload["graceWindowMeasurement"] == "UNKNOWN"
