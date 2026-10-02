"""Tests puros de ``auto_operational_audit`` (``M2``) — el contrato de la traza durable.

Sin I/O: se comprueba la forma de las entradas append-only (identidad derivada, payload
estable, sesión como dueño/caller) y las reglas de honestidad (un hueco ``None`` con su
medición, nunca un valor de relleno). El ``event_type`` es el que el monitor lee.
"""

from __future__ import annotations

import os
from typing import Any

from bolsa_application.auto_operational_audit import (
    AUTO_OPERATIONAL_AUDIT_ENV,
    REASON_GRACE_WINDOW_KEEP,
    REASON_SESSION_OWNED,
    RECONCILIATION_KEEP,
    RECONCILIATION_RELEASE,
    build_cycle_settlement_entry,
    build_entry_order_entry,
    build_protection_entry,
    build_reservation_claim_entry,
    build_reservation_reconciliation_entry,
    durable_fact_dedupe_key,
    operational_audit_enabled,
)
from bolsa_application.auto_operational_monitor import (
    AUTO_CYCLE_SETTLEMENT_EVENT,
    AUTO_ENTRY_ORDER_EVENT,
    AUTO_PROTECTION_EVENT,
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


# ── v2.88.26 — PROTECTION durable ──


def test_protection_entry_seals_the_transition_and_the_venue() -> None:
    entry = build_protection_entry(
        kind="TRAIL_ADVANCED",
        instrument_id="AAPL",
        cycle_id="cyc-abc",
        position_id="pos-1",
        lifecycle_from="T1_REACHED",
        lifecycle_to="TRAILING",
        stop_before=99.0,
        stop_after=101.5,
        target=1,
        trailing_status="armed",
        revision_id="rev-1",
        source="plan",
        actor="auto-sim",
        as_of="2026-01-02T00:00:00Z",
        account_id="acc-1",
    )
    assert entry is not None
    assert entry.event_type == AUTO_PROTECTION_EVENT
    assert entry.decision_id == "dec-abc"  # derivado del ciclo, igual que el resto de la cadena
    assert entry.account_id == "acc-1"
    assert entry.instrument_id == "AAPL"
    payload = entry.payload or {}
    assert payload["event"] == AUTO_PROTECTION_EVENT
    assert payload["kind"] == "TRAIL_ADVANCED"
    assert payload["lifecycleFrom"] == "T1_REACHED"
    assert payload["lifecycleTo"] == "TRAILING"
    assert payload["stopBefore"] == 99.0
    assert payload["stopAfter"] == 101.5
    assert payload["target"] == 1.0
    assert payload["trailingStatus"] == "armed"
    assert payload["revisionId"] == "rev-1"
    assert payload["source"] == "plan"
    assert payload["cycleId"] == "cyc-abc"
    assert payload["cycleIdDerived"] is True


def test_protection_entry_normalizes_kind_and_upper_cases_lifecycle() -> None:
    entry = build_protection_entry(
        kind="t2_hit",
        instrument_id="AAPL",
        cycle_id="cyc-1",
        position_id=None,
        lifecycle_from="t1_reached",
        lifecycle_to="trailing",
        stop_before=None,
        stop_after=None,
        target=2,
        trailing_status=None,
        revision_id=None,
        source=None,
        actor="auto-sim",
        as_of="2026-01-02T00:00:00Z",
    )
    assert entry is not None
    payload = entry.payload or {}
    # El ``kind`` se normaliza contra el vocabulario cerrado (mayúsculas/espacios).
    assert payload["kind"] == "T2_HIT"
    assert payload["lifecycleFrom"] == "T1_REACHED"
    assert payload["lifecycleTo"] == "TRAILING"
    # Un stop sin valor viaja ``None`` (no medido), jamás un ``0``.
    assert payload["stopBefore"] is None
    assert payload["stopAfter"] is None


def test_protection_entry_declares_unknown_kind_as_none() -> None:
    """Un ``kind`` ajeno al vocabulario NO se convierte en literal: se declara ``None``."""
    entry = build_protection_entry(
        kind="TOTALLY_MADE_UP",
        instrument_id="AAPL",
        cycle_id="cyc-1",
        position_id="pos-1",
        lifecycle_from="OPEN",
        lifecycle_to="PROTECTED",
        stop_before=100,
        stop_after=100,
        target=None,
        trailing_status=None,
        revision_id=None,
        source=None,
        actor="auto-sim",
        as_of="2026-01-02T00:00:00Z",
    )
    assert entry is not None
    assert (entry.payload or {})["kind"] is None


def test_protection_entry_without_cycle_or_instrument_is_a_declared_noop() -> None:
    common: dict[str, Any] = {
        "kind": "PROTECT_APPLIED",
        "cycle_id": "cyc-1",
        "position_id": None,
        "lifecycle_from": None,
        "lifecycle_to": None,
        "stop_before": None,
        "stop_after": None,
        "target": None,
        "trailing_status": None,
        "revision_id": None,
        "source": None,
        "actor": "auto-sim",
        "as_of": "2026-01-02T00:00:00Z",
    }
    assert build_protection_entry(instrument_id=None, **common) is None
    assert build_protection_entry(instrument_id="AAPL", **{**common, "cycle_id": None}) is None


# ── v2.88.27 — identidad determinista de los hechos M2 (deduplicación) ────────────────


def test_settlement_dedupe_key_is_deterministic_and_one_per_cycle() -> None:
    key = durable_fact_dedupe_key(
        event_type=AUTO_CYCLE_SETTLEMENT_EVENT,
        account_id="acc-1",
        engine_id="auto-sim",
        cycle_id="cyc-1",
    )
    assert key == "auto_cycle_settlement:acc-1:auto-sim:cyc-1"
    # El MISMO hecho vuelve a dar la MISMA clave: es lo que hace idempotente el reintento.
    assert (
        durable_fact_dedupe_key(
            event_type=AUTO_CYCLE_SETTLEMENT_EVENT,
            account_id="acc-1",
            engine_id="auto-sim",
            cycle_id="cyc-1",
        )
        == key
    )


def test_entry_order_dedupe_key_needs_the_order_identity() -> None:
    assert (
        durable_fact_dedupe_key(
            event_type=AUTO_ENTRY_ORDER_EVENT,
            account_id="acc-1",
            engine_id="auto-sim",
            cycle_id="cyc-1",
            order_id="ord-9",
        )
        == "auto_entry_order:acc-1:auto-sim:cyc-1:ord-9"
    )
    # Sin orden no hay identidad demostrable: ``None`` (el ``append`` conserva el INSERT plano).
    assert (
        durable_fact_dedupe_key(
            event_type=AUTO_ENTRY_ORDER_EVENT,
            account_id="acc-1",
            engine_id="auto-sim",
            cycle_id="cyc-1",
        )
        is None
    )


def test_protection_dedupe_key_requires_the_revision_not_only_kind() -> None:
    """Dos transiciones legítimas del MISMO ``kind`` pueden convivir: la ``kind`` sola no basta."""
    assert (
        durable_fact_dedupe_key(
            event_type=AUTO_PROTECTION_EVENT,
            account_id="acc-1",
            engine_id="auto-sim",
            cycle_id="cyc-1",
            kind="TRAIL_ADVANCED",
            revision_id="rev-2",
        )
        == "auto_protection_event:acc-1:auto-sim:cyc-1:TRAIL_ADVANCED:rev-2"
    )
    assert (
        durable_fact_dedupe_key(
            event_type=AUTO_PROTECTION_EVENT,
            account_id="acc-1",
            engine_id="auto-sim",
            cycle_id="cyc-1",
            kind="TRAIL_ADVANCED",
            revision_id=None,
        )
        is None
    )


def test_dedupe_key_without_identity_components_is_none() -> None:
    """Sin cuenta/motor/ciclo no se inventa una clave a medias, y un ``event_type`` ajeno es ``None``."""
    base = {"account_id": "acc-1", "engine_id": "auto-sim", "cycle_id": "cyc-1"}
    assert durable_fact_dedupe_key(event_type=AUTO_CYCLE_SETTLEMENT_EVENT, **{**base, "cycle_id": None}) is None
    assert durable_fact_dedupe_key(event_type=AUTO_CYCLE_SETTLEMENT_EVENT, **{**base, "account_id": None}) is None
    assert durable_fact_dedupe_key(event_type=AUTO_CYCLE_SETTLEMENT_EVENT, **{**base, "engine_id": None}) is None
    assert durable_fact_dedupe_key(event_type="auto_entry_decision", **base) is None
    assert durable_fact_dedupe_key(event_type=None, **base) is None
