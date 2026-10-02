"""AUTO Operational Monitor — proyección READ-ONLY de la cadena AUTO a la UI.

Qué cierra: hasta hoy la app solo podía decir ``AUTO = RUNNING`` (postura + preview de plan +
evidencia agregada). La cadena de operación —``SIGNAL → TOP_N → RISK → RESERVATION → ORDER →
FILL → PROTECTION → SETTLEMENT → CYCLE CLOSED``— no tenía una proyección canónica, así que el
usuario no podía auditar qué había hecho el motor ciclo a ciclo. Este módulo es el **lector
único** de esa cadena sobre el estado DURABLE que ya existe.

Camino obligatorio (regla de la casa): ``DOMAIN EVENT → PERSISTED OPERATIONAL STATE → CANONICAL
DTO → UI``. La UI **no interpreta** ni re-deriva: pinta este DTO. Aquí no se decide nada, no se
escribe nada y no se sintetiza ningún paso.

Tres reglas duras, declaradas en vez de asumidas:

* **Un paso sin traza durable se declara, no se finge.** El estado del paso es ``unknown`` (o
  ``absent``) con su nota; un valor no medido viaja ``None`` **y** su ``measurement``, nunca un
  ``0``/``100.0`` silencioso.
* **El ciclo se identifica por ``cycle_id``.** La reconstrucción de PnL reutiliza
  ``cycles_from_fills`` (AUTO-7): el MISMO material del informe, sin un segundo FIFO que pueda
  divergir en silencio.
* **``M1`` vs ``M2``.** ``SIGNAL``/``TOP_N``/``RISK`` se leen del spine durable
  (``decision_journal_entries``); mientras ese journal de decisión no se persista (lo cierra el
  sumidero de ``M2``, tras flag), el paso se declara ``unknown`` con la nota ``signal_not_durable``.
  La ownership de reserva y las métricas de concurrencia que solo viven en memoria se declaran
  ``NO MEDIDO`` igual que cualquier otro hueco.

Read-only: este módulo NO escribe (ni journal ni tabla) y NO cambia la semántica del motor.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)
from bolsa_application.auto_cycle_journal import cycle_decision_id
from bolsa_application.auto_self_evaluation_feed import cycles_from_fills

__all__ = [
    "AUTO_ENTRY_DECISION_EVENT",
    "AUTO_RESERVATION_CLAIM_EVENT",
    "AUTO_RESERVATION_RECONCILIATION_EVENT",
    "OPERATIONAL_STEPS",
    "STEP_ABSENT",
    "STEP_PENDING",
    "STEP_REACHED",
    "STEP_UNKNOWN",
    "build_operational_monitor",
    "read_operational_monitor",
]

logger = logging.getLogger(__name__)

#: Orden canónico de la cadena operativa. La UI lo pinta tal cual; no reordena.
OPERATIONAL_STEPS: tuple[str, ...] = (
    "SIGNAL",
    "TOP_N",
    "RISK",
    "RESERVATION",
    "ORDER",
    "FILL",
    "PROTECTION",
    "SETTLEMENT",
    "CYCLE_CLOSED",
)

#: Estados de un paso (fail-closed: ``unknown`` es un estado NOMBRADO, no un hueco mudo).
STEP_REACHED = "reached"
STEP_PENDING = "pending"
STEP_ABSENT = "absent"
STEP_UNKNOWN = "unknown"

#: ``event_type`` de las entradas del spine que este lector consume. El de decisión de entrada
#: ya lo produce ``auto_v2_entry``; los de claim/reconciliación los produce el sumidero de ``M2``
#: (``auto_operational_audit``). Se declaran aquí como fuente única de los literales.
AUTO_ENTRY_DECISION_EVENT = "auto_entry_decision"
AUTO_RESERVATION_CLAIM_EVENT = "auto_reservation_claim"
AUTO_RESERVATION_RECONCILIATION_EVENT = "auto_reservation_reconciliation"

#: Motivos de liberación que cuentan como retirada FORZADA (no por fill materializado).
_FORCED_RELEASE_REASONS: frozenset[str] = frozenset({"cancel", "restart", "tail_dead", "rollback"})
#: Motivo de la ventana de gracia (M2): conservar una reserva joven de un par ajeno.
GRACE_WINDOW_KEEP = "grace_window_keep"


def _get(holder: Any, *names: str) -> Any:
    """Primer campo no ``None`` de ``names`` en un objeto o Mapping; ``None`` si no hay."""
    for name in names:
        value = getattr(holder, name, None)
        if value is None and isinstance(holder, Mapping):
            value = holder.get(name)
        if value is not None:
            return value
    return None


def _parse_instant(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _iso(moment: datetime | None) -> str | None:
    return None if moment is None else moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _step(
    step_id: str,
    *,
    state: str,
    at: str | None = None,
    measurement: MeasurementStatus = MEASUREMENT_COMPLETE,
    facts: Sequence[Mapping[str, Any]] = (),
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "state": state,
        "at": at,
        "measurement": measurement,
        "facts": [dict(fact) for fact in facts],
        "note": note,
    }


def _fact(key: str, value: Any, measurement: MeasurementStatus = MEASUREMENT_COMPLETE) -> dict[str, Any]:
    return {"key": key, "value": value, "measurement": measurement}


def _cycle_id_of(holder: Any) -> str:
    value = _get(holder, "cycle_id", "cycleId")
    return str(value).strip() if isinstance(value, str) else ""


def _journal_for_cycle(entries: Sequence[Any], cycle_id: str) -> list[Any]:
    """Entradas del spine ligadas al ciclo: por ``decision_id`` derivado o por ``payload.cycleId``.

    ``cycle_decision_id`` intercambia el prefijo (``cyc-`` → ``dec-``) sin recalcular digest, que
    es lo que permite leer por el índice de ``decision_id`` sin migración. Una entrada que no
    declare el ``cycleId`` en el ``payload`` tampoco se descarta: se confirma el vínculo en ambos
    sentidos para no creerse una derivación equivocada.
    """
    decision_id = cycle_decision_id(cycle_id)
    matched: list[Any] = []
    for entry in entries:
        if decision_id is not None and _get(entry, "decision_id", "decisionId") == decision_id:
            matched.append(entry)
            continue
        payload = _get(entry, "payload")
        if isinstance(payload, Mapping) and str(payload.get("cycleId") or "").strip() == cycle_id:
            matched.append(entry)
    return matched


def _entry_payload(entry: Any) -> Mapping[str, Any]:
    payload = _get(entry, "payload")
    return payload if isinstance(payload, Mapping) else {}


def _net_open_qty(fills: Sequence[Any]) -> float:
    """Cantidad neta viva del ciclo (compras − ventas); ``> 0`` ⇒ el ciclo sigue abierto."""
    total = 0.0
    for fill in fills:
        qty = float(_get(fill, "quantity") or 0.0)
        side = str(_get(fill, "side") or "").strip().lower()
        total += qty if side == "buy" else (-qty if side == "sell" else 0.0)
    return total


def _applied_friction(fills: Sequence[Any]) -> tuple[float | None, MeasurementStatus]:
    """Fricción APLICADA del ciclo desde el ``reference_mid`` durable (AUTO-16), sin I/O nuevo.

    ``|price − reference_mid| × qty`` sobre los fills que SÍ declaran referencia. Sin ninguna
    referencia el valor es ``None`` con ``UNKNOWN`` (nunca un ``0``, que diría "fricción gratis");
    con referencias parciales el agregado es un suelo y se declara ``PARTIAL``.
    """
    total = 0.0
    valued = 0
    unvalued = 0
    for fill in fills:
        ref = _get(fill, "reference_mid", "referenceMid")
        price = _get(fill, "price")
        qty = _get(fill, "quantity")
        if ref is None or price is None or qty is None:
            unvalued += 1
            continue
        try:
            spread = abs(float(price) - float(ref))
            total += spread * float(qty)
        except (TypeError, ValueError):
            unvalued += 1
            continue
        valued += 1
    if valued == 0 and unvalued == 0:
        return None, MEASUREMENT_COMPLETE
    if valued == 0:
        return None, MEASUREMENT_UNKNOWN
    return round(total, 6), MEASUREMENT_COMPLETE if unvalued == 0 else MEASUREMENT_PARTIAL


def _entry_decision_step(
    step_id: str,
    journal: Sequence[Any],
    *,
    note_absent: str,
) -> dict[str, Any]:
    """``SIGNAL``/``TOP_N``/``RISK`` desde el journal de decisión durable (o declarados)."""
    entry = next(
        (row for row in journal if _get(row, "event_type", "eventType") == AUTO_ENTRY_DECISION_EVENT),
        None,
    )
    if entry is None:
        return _step(step_id, state=STEP_UNKNOWN, measurement=MEASUREMENT_UNKNOWN, note=note_absent)
    payload = _entry_payload(entry)
    at = _iso(_parse_instant(_get(entry, "created_at", "createdAt")))
    facts: list[dict[str, Any]] = []
    if step_id == "SIGNAL":
        if payload.get("instrumentId"):
            facts.append(_fact("instrumentId", payload.get("instrumentId")))
        if payload.get("strategyVersion"):
            facts.append(_fact("strategyVersion", payload.get("strategyVersion")))
        if payload.get("opportunityScore") is not None:
            facts.append(_fact("score", payload.get("opportunityScore")))
    elif step_id == "TOP_N":
        if payload.get("rank") is not None:
            facts.append(_fact("rank", payload.get("rank")))
    elif step_id == "RISK":
        for key in ("quantity", "riskAmount", "stop", "entry", "riskPct"):
            if payload.get(key) is not None:
                facts.append(_fact(key, payload.get(key)))
    if not facts:
        return _step(step_id, state=STEP_UNKNOWN, measurement=MEASUREMENT_UNKNOWN, note=note_absent)
    return _step(step_id, state=STEP_REACHED, at=at, facts=facts)


def _reservation_step(reservation: Any | None) -> dict[str, Any]:
    if reservation is None:
        return _step(
            "RESERVATION",
            state=STEP_ABSENT,
            measurement=MEASUREMENT_UNKNOWN,
            note="no_reservation_for_cycle",
        )
    risk = _get(reservation, "reserved_risk", "reservedRisk")
    facts = [
        _fact("quantity", _get(reservation, "quantity")),
        _fact("remainingQty", _get(reservation, "remaining_qty", "remainingQty")),
        _fact("side", _get(reservation, "side")),
        _fact("status", _get(reservation, "status")),
        _fact("reservedRisk", risk, MEASUREMENT_COMPLETE if risk is not None else MEASUREMENT_UNKNOWN),
        _fact("stop", _get(reservation, "stop")),
        _fact("entry", _get(reservation, "entry")),
    ]
    release_reason = _get(reservation, "release_reason", "releaseReason")
    if release_reason is not None:
        facts.append(_fact("releaseReason", release_reason))
    is_live = _get(reservation, "is_live")
    if is_live is None and isinstance(reservation, Mapping):
        is_live = str(_get(reservation, "status") or "").upper() == "OPEN"
    at = _iso(_parse_instant(_get(reservation, "created_at", "createdAt")))
    return _step("RESERVATION", state=STEP_REACHED, at=at, facts=facts)


def _order_step(orders: Sequence[Any]) -> dict[str, Any]:
    """``ORDER`` — INTENT de salida durable. La emisión de la orden de ENTRADA no es durable."""
    if not orders:
        return _step(
            "ORDER",
            state=STEP_UNKNOWN,
            measurement=MEASUREMENT_UNKNOWN,
            note="entry_order_not_durable",
        )
    facts: list[dict[str, Any]] = []
    for order in orders:
        facts.append(
            _fact(
                "exitOrder",
                {
                    "exitOrderId": _get(order, "exit_order_id", "exitOrderId"),
                    "state": _get(order, "state"),
                    "requestedQty": _get(order, "requested_qty", "requestedQty"),
                    "filledQty": _get(order, "filled_qty", "filledQty"),
                    "remainingQty": _get(order, "remaining_qty", "remainingQty"),
                },
            )
        )
    at = _iso(_parse_instant(_get(orders[0], "created_at", "createdAt")))
    return _step("ORDER", state=STEP_REACHED, at=at, facts=facts)


def _fill_step(fills: Sequence[Any]) -> dict[str, Any]:
    if not fills:
        return _step("FILL", state=STEP_PENDING, measurement=MEASUREMENT_UNKNOWN, note="no_fills")
    buys = [f for f in fills if str(_get(f, "side") or "").lower() == "buy"]
    sells = [f for f in fills if str(_get(f, "side") or "").lower() == "sell"]

    def _vwap(rows: Sequence[Any]) -> tuple[float | None, float]:
        qty_total = 0.0
        notional = 0.0
        for row in rows:
            try:
                q = float(_get(row, "quantity") or 0.0)
                p = float(_get(row, "price") or 0.0)
            except (TypeError, ValueError):
                continue
            qty_total += q
            notional += q * p
        return (round(notional / qty_total, 6) if qty_total > 0 else None, qty_total)

    buy_vwap, buy_qty = _vwap(buys)
    sell_vwap, sell_qty = _vwap(sells)
    friction, friction_measurement = _applied_friction(fills)
    facts = [
        _fact("buyQty", round(buy_qty, 6)),
        _fact("buyVwap", buy_vwap, MEASUREMENT_COMPLETE if buy_vwap is not None else MEASUREMENT_UNKNOWN),
        _fact("sellQty", round(sell_qty, 6)),
        _fact(
            "sellVwap",
            sell_vwap,
            MEASUREMENT_COMPLETE if sell_vwap is not None else MEASUREMENT_UNKNOWN,
        ),
        _fact("appliedFriction", friction, friction_measurement),
    ]
    at = _iso(_parse_instant(_get(fills[-1], "created_at", "createdAt")))
    return _step("FILL", state=STEP_REACHED, at=at, facts=facts)


def _protection_step(position: Mapping[str, Any] | None) -> dict[str, Any]:
    if position is None:
        return _step(
            "PROTECTION",
            state=STEP_UNKNOWN,
            measurement=MEASUREMENT_UNKNOWN,
            note="no_open_position_for_cycle",
        )
    state_map = position.get("positionState") or {}
    mfe_mae = state_map.get("mfeMae") if isinstance(state_map, Mapping) else None
    facts = [
        _fact("stopPrice", position.get("stopPrice")),
        _fact(
            "currentStop",
            state_map.get("currentStop") if isinstance(state_map, Mapping) else None,
        ),
        _fact("highWatermark", position.get("highWatermark")),
        _fact("t1State", position.get("t1State")),
        _fact("trailingState", position.get("trailingState")),
        _fact(
            "protectionState",
            state_map.get("protectionState") if isinstance(state_map, Mapping) else None,
        ),
        _fact(
            "lifecycleState",
            state_map.get("lifecycleState") if isinstance(state_map, Mapping) else None,
        ),
        _fact("mfeMae", mfe_mae),
    ]
    return _step("PROTECTION", state=STEP_REACHED, facts=facts)


def _settlement_step(
    settlement: Mapping[str, Any] | None,
    fills: Sequence[Any],
) -> dict[str, Any]:
    """``SETTLEMENT`` — SOLO desde un hecho durable explícito de liquidación.

    Regla dura de esta versión: un ciclo cerrado (``cycles_from_fills``) **no** demuestra que
    haya ocurrido un settlement durable. Tener ``fill + PnL + ciclo cerrado`` no es evidencia de
    liquidación, así que sin un evento/estado durable de settlement el paso se declara
    ``unknown`` con ``settlement_not_durable`` — **jamás** ``reached``. El PnL se lee en
    ``CYCLE_CLOSED``. La costura ``settlement`` queda lista para el ``SETTLEMENT_EVENT`` de ``M2``.
    """
    if settlement is None:
        return _step(
            "SETTLEMENT",
            state=STEP_UNKNOWN,
            measurement=MEASUREMENT_UNKNOWN,
            note="settlement_not_durable",
        )
    friction, friction_measurement = _applied_friction(fills)
    facts: list[dict[str, Any]] = [
        _fact("appliedFriction", friction, friction_measurement),
    ]
    for key in ("settlementId", "pnl", "settledAt"):
        if settlement.get(key) is not None:
            facts.append(_fact(key, settlement.get(key)))
    return _step(
        "SETTLEMENT",
        state=STEP_REACHED,
        at=settlement.get("settledAt"),
        facts=facts,
    )


def _cycle_closed_step(closed: Mapping[str, Any] | None) -> dict[str, Any]:
    if closed is None:
        return _step("CYCLE_CLOSED", state=STEP_PENDING, measurement=MEASUREMENT_UNKNOWN)
    return _step(
        "CYCLE_CLOSED",
        state=STEP_REACHED,
        at=closed.get("closedAt"),
        facts=[_fact("pnl", closed.get("pnl")), _fact("reason", closed.get("reason", "flat"))],
    )


def _build_cycle(
    cycle_id: str,
    *,
    reservations: Sequence[Any],
    orders_by_cycle: Mapping[str, Sequence[Any]],
    fills_by_cycle: Mapping[str, Sequence[Any]],
    positions_by_cycle: Mapping[str, Mapping[str, Any]],
    closed_by_cycle: Mapping[str, Mapping[str, Any]],
    journal: Sequence[Any],
    settlement_by_cycle: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    reservation = reservations[0] if reservations else None
    cycle_journal = _journal_for_cycle(journal, cycle_id)
    cycle_fills = list(fills_by_cycle.get(cycle_id, ()))
    orders = list(orders_by_cycle.get(cycle_id, ()))
    closed = closed_by_cycle.get(cycle_id)
    settlement = (settlement_by_cycle or {}).get(cycle_id)
    net = _net_open_qty(cycle_fills)
    is_open = net > 1e-9
    side = str(_get(reservation, "side") or "").strip().lower() if reservation else ""

    steps = [
        _entry_decision_step("SIGNAL", cycle_journal, note_absent="signal_not_durable"),
        _entry_decision_step("TOP_N", cycle_journal, note_absent="top_n_not_durable"),
        _entry_decision_step("RISK", cycle_journal, note_absent="risk_not_durable"),
        _reservation_step(reservation),
        _order_step(orders),
        _fill_step(cycle_fills),
        _protection_step(positions_by_cycle.get(cycle_id)),
        _settlement_step(settlement, cycle_fills),
        _cycle_closed_step(closed),
    ]
    notes: list[str] = []
    for step in steps:
        if step["state"] == STEP_UNKNOWN and step["note"]:
            notes.append(step["note"])
    return {
        "cycleId": cycle_id,
        "instrumentId": _get(reservation, "instrument_id", "instrumentId"),
        "strategyVersion": _get(reservation, "strategy_version_id", "strategyVersionId"),
        "direction": "short" if side == "sell" else "long",
        "closed": closed is not None and not is_open,
        "steps": steps,
        "result": (
            None
            if closed is None
            else {
                "pnl": closed.get("pnl"),
                "closedAt": closed.get("closedAt"),
            }
        ),
        "notes": notes,
    }


def _claim_owner(claims: Sequence[Any], reservation_id: str) -> tuple[str | None, str]:
    """Dueño durable del compromiso: la sesión del claim GANADO de esa reserva.

    Se lee del spine (``auto_reservation_claim`` con ``claimed = True``). Sin claim ganado el
    dueño no se puede afirmar: ``None`` con ``UNKNOWN`` (nunca un propietario inventado).
    """
    for entry in claims:
        payload = _entry_payload(entry)
        rid = _get(entry, "reservation_id", "reservationId") or payload.get(
            "reservation_id", payload.get("reservationId")
        )
        if str(rid or "") != reservation_id:
            continue
        if payload.get("claimed") is True:
            owner = payload.get("caller") or _get(entry, "session_id", "sessionId")
            owner_text = str(owner).strip() if owner else ""
            if owner_text:
                return owner_text, MEASUREMENT_COMPLETE
    return None, MEASUREMENT_UNKNOWN


def _reservation_view(
    reservation: Any,
    *,
    reconciliations: Sequence[Any],
    claims: Sequence[Any],
    grace_seconds: float | None,
) -> dict[str, Any]:
    reservation_id = str(_get(reservation, "reservation_id", "reservationId") or "")
    created = _parse_instant(_get(reservation, "created_at", "createdAt"))
    expires = (
        created + timedelta(seconds=grace_seconds)
        if created is not None and grace_seconds is not None
        else None
    )
    quantity = _get(reservation, "quantity")
    remaining = _get(reservation, "remaining_qty", "remainingQty")
    released = _get(reservation, "released_qty", "releasedQty")
    filled = None
    if quantity is not None and remaining is not None:
        try:
            filled = round(float(quantity) - float(remaining), 6)
        except (TypeError, ValueError):
            filled = None
    if filled is None:
        try:
            filled = round(float(released), 6) if released is not None else None
        except (TypeError, ValueError):
            filled = None
    release_reason = _get(reservation, "release_reason", "releaseReason")
    is_live = _get(reservation, "is_live")
    if is_live is None:
        is_live = str(_get(reservation, "status") or "").upper() == "OPEN"

    events: list[dict[str, Any]] = []
    for entry in reconciliations:
        payload = _entry_payload(entry)
        entry_reservation = _get(entry, "reservation_id", "reservationId") or payload.get(
            "reservation_id", payload.get("reservationId")
        )
        if str(entry_reservation or "") != reservation_id:
            continue
        events.append(
            {
                "at": _iso(_parse_instant(_get(entry, "created_at", "createdAt"))),
                "caller": payload.get("caller"),
                "decision": payload.get("decision"),
                "reason": payload.get("reason"),
                "aged": payload.get("aged"),
                "graceWindowSeconds": payload.get("graceWindowSeconds"),
            }
        )
    owner_session, owner_measurement = _claim_owner(claims, reservation_id)
    return {
        "reservationId": reservation_id,
        "instrumentId": _get(reservation, "instrument_id", "instrumentId"),
        "side": _get(reservation, "side"),
        "quantity": quantity,
        "remainingQty": remaining,
        # Ownership durable: la sesión del claim ganado (``M2``, spine). Sin claim ganado se
        # declara ``NO MEDIDO``, nunca un dueño inferido del proceso que pinta.
        "ownerSession": owner_session,
        "ownerMeasurement": owner_measurement,
        "created": _iso(created),
        "expires": _iso(expires),
        "expiresMeasurement": (
            MEASUREMENT_COMPLETE if expires is not None else MEASUREMENT_UNKNOWN
        ),
        "state": "LIVE" if is_live else "RELEASED",
        "releaseReason": release_reason,
        "releaseReasonMeasurement": (
            MEASUREMENT_COMPLETE if (release_reason is not None or not is_live) else MEASUREMENT_UNKNOWN
        ),
        "fillProgress": {
            "filled": filled,
            "requested": quantity,
            "measurement": MEASUREMENT_COMPLETE if filled is not None else MEASUREMENT_UNKNOWN,
        },
        "reconciliations": events,
    }


def _header(
    engine: Any,
    *,
    engine_ticks: int,
    granularity: Mapping[str, Any],
    interval_seconds: float | None,
    real_price_enabled: bool,
    grace_seconds: float | None,
    last_decision_at: datetime | None,
    as_of: str,
) -> dict[str, Any]:
    # ``last_tick_at`` es el LATIDO del motor, NO la última decisión de inversión. Se exponen
    # por separado (``lastHeartbeatAt`` vs ``lastDecisionAt``): mezclarlos haría pasar un
    # heartbeat por una decisión. La próxima decisión solo se deriva si hay decisión durable.
    last_tick = _parse_instant(_get(engine, "last_tick_at", "lastTickAt")) if engine else None
    next_decision = (
        last_decision_at + timedelta(seconds=interval_seconds)
        if last_decision_at is not None and interval_seconds is not None
        else None
    )
    return {
        "engineId": _get(engine, "engine_id", "engineId"),
        "state": _get(engine, "state") or "UNKNOWN",
        "venue": _get(engine, "venue") or "paper",
        "granularity": dict(granularity),
        "decisionClock": "CLOSED BAR",
        "executionDeclared": granularity.get("executionDeclared"),
        "executionEnabled": granularity.get("executionEnabled"),
        "protectionModel": granularity.get("protection"),
        "heartbeatSeconds": interval_seconds,
        "graceSeconds": grace_seconds,
        "lastHeartbeatAt": _iso(last_tick),
        "lastHeartbeatMeasurement": (
            MEASUREMENT_COMPLETE if last_tick is not None else MEASUREMENT_UNKNOWN
        ),
        "lastDecisionAt": _iso(last_decision_at),
        "lastDecisionMeasurement": (
            MEASUREMENT_COMPLETE if last_decision_at is not None else MEASUREMENT_UNKNOWN
        ),
        "nextDecisionAt": _iso(next_decision),
        "realPriceEnabled": real_price_enabled,
        "heartbeatsPersisted": engine_ticks,
        "asOf": as_of,
    }


def _last_decision_instant(journal: Sequence[Any]) -> datetime | None:
    """Instante de la última DECISIÓN de entrada durable (``auto_entry_decision``).

    Sin entrada durable de decisión no hay "última decisión": devolver el ``last_tick_at`` del
    motor sería afirmar un heartbeat como decisión. ``None`` ⇒ la UI rotula ``NO MEDIDO``.
    """
    moments = [
        _parse_instant(_get(entry, "created_at", "createdAt"))
        for entry in journal
        if _get(entry, "event_type", "eventType") == AUTO_ENTRY_DECISION_EVENT
    ]
    valid = [moment for moment in moments if moment is not None]
    return max(valid) if valid else None


def _concurrency(
    *,
    engine_ticks: int,
    reservations: Sequence[Any],
    reconcilations: Sequence[Any],
    claims: Sequence[Any],
    journal: Sequence[Any],
) -> dict[str, Any]:
    reconciliations_count = len(reconcilations)
    grace_keeps = sum(
        1
        for entry in reconcilations
        if _entry_payload(entry).get("reason") == GRACE_WINDOW_KEEP
    )
    has_claims = bool(claims)
    # Se DECLARAN por separado: ``claimAttempts`` (todo intento auditado), ``successfulClaims``
    # (``claimed=True``), ``lostClaims`` (``claimed=False``) y ``raceConflicts`` (conflicto de
    # carrera DECLARADO por el productor). ``claimed=False`` NO equivale a carrera: puede ser
    # invalid/expired/already_released/wrong_state; por eso la carrera se lee de
    # ``payload.conflict`` y no se infiere del claim perdido.
    claim_attempts = len(claims) if has_claims else None
    successful_claims = (
        sum(1 for entry in claims if _entry_payload(entry).get("claimed") is True)
        if has_claims
        else None
    )
    lost_claims_count = (
        sum(1 for entry in claims if _entry_payload(entry).get("claimed") is False)
        if has_claims
        else None
    )
    race_conflicts = (
        sum(1 for entry in claims if _entry_payload(entry).get("conflict") is True)
        if has_claims
        else None
    )
    forced_releases = sum(
        1
        for row in reservations
        if str(_get(row, "release_reason", "releaseReason") or "") in _FORCED_RELEASE_REASONS
    )
    def _entry_session(entry: Any) -> str | None:
        # La sesión de motor viaja en ``payload.caller`` (la columna ``session_id`` apunta por
        # FK a ``decision_sessions`` y no se invade); se acepta también la columna por si una
        # entrada la trae de un productor legítimo.
        column = _get(entry, "session_id", "sessionId")
        caller = _entry_payload(entry).get("caller")
        return str(column or caller or "").strip() or None

    sessions = {
        session
        for entry in (*journal, *reconcilations, *claims)
        if (session := _entry_session(entry)) is not None
    }
    # ``activeSessions`` por ``DISTINCT`` sesión del spine: es un SUELO (solo ve sesiones que
    # ya escribieron), no el censo vivo. Sin sesiones en la ventana se declara NO MEDIDO.
    active_sessions: int | None = len(sessions) if sessions else None
    # Último conflicto: la carrera de claim PERDIDA más reciente (otra sesión ya tenía vivo el
    # compromiso con la misma identidad determinista). Sin claims, el hueco se declara.
    lost_claims = [entry for entry in claims if _entry_payload(entry).get("claimed") is False]
    if lost_claims:
        latest = max(lost_claims, key=lambda e: str(_get(e, "created_at", "createdAt") or ""))
        latest_payload = _entry_payload(latest)
        last_conflict: dict[str, Any] | None = {
            "at": _iso(_parse_instant(_get(latest, "created_at", "createdAt"))),
            "reservationId": latest_payload.get("reservation_id", latest_payload.get("reservationId")),
            "loserSession": latest_payload.get("caller"),
        }
        last_conflict_measurement = MEASUREMENT_COMPLETE
    else:
        last_conflict = None
        last_conflict_measurement = MEASUREMENT_COMPLETE if claims else MEASUREMENT_UNKNOWN
    return {
        "activeSessions": active_sessions,
        "activeSessionsMeasurement": (
            MEASUREMENT_PARTIAL if active_sessions is not None else MEASUREMENT_UNKNOWN
        ),
        "heartbeatsPersisted": engine_ticks,
        "claimAttempts": claim_attempts,
        "claimAttemptsMeasurement": MEASUREMENT_COMPLETE if has_claims else MEASUREMENT_UNKNOWN,
        "successfulClaims": successful_claims,
        "successfulClaimsMeasurement": (
            MEASUREMENT_COMPLETE if has_claims else MEASUREMENT_UNKNOWN
        ),
        "lostClaims": lost_claims_count,
        "lostClaimsMeasurement": MEASUREMENT_COMPLETE if has_claims else MEASUREMENT_UNKNOWN,
        "raceConflicts": race_conflicts,
        "raceConflictsMeasurement": MEASUREMENT_COMPLETE if has_claims else MEASUREMENT_UNKNOWN,
        "reconciliations": reconciliations_count if reconcilations else None,
        "reconciliationsMeasurement": (
            MEASUREMENT_COMPLETE if reconcilations else MEASUREMENT_UNKNOWN
        ),
        "graceWindowKeeps": grace_keeps if reconcilations else None,
        "graceWindowKeepsMeasurement": (
            MEASUREMENT_COMPLETE if reconcilations else MEASUREMENT_UNKNOWN
        ),
        "forcedReleases": forced_releases,
        "forcedReleasesMeasurement": MEASUREMENT_COMPLETE,
        "lastConflict": last_conflict,
        "lastConflictMeasurement": last_conflict_measurement,
    }


def build_operational_monitor(
    *,
    account_id: str,
    engine: Any = None,
    engine_ticks: int = 0,
    positions: Mapping[str, Mapping[str, Any]] | None = None,
    reservations: Sequence[Any] = (),
    exit_orders: Sequence[Any] = (),
    fills: Sequence[Any] = (),
    journal: Sequence[Any] = (),
    reconciliation_entries: Sequence[Any] = (),
    claim_entries: Sequence[Any] = (),
    settlements: Sequence[Any] = (),
    granularity: Mapping[str, Any] | None = None,
    interval_seconds: float | None = None,
    grace_seconds: float | None = None,
    real_price_enabled: bool = False,
    cycle_id: str | None = None,
    limit: int = 20,
    as_of: str | None = None,
) -> dict[str, Any]:
    """(PURA) construye el DTO del monitor desde el estado durable ya leído. Sin I/O.

    No sintetiza pasos: cada etapa viene de un hecho durable concreto y lo que no existe se
    declara ``unknown``/``absent`` con su nota. Un ``cycle_id`` filtra a un único ciclo (para el
    drill-down); sin él se devuelven los ciclos de la ventana (``limit``).
    """
    positions = dict(positions or {})
    granularity_view = dict(granularity or {})
    stamp = as_of or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    closed_by_cycle: dict[str, Mapping[str, Any]] = {}
    for row in cycles_from_fills(fills):
        key = str(row.get("cycleId") or "").strip()
        if key:
            closed_by_cycle[key] = row

    reservations_by_cycle: dict[str, list[Any]] = {}
    for row in reservations:
        key = _cycle_id_of(row)
        if key:
            reservations_by_cycle.setdefault(key, []).append(row)

    fills_by_cycle: dict[str, list[Any]] = {}
    for row in fills:
        key = _cycle_id_of(row)
        if key:
            fills_by_cycle.setdefault(key, []).append(row)

    orders_by_cycle: dict[str, list[Any]] = {}
    for row in exit_orders:
        key = _cycle_id_of(row)
        if key:
            orders_by_cycle.setdefault(key, []).append(row)

    positions_by_cycle: dict[str, Mapping[str, Any]] = {}
    for position in positions.values():
        state_map = position.get("positionState") if isinstance(position, Mapping) else None
        key = ""
        if isinstance(state_map, Mapping):
            key = str(state_map.get("cycleId") or "").strip()
        if key:
            positions_by_cycle.setdefault(key, position)

    # Un settlement durable por ciclo (costura de ``M2``): sin entradas el paso se declara
    # ``unknown``; nunca se deriva de ``CYCLE_CLOSED``.
    settlement_by_cycle: dict[str, Mapping[str, Any]] = {}
    for row in settlements:
        key = _cycle_id_of(row)
        if key and isinstance(row, Mapping):
            settlement_by_cycle[key] = row

    cycle_ids: list[str] = []
    seen: set[str] = set()
    if cycle_id:
        ordered = [cycle_id]
    else:
        for row in reservations:
            key = _cycle_id_of(row)
            if key and key not in seen:
                cycle_ids.append(key)
                seen.add(key)
        ordered = cycle_ids
    # Reconstruir el orden si venía de ``cycle_ids`` (incluye ciclos solo en fills/closed).
    for key in list(closed_by_cycle) + list(fills_by_cycle):
        if key and key not in seen and (not cycle_id or key == cycle_id):
            ordered.append(key)
            seen.add(key)

    cycles = [
        _build_cycle(
            key,
            reservations=reservations_by_cycle.get(key, ()),
            orders_by_cycle=orders_by_cycle,
            fills_by_cycle=fills_by_cycle,
            positions_by_cycle=positions_by_cycle,
            closed_by_cycle=closed_by_cycle,
            journal=journal,
            settlement_by_cycle=settlement_by_cycle,
        )
        for key in ordered
    ]
    if cycle_id is None and limit > 0:
        cycles = cycles[:limit]

    reconciliations = list(reconciliation_entries)
    claims = list(claim_entries)
    reservation_views = [
        _reservation_view(
            row, reconciliations=reconciliations, claims=claims, grace_seconds=grace_seconds
        )
        for row in reservations
    ]

    header = _header(
        engine,
        engine_ticks=engine_ticks,
        granularity=granularity_view,
        interval_seconds=interval_seconds,
        real_price_enabled=real_price_enabled,
        grace_seconds=grace_seconds,
        last_decision_at=_last_decision_instant(journal),
        as_of=stamp,
    )
    concurrency = _concurrency(
        engine_ticks=engine_ticks,
        reservations=reservations,
        reconcilations=reconciliations,
        claims=list(claim_entries),
        journal=journal,
    )
    notes: list[str] = []
    if not journal:
        notes.append("decision_journal_not_durable")
    if not reconciliations:
        notes.append("reconciliation_not_durable")
    if not claim_entries:
        notes.append("claim_audit_not_durable")
    if reservation_views and not any(view["ownerSession"] for view in reservation_views):
        # Hay reservas pero ningún claim ganado en el spine: el dueño no se puede afirmar.
        notes.append("owner_session_not_durable")
    return {
        "key": "auto_operational_monitor_v1",
        "readOnly": True,
        "accountId": account_id,
        "asOf": stamp,
        "header": header,
        "cycles": cycles,
        "reservations": reservation_views,
        "concurrency": concurrency,
        "notes": notes,
    }


async def read_operational_monitor(
    session: Any,
    account_id: str,
    *,
    engine_id: str = "auto-sim",
    limit: int = 20,
    cycle_id: str | None = None,
    interval_seconds: float | None = None,
    grace_seconds: float | None = None,
) -> dict[str, Any]:
    """(I/O) lee el estado durable de la cadena AUTO y devuelve el DTO canónico.

    Read-only: solo hay ``SELECT``. Un fallo de lectura de un bloque opcional se declara (el
    ``notes`` del DTO) y NO tumba el resto — un hueco declarado, nunca un ``0`` fingido.
    """
    from bolsa_application.auto_engine_state_store import PostgresAutoEngineStore
    from bolsa_application.exit_order_store import PostgresExitOrderStore
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import (
        PostgresSimAutoPositionStore,
        PostgresSimFillFinanceContextStore,
    )
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    reservation_store = PostgresReservationStore(session, autocommit=False)
    context_store = PostgresSimFillFinanceContextStore(session, autocommit=False)
    position_store = PostgresSimAutoPositionStore(session, autocommit=False)
    exit_store = PostgresExitOrderStore(session, autocommit=False)
    engine_store = PostgresAutoEngineStore(session)
    repository = SqlAlchemyJournalRepository(session)

    if cycle_id:
        reservations = await reservation_store.list_by_cycle_ids(
            account_id, [cycle_id], limit=limit
        )
    else:
        reservations = await reservation_store.list_recent_with_cycle(account_id, limit=limit)

    cycle_ids: list[str] = []
    seen: set[str] = set()
    if cycle_id:
        cycle_ids.append(cycle_id)
        seen.add(cycle_id)
    for row in reservations:
        key = _cycle_id_of(row)
        if key and key not in seen:
            cycle_ids.append(key)
            seen.add(key)

    fills: list[Any] = []
    exit_orders: list[Any] = []
    if cycle_ids:
        fills = await context_store.list_by_cycle_ids(account_id, cycle_ids, limit=max(limit * 50, 200))
        exit_orders = await exit_store.list_by_cycle_ids(account_id, cycle_ids)

    engine = await engine_store.read(engine_id)
    engine_ticks = 0
    try:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

        engine_ticks = int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(AutoEngineTickRow)
                .where(AutoEngineTickRow.engine_id == engine_id)
            )
            or 0
        )
    except Exception:  # noqa: BLE001 — telemetría opcional: el hueco se declara, no se finge.
        logger.warning("auto monitor: tick count unavailable", exc_info=True)

    projections = await position_store.read_projection(account_id, engine_id)
    positions = {
        symbol: {
            "symbol": row.symbol,
            "quantity": str(row.quantity),
            "entryPrice": None if row.entry_price is None else str(row.entry_price),
            "highWatermark": None if row.high_watermark is None else str(row.high_watermark),
            "stopPrice": None if row.stop_price is None else str(row.stop_price),
            "t1State": row.t1_state,
            "trailingState": row.trailing_state,
            "positionState": dict(row.position_state) if row.position_state else None,
        }
        for symbol, row in projections.items()
    }

    journal: list[Any] = []
    reconciliation_entries: list[Any] = []
    claim_entries: list[Any] = []
    decision_ids = [d for d in (cycle_decision_id(cid) for cid in cycle_ids) if d]
    if decision_ids:
        try:
            journal = await repository.list_by_decision_ids(decision_ids)
        except Exception:  # noqa: BLE001
            logger.warning("auto monitor: decision journal unavailable", exc_info=True)
    try:
        reconciliation_entries, _ = await repository.list_entries(
            account_id=account_id,
            event_type=AUTO_RESERVATION_RECONCILIATION_EVENT,
            limit=max(limit * 10, 100),
        )
        claim_entries, _ = await repository.list_entries(
            account_id=account_id,
            event_type=AUTO_RESERVATION_CLAIM_EVENT,
            limit=max(limit * 10, 100),
        )
    except Exception:  # noqa: BLE001
        logger.warning("auto monitor: audit journal unavailable", exc_info=True)

    return build_operational_monitor(
        account_id=account_id,
        engine=engine,
        engine_ticks=engine_ticks,
        positions=positions,
        reservations=reservations,
        exit_orders=exit_orders,
        fills=fills,
        journal=journal,
        reconciliation_entries=reconciliation_entries,
        claim_entries=claim_entries,
        granularity=granularity_view_from_env(),
        interval_seconds=interval_seconds,
        grace_seconds=grace_seconds,
        real_price_enabled=real_price_enabled_from_env(),
        cycle_id=cycle_id,
        limit=limit,
    )


def granularity_view_from_env() -> dict[str, Any]:
    """Vista de granularidad DECLARADA vs HABILITADA (el header debe poder decir la diferencia).

    Nunca degrada en silencio: si la granularidad del entorno no está habilitada, se declara
    igualmente y el gate del motor es quien la rechaza al arrancar.
    """
    try:
        from bolsa_domain.operative_granularity import (
            DAILY_GRANULARITY,
            ExecutionTiming,
        )

        granularity = DAILY_GRANULARITY
        enabled = granularity.is_supported()
        return {
            "decision": granularity.decision.timeframe,
            "execution": granularity.execution.timing.value,
            "executionDeclared": ExecutionTiming.NEXT_BAR_OPEN.value,
            "executionEnabled": (
                granularity.execution.timing == ExecutionTiming.NEXT_BAR_OPEN and enabled
            ),
            "protection": granularity.protection.model.value,
            "evidence": granularity.evidence.unit.value,
        }
    except Exception:  # noqa: BLE001 — sin granularidad resoluble el hueco se declara.
        logger.warning("auto monitor: granularity unavailable", exc_info=True)
        return {}


def real_price_enabled_from_env() -> bool:
    """``AUTO_ENGINE_SIM_REAL_PRICE`` (default OFF): el header declara si el precio es real."""
    import os

    return (os.getenv("AUTO_ENGINE_SIM_REAL_PRICE") or "").strip() not in {"", "0", "false", "False"}
