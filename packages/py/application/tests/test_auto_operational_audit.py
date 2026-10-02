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
    build_cycle_settlement_entry,
    build_entry_order_entry,
    build_reservation_claim_entry,
    build_reservation_reconciliation_entry,
    operational_audit_enabled,
)
from bolsa_application.auto_operational_monitor import (
    AUTO_CYCLE_SETTLEMENT_EVENT,
    AUTO_ENTRY_ORDER_EVENT,
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
    # ``conflict`` ausente = NO DECLARADO: no se deriva de ``claimed`` ni se inventa motivo.
    assert payload["conflict"] is None
    assert payload["conflictReason"] is None
    assert payload["conflictMeasurement"] == "UNKNOWN"
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
    payload = entry.payload or {}
    assert payload["claimed"] is False
    # Un claim PERDIDO no declara carrera por sí solo: sin ``conflict`` explícito viaja NO
    # DECLARADO (UNKNOWN), nunca ``duplicate_claim`` fabricado.
    assert payload["conflict"] is None
    assert payload["conflictReason"] is None
    assert payload["conflictMeasurement"] == "UNKNOWN"
    assert payload["caller"] == "sess-loser"


def test_declared_conflict_is_measured_and_carries_its_reason() -> None:
    """Sólo la capa que DEMOSTRÓ la carrera puede emitir ``conflict=True`` (COMPLETE)."""
    entry = build_reservation_claim_entry(
        reservation_id="res-1",
        cycle_id="cyc-1",
        claimed=False,
        actor="auto-sim",
        session_id="sess-loser",
        as_of="2026-01-02T00:00:00Z",
        conflict=True,
        conflict_reason="duplicate_claim",
    )
    assert entry is not None
    payload = entry.payload or {}
    assert payload["conflict"] is True
    assert payload["conflictReason"] == "duplicate_claim"
    assert payload["conflictMeasurement"] == "COMPLETE"


def test_explicit_no_conflict_is_a_declared_complete_measurement() -> None:
    """``conflict=False`` es un hecho DECLARADO ("no hubo carrera") ⇒ COMPLETE, sin motivo."""
    entry = build_reservation_claim_entry(
        reservation_id="res-1",
        cycle_id="cyc-1",
        claimed=False,
        actor="auto-sim",
        session_id="sess-a",
        as_of="2026-01-02T00:00:00Z",
        conflict=False,
    )
    assert entry is not None
    payload = entry.payload or {}
    assert payload["conflict"] is False
    assert payload["conflictReason"] is None
    assert payload["conflictMeasurement"] == "COMPLETE"


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


# ── v2.88.25 — ENTRY_ORDER y SETTLEMENT durables ──


def test_entry_order_entry_seals_requested_vs_applied_and_source() -> None:
    entry = build_entry_order_entry(
        order_id="ORD-1",
        instrument_id="AAPL",
        side="BUY",
        requested_qty=100,
        applied_qty=73.5,
        partial=True,
        price_source="MARKET_CLOSE",
        cycle_id="cyc-abc",
        actor="auto-sim",
        as_of="2026-01-02T00:00:00Z",
        account_id="acc-1",
    )
    assert entry is not None
    assert entry.event_type == AUTO_ENTRY_ORDER_EVENT
    assert entry.decision_id == "dec-abc"  # derivado del ciclo, igual que el resto de la cadena
    assert entry.account_id == "acc-1"
    payload = entry.payload or {}
    assert payload["event"] == AUTO_ENTRY_ORDER_EVENT
    assert payload["orderId"] == "ORD-1"
    assert payload["side"] == "buy"
    # Pedido vs materializado viajan SEPARADOS: un fill parcial no se disfraza de completo.
    assert payload["requestedQty"] == 100.0
    assert payload["appliedQty"] == 73.5
    assert payload["partial"] is True
    assert payload["priceSource"] == "MARKET_CLOSE"
    assert payload["cycleId"] == "cyc-abc"
    assert payload["cycleIdDerived"] is True


def test_entry_order_entry_without_order_is_a_declared_noop() -> None:
    assert (
        build_entry_order_entry(
            order_id=None,
            instrument_id="AAPL",
            side="buy",
            requested_qty=100,
            applied_qty=100,
            partial=False,
            price_source="SYNTHETIC",
            cycle_id="cyc-1",
            actor="auto-sim",
            as_of="2026-01-02T00:00:00Z",
        )
        is None
    )


def test_entry_order_entry_declares_unknown_source_as_none() -> None:
    """Una fuente ajena al vocabulario NO se convierte en literal: se declara ``None``."""
    entry = build_entry_order_entry(
        order_id="ORD-1",
        instrument_id="AAPL",
        side="buy",
        requested_qty=100,
        applied_qty=100,
        partial=False,
        price_source="TOTALLY_MADE_UP",
        cycle_id="cyc-1",
        actor="auto-sim",
        as_of="2026-01-02T00:00:00Z",
    )
    assert entry is not None
    assert (entry.payload or {})["priceSource"] is None


def test_cycle_settlement_entry_carries_pnl_and_measurement() -> None:
    entry = build_cycle_settlement_entry(
        settlement_id="SET-1",
        instrument_id="AAPL",
        side="SELL",
        closed_qty=10,
        pnl=123.45,
        settled_at="2026-01-02T03:00:00Z",
        exit_reason="time_exit",
        price_source="MARKET_CLOSE",
        cycle_id="cyc-abc",
        actor="auto-sim",
        as_of="2026-01-02T03:00:00Z",
        account_id="acc-1",
    )
    assert entry is not None
    assert entry.event_type == AUTO_CYCLE_SETTLEMENT_EVENT
    assert entry.decision_id == "dec-abc"
    payload = entry.payload or {}
    assert payload["settlementId"] == "SET-1"
    assert payload["closedQty"] == 10.0
    assert payload["pnl"] == 123.45
    assert payload["pnlMeasurement"] == "COMPLETE"
    assert payload["exitReason"] == "time_exit"
    assert payload["settledAt"] == "2026-01-02T03:00:00Z"
    assert payload["cycleId"] == "cyc-abc"


def test_cycle_settlement_entry_partial_pnl_keeps_no_figure() -> None:
    """Con evidencia truncada el PnL es ``None`` + ``PARTIAL``: nunca una cifra sobre un recorte."""
    entry = build_cycle_settlement_entry(
        settlement_id="SET-2",
        instrument_id="AAPL",
        side="sell",
        closed_qty=10,
        pnl=None,
        pnl_measurement="PARTIAL",
        settled_at="2026-01-02T03:00:00Z",
        exit_reason=None,
        price_source=None,
        cycle_id="cyc-1",
        actor="auto-sim",
        as_of="2026-01-02T03:00:00Z",
    )
    assert entry is not None
    payload = entry.payload or {}
    assert payload["pnl"] is None
    assert payload["pnlMeasurement"] == "PARTIAL"
    assert payload["priceSource"] is None


def test_cycle_settlement_entry_without_cycle_is_a_declared_noop() -> None:
    assert (
        build_cycle_settlement_entry(
            settlement_id="SET-1",
            instrument_id="AAPL",
            side="sell",
            closed_qty=10,
            pnl=1.0,
            settled_at="2026-01-02T03:00:00Z",
            exit_reason=None,
            price_source=None,
            cycle_id=None,
            actor="auto-sim",
            as_of="2026-01-02T03:00:00Z",
        )
        is None
    )
