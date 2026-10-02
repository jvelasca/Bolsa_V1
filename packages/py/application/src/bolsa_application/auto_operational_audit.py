"""AUTO Operational Monitor · ``M2`` — sumidero de auditoría en el spine (contrato puro).

Qué cierra: los hechos que hacen visible la cadena AUTO existían **sólo en memoria** del
proceso y por eso el monitor los declaraba ``unknown``/``NO MEDIDO``. Este módulo es el
contrato puro de las entradas append-only que los hacen durables en
``decision_journal_entries`` (ADR-029 F1), **sin migración**:

* ``auto_entry_decision`` (ya producido por ``auto_v2_entry``) **persistido** con su
  ``cycleId`` en el ``payload`` ⇒ ``SIGNAL``/``TOP_N``/``RISK`` pasan a ser enlazables por
  ``decision_id``/``cycleId``.
* ``auto_reservation_claim`` — claim ganado/perdido (la carrera por la PK determinista de
  ``portfolio_reservations``, AUTO-6).
* ``auto_reservation_reconciliation`` — la decisión del barrido por reserva:
  ``caller`` (sesión), ``mine``, ``decision`` (``KEEP``/``RELEASE``), ``reason``,
  ``aged`` y ``graceWindowSeconds``.

Tres reglas duras, declaradas en vez de asumidas:

* **Identidad derivada, nunca inventada.** Un ``cycle_id`` con forma ``cyc-<x>`` tiene por
  decisión ``dec-<x>`` (``cycle_decision_id``): es lo que permite leer por el índice de
  ``decision_id`` sin migración. Sin esa forma la entrada **no finge** una derivación: se
  marca con ``decision_id`` propio y ``cycleIdDerived = False``.
* **Un hecho no medido viaja declarado.** ``caller``/``aged``/``graceWindowSeconds``
  ausentes van a ``None`` con su medición, **nunca** a un valor de relleno.
* **Read-only respecto al dinero.** Este módulo **no** escribe en la base de datos;
  construye el registro que el worker entrega a su sink durable. La escritura vive en
  ``build_operational_audit_sink`` y sólo ocurre tras el flag ``AUTO_OPERATIONAL_AUDIT``
  (default **OFF**).
"""

from __future__ import annotations

import math
import os
from typing import Any
from uuid import uuid4

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)
from bolsa_application.auto_cycle_journal import cycle_decision_id
from bolsa_application.auto_operational_monitor import (
    AUTO_CYCLE_SETTLEMENT_EVENT,
    AUTO_ENTRY_ORDER_EVENT,
    AUTO_PROTECTION_EVENT,
    AUTO_RESERVATION_CLAIM_EVENT,
    AUTO_RESERVATION_RECONCILIATION_EVENT,
)
from bolsa_application.price_source_kind import usable_price_source
from bolsa_application.protection_event_kind import usable_protection_kind
from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord

__all__ = [
    "AUTO_OPERATIONAL_AUDIT_ENV",
    "RECONCILIATION_KEEP",
    "RECONCILIATION_RELEASE",
    "REASON_GRACE_WINDOW_KEEP",
    "REASON_SESSION_OWNED",
    "build_cycle_settlement_entry",
    "build_entry_order_entry",
    "build_protection_entry",
    "build_reservation_claim_entry",
    "build_reservation_reconciliation_entry",
    "durable_fact_dedupe_key",
    "operational_audit_enabled",
]

#: Interruptor de la costura inerte (mismo patrón que ``AUTO_ENGINE_SIM_REAL_PRICE``).
AUTO_OPERATIONAL_AUDIT_ENV = "AUTO_OPERATIONAL_AUDIT"

#: Decisiones del barrido (el vocabulario que pinta el panel de ownership).
RECONCILIATION_KEEP = "KEEP"
RECONCILIATION_RELEASE = "RELEASE"
#: Motivos de ``KEEP`` (los de ``RELEASE`` son los ``RELEASE_REASON_*`` de la reserva).
REASON_GRACE_WINDOW_KEEP = "grace_window_keep"
REASON_SESSION_OWNED = "session_owned"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_DECISION_ID_PREFIX = "dec-"


def operational_audit_enabled(raw: str | None = None) -> bool:
    """``True`` sólo con un valor explícito de encendido; ausente/vacío ⇒ ``False`` (Δ = 0)."""
    value = raw if raw is not None else os.getenv(AUTO_OPERATIONAL_AUDIT_ENV)
    return str(value or "").strip().lower() in _TRUE_VALUES


def durable_fact_dedupe_key(
    *,
    event_type: str | None,
    account_id: str | None,
    engine_id: str | None,
    cycle_id: str | None = None,
    order_id: str | None = None,
    kind: str | None = None,
    revision_id: str | None = None,
) -> str | None:
    """(PURA) identidad determinista de un hecho durable M2, o ``None`` sin base para ella.

    Es lo que permite que el alta sea idempotente (``INSERT ... ON CONFLICT DO NOTHING``):
    el MISMO hecho reintentado no duplica. Se construye SOLO cuando el productor puede
    demostrar la identidad; si falta un componente no se inventa una clave a medias (``None``)
    y el ``append`` conserva el INSERT plano (Δ = 0).

    Vocabulario (una cosa, una clave):

    * ``auto_cycle_settlement`` — un settlement por ciclo cerrado:
      ``auto_cycle_settlement:{account}:{engine}:{cycle_id}``.
    * ``auto_entry_order`` — una orden de entrada por ciclo y orden:
      ``auto_entry_order:{account}:{engine}:{cycle_id}:{order_id}``.
    * ``auto_protection_event`` — una transición por ciclo, ``kind`` y revisión. La ``kind``
      sola NO basta: dos transiciones legítimas del mismo ``kind`` pueden ocurrir en un ciclo.
      Se exige ``revisionId`` (referencia a la revisión durable); sin él la clave es ``None``.
    """
    event = _text(event_type)
    account = _text(account_id)
    engine = _text(engine_id)
    cycle = _text(cycle_id)
    if event is None or account is None or engine is None or cycle is None:
        return None
    if event == AUTO_CYCLE_SETTLEMENT_EVENT:
        return f"{AUTO_CYCLE_SETTLEMENT_EVENT}:{account}:{engine}:{cycle}"
    if event == AUTO_ENTRY_ORDER_EVENT:
        order = _text(order_id)
        if order is None:
            return None
        return f"{AUTO_ENTRY_ORDER_EVENT}:{account}:{engine}:{cycle}:{order}"
    if event == AUTO_PROTECTION_EVENT:
        resolved_kind = _text(kind)
        revision = _text(revision_id)
        if resolved_kind is None or revision is None:
            return None
        return f"{AUTO_PROTECTION_EVENT}:{account}:{engine}:{cycle}:{resolved_kind}:{revision}"
    return None


def _stamp(as_of: str | None) -> str:
    if as_of:
        return str(as_of)
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decision_id(cycle_id: str | None) -> tuple[str, bool]:
    """``decision_id`` del ciclo (derivado del prefijo) y si la derivación se pudo probar."""
    derived = cycle_decision_id(cycle_id)
    if derived is not None:
        return derived, True
    return f"{_DECISION_ID_PREFIX}{uuid4().hex[:12]}", False


def build_reservation_claim_entry(
    *,
    reservation_id: str | None,
    cycle_id: str | None,
    claimed: bool,
    actor: str,
    session_id: str | None,
    as_of: str | None,
    account_id: str | None = None,
    instrument_id: str | None = None,
    conflict: bool | None = None,
    conflict_reason: str | None = None,
) -> DecisionJournalEntryRecord | None:
    """(PURA) entrada append-only del claim de una reserva, o ``None`` sin reserva.

    ``claimed = True`` es el claim **ganado** por esta sesión (dueña del compromiso);
    ``False`` es el claim **perdido** (ya había un compromiso vivo con la misma identidad
    determinista). El hecho de que un claim perdido sea además una **carrera** se declara
    aparte en ``conflict``/``conflictReason``: ``claimed=False`` también puede venir de
    invalid/expired/already_released/wrong_state, así que **NO se infiere**.

    Sin ``conflict`` explícito el conflicto viaja **NO DECLARADO**: ``conflict=None`` con su
    ``conflictMeasurement = UNKNOWN`` y sin ``conflictReason`` inventado. Sólo la capa de
    concurrencia que **demostró** la carrera puede emitir ``conflict=True``; un claim perdido
    sin esa prueba queda como ``lostClaims``, nunca como ``raceConflicts``.
    """
    rid = _text(reservation_id)
    if rid is None:
        return None
    cycle = _text(cycle_id)
    decision_id, derived = _decision_id(cycle)
    # ``conflict`` ausente = NO DECLARADO (UNKNOWN), jamás ``not claimed``: un claim perdido no
    # demuestra por sí solo una carrera (invalid/expired/already_released/wrong_state).
    resolved_conflict: bool | None = None if conflict is None else bool(conflict)
    resolved_reason = _text(conflict_reason)
    payload: dict[str, Any] = {
        "event": AUTO_RESERVATION_CLAIM_EVENT,
        "reservation_id": rid,
        "claimed": bool(claimed),
        "conflict": resolved_conflict,
        "conflictReason": resolved_reason,
        "conflictMeasurement": (
            MEASUREMENT_COMPLETE if conflict is not None else MEASUREMENT_UNKNOWN
        ),
        "cycleIdDerived": derived,
    }
    if cycle is not None:
        payload["cycleId"] = cycle
    instrument = _text(instrument_id)
    if instrument is not None:
        payload["instrumentId"] = instrument
    caller = _text(session_id)
    payload["caller"] = caller
    payload["callerMeasurement"] = (
        MEASUREMENT_COMPLETE if caller is not None else MEASUREMENT_UNKNOWN
    )
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision_id,
        event_type=AUTO_RESERVATION_CLAIM_EVENT,
        actor=str(actor or ""),
        created_at=_stamp(as_of),
        # ``session_id`` apunta por FK a ``decision_sessions`` (sesiones de decisión reales):
        # la sesión del motor viaja en ``payload.caller`` para no inventar una fila ni migrar.
        session_id=None,
        account_id=_text(account_id),
        instrument_id=instrument,
        payload=payload,
    )


def build_reservation_reconciliation_entry(
    *,
    reservation_id: str | None,
    cycle_id: str | None,
    decision: str,
    reason: str | None,
    mine: bool | None,
    aged: bool | None,
    grace_window_seconds: float | None,
    actor: str,
    session_id: str | None,
    as_of: str | None,
    account_id: str | None = None,
    instrument_id: str | None = None,
    measured: bool = True,
) -> DecisionJournalEntryRecord | None:
    """(PURA) entrada append-only de la decisión del barrido sobre UNA reserva.

    ``caller`` es la sesión que ejecuta el barrido; ``mine`` distingue si la reserva estaba
    en su libro (autoridad de retirada) o si se conserva por ventana de gracia. ``aged`` y
    ``graceWindowSeconds`` viajan con su medición: sin dato medible van ``None`` +
    ``UNKNOWN``, jamás un ``0`` que afirmaría "envejecida"/"sin gracia".
    """
    rid = _text(reservation_id)
    if rid is None:
        return None
    cycle = _text(cycle_id)
    decision_id, derived = _decision_id(cycle)
    caller = _text(session_id)
    rejection = _text(reason)
    measured_flag: MeasurementStatus = MEASUREMENT_COMPLETE if measured else MEASUREMENT_UNKNOWN
    payload: dict[str, Any] = {
        "event": AUTO_RESERVATION_RECONCILIATION_EVENT,
        "reservation_id": rid,
        "decision": str(decision or "").upper(),
        "reason": rejection,
        "reasonMeasurement": (MEASUREMENT_COMPLETE if rejection else MEASUREMENT_UNKNOWN),
        "mine": None if mine is None else bool(mine),
        "caller": caller,
        "callerMeasurement": (MEASUREMENT_COMPLETE if caller else MEASUREMENT_UNKNOWN),
        "aged": None if aged is None else bool(aged),
        "agedMeasurement": (MEASUREMENT_COMPLETE if aged is not None else MEASUREMENT_UNKNOWN),
        "graceWindowSeconds": (
            float(grace_window_seconds) if grace_window_seconds is not None else None
        ),
        "graceWindowMeasurement": (
            MEASUREMENT_COMPLETE if grace_window_seconds is not None else MEASUREMENT_UNKNOWN
        ),
        "cycleIdDerived": derived,
        "reconciliationMeasurement": measured_flag,
    }
    if cycle is not None:
        payload["cycleId"] = cycle
    instrument = _text(instrument_id)
    if instrument is not None:
        payload["instrumentId"] = instrument
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision_id,
        event_type=AUTO_RESERVATION_RECONCILIATION_EVENT,
        actor=str(actor or ""),
        created_at=_stamp(as_of),
        # Ver ``build_reservation_claim_entry``: la sesión va en ``payload.caller``, no en la
        # columna con FK a ``decision_sessions``.
        session_id=None,
        account_id=_text(account_id),
        instrument_id=instrument,
        payload=payload,
    )


def _number(raw: Any) -> float | None:
    """Número finito utilizable, o ``None`` (nunca un ``0`` que afirme una medición)."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def build_entry_order_entry(
    *,
    order_id: str | None,
    instrument_id: str | None,
    side: str,
    requested_qty: Any,
    applied_qty: Any,
    partial: bool,
    price_source: str | None,
    cycle_id: str | None,
    actor: str,
    as_of: str | None,
    account_id: str | None = None,
) -> DecisionJournalEntryRecord | None:
    """(PURA) entrada append-only de la ORDEN DE ENTRADA emitida y materializada.

    Hasta v2.88.25 la orden de ENTRADA no tenía representación durable (sólo las de SALIDA,
    ``auto_exit_orders``): el monitor declaraba ``entry_order_not_durable``. Esta entrada la
    sella por ``cycle_id`` con la cantidad PEDIDA y la MATERIALIZADA (que difieren con un fill
    parcial) y la FUENTE de precio usada. Sin orden/instrumento no se finge una: ``None``.
    """
    oid = _text(order_id)
    instrument = _text(instrument_id)
    if oid is None or instrument is None:
        return None
    cycle = _text(cycle_id)
    decision_id, derived = _decision_id(cycle)
    raw_side = _text(side)
    payload: dict[str, Any] = {
        "event": AUTO_ENTRY_ORDER_EVENT,
        "orderId": oid,
        "instrumentId": instrument,
        "side": raw_side.lower() if raw_side else None,
        "requestedQty": _number(requested_qty),
        "appliedQty": _number(applied_qty),
        "partial": bool(partial),
        "priceSource": usable_price_source(price_source),
        "cycleIdDerived": derived,
    }
    if cycle is not None:
        payload["cycleId"] = cycle
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision_id,
        event_type=AUTO_ENTRY_ORDER_EVENT,
        actor=str(actor or ""),
        created_at=_stamp(as_of),
        session_id=None,
        account_id=_text(account_id),
        instrument_id=instrument,
        payload=payload,
    )


def build_cycle_settlement_entry(
    *,
    settlement_id: str | None,
    instrument_id: str | None,
    side: str | None,
    closed_qty: Any,
    pnl: Any,
    pnl_measurement: MeasurementStatus | None = None,
    settled_at: str | None,
    exit_reason: str | None,
    price_source: str | None,
    cycle_id: str | None,
    actor: str,
    as_of: str | None,
    account_id: str | None = None,
) -> DecisionJournalEntryRecord | None:
    """(PURA) entrada append-only del HECHO durable de liquidación de un ciclo.

    Regla dura: un ``CYCLE_CLOSED`` reconstruido de fills **no** es un settlement. Sólo esta
    entrada (emitida al cerrar la posición, con la evidencia del ciclo declarada) enciende el
    paso ``SETTLEMENT``. El PnL viaja con su medición: si la evidencia del ciclo está truncada
    el valor es ``None`` con ``PARTIAL`` — jamás una cifra sobre un subconjunto. Sin ciclo no
    se finge un settlement: ``None``.
    """
    cycle = _text(cycle_id)
    if cycle is None:
        return None
    instrument = _text(instrument_id)
    decision_id, derived = _decision_id(cycle)
    raw_side = _text(side)
    pnl_value = _number(pnl)
    if pnl_value is not None:
        measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    elif pnl_measurement is not None:
        measurement = pnl_measurement
    else:
        measurement = MEASUREMENT_UNKNOWN
    payload: dict[str, Any] = {
        "event": AUTO_CYCLE_SETTLEMENT_EVENT,
        "settlementId": _text(settlement_id),
        "instrumentId": instrument,
        "side": raw_side.lower() if raw_side else None,
        "closedQty": _number(closed_qty),
        "pnl": pnl_value,
        "pnlMeasurement": measurement,
        "settledAt": _text(settled_at) or _stamp(as_of),
        "exitReason": _text(exit_reason),
        "priceSource": usable_price_source(price_source),
        "cycleIdDerived": derived,
        "cycleId": cycle,
    }
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision_id,
        event_type=AUTO_CYCLE_SETTLEMENT_EVENT,
        actor=str(actor or ""),
        created_at=_stamp(as_of),
        session_id=None,
        account_id=_text(account_id),
        instrument_id=instrument,
        payload=payload,
    )


def build_protection_entry(
    *,
    kind: str | None,
    instrument_id: str | None,
    cycle_id: str | None,
    lifecycle_from: str | None,
    lifecycle_to: str | None,
    stop_before: Any,
    stop_after: Any,
    target: Any,
    trailing_status: str | None,
    revision_id: str | None,
    source: str | None,
    actor: str,
    as_of: str | None,
    account_id: str | None = None,
    position_id: str | None = None,
) -> DecisionJournalEntryRecord | None:
    """(PURA) entrada append-only del HECHO durable de una transición de PROTECCIÓN.

    Hasta v2.88.25 la protección vivía **sólo** en la proyección ``position_state``: el monitor
    encendía ``PROTECTION`` con esa proyección y no existía traza append-only de *cuándo* cambió
    el stop, se alcanzó T1/T2, se armó el trailing o se pidió la salida. Esta entrada sella esa
    transición por ``cycle_id``.

    Canonicalidad: el hecho es la **traza** de la transición que ya produjo ``PositionState``
    (la autoridad): NO re-deriva el stop ni el estado — los copia. ``revisionId``/``positionId``
    son la referencia al estado durable. Sin ``instrument_id``/``cycle_id`` no se finge un hecho:
    ``None``. Un ``kind`` ajeno al vocabulario se declara ``None`` (no medido), nunca inventado.
    """
    instrument = _text(instrument_id)
    cycle = _text(cycle_id)
    if instrument is None or cycle is None:
        return None
    resolved_kind = usable_protection_kind(kind)
    decision_id, derived = _decision_id(cycle)
    raw_from = _text(lifecycle_from)
    raw_to = _text(lifecycle_to)
    payload: dict[str, Any] = {
        "event": AUTO_PROTECTION_EVENT,
        "kind": resolved_kind,
        "instrumentId": instrument,
        "positionId": _text(position_id),
        "lifecycleFrom": raw_from.upper() if raw_from else None,
        "lifecycleTo": raw_to.upper() if raw_to else None,
        "stopBefore": _number(stop_before),
        "stopAfter": _number(stop_after),
        "target": _number(target),
        "trailingStatus": _text(trailing_status),
        "revisionId": _text(revision_id),
        "source": _text(source),
        "at": _stamp(as_of),
        "cycleIdDerived": derived,
        "cycleId": cycle,
    }
    return DecisionJournalEntryRecord(
        id=f"JNL-{uuid4().hex[:12]}",
        decision_id=decision_id,
        event_type=AUTO_PROTECTION_EVENT,
        actor=str(actor or ""),
        created_at=_stamp(as_of),
        session_id=None,
        account_id=_text(account_id),
        instrument_id=instrument,
        payload=payload,
    )
