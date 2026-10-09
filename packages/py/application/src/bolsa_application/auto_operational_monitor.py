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
    coerce_measurement,
)
from bolsa_application.auto_cycle_journal import cycle_decision_id
from bolsa_application.auto_self_evaluation_feed import cycles_from_fills

__all__ = [
    "AUTO_CYCLE_SETTLEMENT_EVENT",
    "AUTO_ENTRY_DECISION_EVENT",
    "AUTO_ENTRY_ORDER_EVENT",
    "AUTO_PROTECTION_EVENT",
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
#: v2.88.25 — la ORDEN DE ENTRADA emitida y materializada (hasta hoy sólo ``exitOrders`` era
#: durable). Cierra ``entry_order_not_durable`` del paso ``ORDER``.
AUTO_ENTRY_ORDER_EVENT = "auto_entry_order"
#: v2.88.25 — el HECHO durable del ciclo cerrado (liquidación real), distinto del ``CYCLE_CLOSED``
#: reconstruido de fills. Cierra ``settlement_not_durable`` del paso ``SETTLEMENT``.
AUTO_CYCLE_SETTLEMENT_EVENT = "auto_cycle_settlement"
#: v2.88.26 — el HECHO durable de una transición de PROTECCIÓN (ratchet, T1/T2, armado de
#: trailing, salida pedida). Cierra ``protection_not_durable`` del paso ``PROTECTION``: sin este
#: evento el paso se declara ``unknown`` (jamás ``reached`` desde la proyección).
AUTO_PROTECTION_EVENT = "auto_protection_event"

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


def _fact(
    key: str, value: Any, measurement: MeasurementStatus | None = None
) -> dict[str, Any]:
    """Hecho con su medición. Un hecho SIN valor NO se declara medido.

    ``measurement`` ausente (``None``) significa "deduce la medición del valor": con valor ⇒
    ``COMPLETE``; sin valor (``None``) ⇒ ``UNKNOWN``, para que la UI nunca rotule ``MEDIDO`` un
    hecho ausente (regla de la casa: ``NO HAY EVIDENCIA → UNKNOWN``, jamás un valor silencioso).
    Un llamante que necesite forzar la medición la pasa explícita.
    """
    resolved = measurement
    if resolved is None:
        resolved = MEASUREMENT_COMPLETE if value is not None else MEASUREMENT_UNKNOWN
    return {"key": key, "value": value, "measurement": resolved}


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


def _net_open_qty(fills: Sequence[Any]) -> tuple[float, int]:
    """Cantidad neta viva del ciclo (compras − ventas) y nº de fills con ``side`` NO clasificable.

    Un ``side`` ausente o ilegible NO se descarta en silencio (eso torcería el neto y podría
    declarar un ciclo cerrado que no lo está): se cuenta aparte y el llamante declara el hueco.
    ``> 0`` ⇒ el ciclo sigue abierto.
    """
    total = 0.0
    unclassified = 0
    for fill in fills:
        qty = float(_get(fill, "quantity") or 0.0)
        side = str(_get(fill, "side") or "").strip().lower()
        if side == "buy":
            total += qty
        elif side == "sell":
            total -= qty
        else:
            unclassified += 1
    return total, unclassified


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


def _price_sources(fills: Sequence[Any]) -> tuple[dict[str, int] | None, MeasurementStatus]:
    """v2.88.25 — FUENTES de precio realmente usadas por los fills del ciclo, contadas.

    Es el hecho que sustituye a leer ``realPriceEnabled`` (configuración) como si fuera el
    precio de la operación: ``{"MARKET_CLOSE": 2}`` dice que AMBAS patas se construyeron con
    precio real de barra. Un fill sin fuente declarada NO se descarta en silencio: degrada el
    agregado a ``PARTIAL`` (medido a medias), y sin ninguna fuente el valor es ``None`` con
    ``UNKNOWN`` — nunca un ``{}`` que afirmaría "ninguna fuente", que no es lo mismo.
    """
    counts: dict[str, int] = {}
    unmeasured = 0
    for fill in fills:
        raw = _get(fill, "price_source", "priceSource")
        kind = str(raw).strip() if raw is not None else ""
        if kind:
            counts[kind] = counts.get(kind, 0) + 1
        else:
            unmeasured += 1
    if not counts:
        return None, MEASUREMENT_COMPLETE if unmeasured == 0 else MEASUREMENT_UNKNOWN
    return counts, MEASUREMENT_COMPLETE if unmeasured == 0 else MEASUREMENT_PARTIAL


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
        # El envoltorio de riesgo de la decisión vive DURABLE y ANIDADO en la propia
        # entrada: la asignación del sizing en ``payload.risk`` (``quantity``/
        # ``riskAmount``/``riskPct``) y la entrada y el stop estructural en
        # ``payload.tradePlan``. Se lee de ahí y no de claves planas que el productor
        # nunca selló — que era justo por lo que ``RISK`` no era demostrable.
        allocation = payload.get("risk")
        if isinstance(allocation, Mapping):
            for key in ("quantity", "riskAmount", "riskPct"):
                if allocation.get(key) is not None:
                    facts.append(_fact(key, allocation.get(key)))
        plan = payload.get("tradePlan")
        if isinstance(plan, Mapping):
            if plan.get("entry") is not None:
                facts.append(_fact("entry", plan.get("entry")))
            if plan.get("structuralStop") is not None:
                facts.append(_fact("stop", plan.get("structuralStop")))
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


def _order_step(orders: Sequence[Any], journal: Sequence[Any] = ()) -> dict[str, Any]:
    """``ORDER`` — INTENT de salida durable **y** orden de ENTRADA durable (v2.88.25).

    Hasta v2.88.25 la orden de entrada no era durable y el paso sólo podía leer las salidas
    (``auto_exit_orders``), quedando ``entry_order_not_durable``. Ahora el evento
    ``auto_entry_order`` del spine aporta el hecho de entrada (pedido vs materializado +
    fuente de precio); si hay salida durable pero ninguna entrada, el hueco se declara en la
    nota en vez de esconderse.
    """
    entry_orders = [
        entry
        for entry in journal
        if _get(entry, "event_type", "eventType") == AUTO_ENTRY_ORDER_EVENT
    ]
    if not orders and not entry_orders:
        return _step(
            "ORDER",
            state=STEP_UNKNOWN,
            measurement=MEASUREMENT_UNKNOWN,
            note="entry_order_not_durable",
        )
    facts: list[dict[str, Any]] = []
    for entry in entry_orders:
        payload = _entry_payload(entry)
        facts.append(
            _fact(
                "entryOrder",
                {
                    "orderId": payload.get("orderId"),
                    "requestedQty": payload.get("requestedQty"),
                    "appliedQty": payload.get("appliedQty"),
                    "partial": payload.get("partial"),
                    "priceSource": payload.get("priceSource"),
                },
            )
        )
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
    moments = [
        _parse_instant(_get(row, "created_at", "createdAt"))
        for row in (*entry_orders, *orders)
    ]
    valid = [moment for moment in moments if moment is not None]
    # Salida durable sin hecho de entrada: el hueco se declara, no se oculta.
    note = "entry_order_not_durable" if orders and not entry_orders else None
    return _step(
        "ORDER",
        state=STEP_REACHED,
        at=_iso(max(valid)) if valid else None,
        facts=facts,
        note=note,
    )


def _fill_step(fills: Sequence[Any], *, window_full: bool = False) -> dict[str, Any]:
    """``FILL`` — VWAPs y fricción del ciclo, declarando los huecos de la ventana y del ``side``.

    ``window_full`` es el suelo declarado de la lectura (``len == limit``): con la ventana llena
    el conjunto de fills pudo truncarse y el paso se declara ``PARTIAL``. Un fill con ``side``
    no clasificable TAMPOCO se descarta en silencio: no entra en ``buyQty``/``sellQty`` y por eso
    el paso se declara ``PARTIAL`` con la nota ``fill_side_undeclared``.
    """
    if not fills:
        return _step("FILL", state=STEP_PENDING, measurement=MEASUREMENT_UNKNOWN, note="no_fills")
    buys = [f for f in fills if str(_get(f, "side") or "").lower() == "buy"]
    sells = [f for f in fills if str(_get(f, "side") or "").lower() == "sell"]
    unclassified = [
        f for f in fills if str(_get(f, "side") or "").strip().lower() not in {"buy", "sell"}
    ]

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
    price_sources, price_sources_measurement = _price_sources(fills)
    # Los buckets de lado son incompletos si algún fill no declara un lado clasificable.
    bucket_measurement: MeasurementStatus = (
        MEASUREMENT_PARTIAL if unclassified else MEASUREMENT_COMPLETE
    )
    facts = [
        _fact("buyQty", round(buy_qty, 6), bucket_measurement),
        _fact(
            "buyVwap",
            buy_vwap,
            MEASUREMENT_UNKNOWN if buy_vwap is None else bucket_measurement,
        ),
        _fact("sellQty", round(sell_qty, 6), bucket_measurement),
        _fact(
            "sellVwap",
            sell_vwap,
            MEASUREMENT_UNKNOWN if sell_vwap is None else bucket_measurement,
        ),
        _fact("appliedFriction", friction, friction_measurement),
        _fact("priceSources", price_sources, price_sources_measurement),
    ]
    at = _iso(_parse_instant(_get(fills[-1], "created_at", "createdAt")))
    notes: list[str] = []
    if unclassified:
        notes.append("fill_side_undeclared")
    if window_full:
        notes.append("fill_window_truncated")
    return _step(
        "FILL",
        state=STEP_REACHED,
        at=at,
        measurement=MEASUREMENT_PARTIAL if notes else MEASUREMENT_COMPLETE,
        facts=facts,
        note=", ".join(notes) or None,
    )


def _protection_projection_facts(
    position: Mapping[str, Any] | None,
    *,
    measurement: MeasurementStatus | None,
) -> list[dict[str, Any]]:
    """Facts proyectados del ``PositionState`` vivo (autoridad del estado ACTUAL).

    Con un hecho durable se exponen con su medición natural (``None`` ⇒ ``_fact`` la deduce
    del valor). Sin hecho durable NO son evidencia de que la transición ocurriera, así que se
    fuerzan ``UNKNOWN``: la UI no puede rotular ``MEDIDO`` una proyección sin traza.
    """
    if position is None:
        return []
    state_map = position.get("positionState") or {}
    active_map = state_map if isinstance(state_map, Mapping) else {}
    mfe_mae = active_map.get("mfeMae")
    return [
        _fact("stopPrice", position.get("stopPrice"), measurement),
        _fact("currentStop", active_map.get("currentStop"), measurement),
        _fact("highWatermark", position.get("highWatermark"), measurement),
        _fact("t1State", position.get("t1State"), measurement),
        _fact("trailingState", position.get("trailingState"), measurement),
        _fact("protectionState", active_map.get("protectionState"), measurement),
        _fact("lifecycleState", active_map.get("lifecycleState"), measurement),
        _fact("mfeMae", mfe_mae, measurement),
    ]


def _protection_step(
    position: Mapping[str, Any] | None,
    protection: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """``PROTECTION`` — SOLO desde un hecho durable explícito de protección.

    Regla dura de esta versión (simétrica a ``SETTLEMENT``): la proyección
    (``sim_auto_positions.position_state``) describe el estado **actual**, pero **no** demuestra
    que una transición de protección haya ocurrido. Sin un hecho durable
    (``auto_protection_event``) el paso se declara ``unknown`` con ``protection_not_durable``
    — **jamás** ``reached`` desde la proyección — y los facts proyectados viajan ``UNKNOWN``.

    Con el hecho durable, el paso se enciende (``reached``) y expone la transición sellada
    (``kind``, ``stopBefore``/``stopAfter``, ``target``, ``lifecycleFrom``→``lifecycleTo``)
    junto con la proyección viva. Si el último ``kind`` es una salida pedida
    (``EXIT_REQUESTED``/``PROTECT_REQUESTED``) se declara que aún no hay materialización.
    """
    if protection is None:
        return _step(
            "PROTECTION",
            state=STEP_UNKNOWN,
            measurement=MEASUREMENT_UNKNOWN,
            note="protection_not_durable",
            facts=_protection_projection_facts(position, measurement=MEASUREMENT_UNKNOWN),
        )
    kind = protection.get("kind")
    facts: list[dict[str, Any]] = [
        _fact("protectionKind", kind),
        _fact("lifecycleFrom", protection.get("lifecycleFrom")),
        _fact("lifecycleTo", protection.get("lifecycleTo")),
        _fact("stopBefore", protection.get("stopBefore")),
        _fact("stopAfter", protection.get("stopAfter")),
        _fact("target", protection.get("target")),
        _fact("trailingStatus", protection.get("trailingStatus")),
        _fact("revisionId", protection.get("revisionId")),
        _fact("source", protection.get("source")),
        *_protection_projection_facts(position, measurement=None),
    ]
    kind_text = str(kind or "").strip().upper()
    note = (
        "protection_exit_requested_without_materialization"
        if kind_text in {"EXIT_REQUESTED", "PROTECT_REQUESTED"}
        else None
    )
    return _step(
        "PROTECTION",
        state=STEP_REACHED,
        at=protection.get("at"),
        facts=facts,
        note=note,
    )


def _settlement_step(
    settlement: Mapping[str, Any] | None,
    fills: Sequence[Any],
    *,
    duplicate: bool = False,
) -> dict[str, Any]:
    """``SETTLEMENT`` — SOLO desde un hecho durable explícito de liquidación.

    Regla dura de esta versión: un ciclo cerrado (``cycles_from_fills``) **no** demuestra que
    haya ocurrido un settlement durable. Tener ``fill + PnL + ciclo cerrado`` no es evidencia de
    liquidación, así que sin un evento/estado durable de settlement el paso se declara
    ``unknown`` con ``settlement_not_durable`` — **jamás** ``reached``. El PnL se lee en
    ``CYCLE_CLOSED``.

    v2.88.25: el hecho durable lo produce el worker al cerrar la posición
    (``auto_cycle_settlement``). El PnL viaja con su MEDICIÓN (``pnlMeasurement``): una cifra
    marcada ``PARTIAL`` (evidencia truncada) no se publica como afirmada.
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
    pnl_measurement = coerce_measurement(settlement.get("pnlMeasurement"))
    for key in ("settlementId", "closedQty", "exitReason", "priceSource", "settledAt"):
        if settlement.get(key) is not None:
            facts.append(_fact(key, settlement.get(key)))
    # El PnL viaja con SU medición declarada por el productor (no se deduce del valor).
    facts.append(
        _fact(
            "pnl",
            settlement.get("pnl"),
            pnl_measurement
            if settlement.get("pnl") is None
            else (pnl_measurement or MEASUREMENT_COMPLETE),
        )
    )
    if duplicate:
        # DOS settlements del mismo ciclo: cuál es la liquidación autoritativa no se puede
        # afirmar. Se conserva uno de forma determinista y el hecho se declara CONTRADICHO
        # (``PARTIAL`` + nota), nunca se pisa en silencio — el mismo criterio que la
        # conciliación de evidencia PAPER-2.1.
        return _step(
            "SETTLEMENT",
            state=STEP_REACHED,
            at=settlement.get("settledAt"),
            measurement=MEASUREMENT_PARTIAL,
            facts=facts,
            note="duplicate_settlement_cycle",
        )
    return _step(
        "SETTLEMENT",
        state=STEP_REACHED,
        at=settlement.get("settledAt"),
        facts=facts,
    )


def _cycle_closed_step(
    closed: Mapping[str, Any] | None, *, window_truncated: bool = False
) -> dict[str, Any]:
    """``CYCLE_CLOSED`` — cierre reconstruido de los fills, DECLARADO si la ventana se truncó.

    Con la ventana de fills truncada el conjunto pudo perder una pata y ``cycles_from_fills``
    puede reconstruir un cierre que la evidencia completa desmintiera: el paso **no** se afirma
    (``unknown``/``PARTIAL`` con nota), por coherencia con ``FILL``. Sin truncamiento se comporta
    como antes.
    """
    if closed is None:
        return _step("CYCLE_CLOSED", state=STEP_PENDING, measurement=MEASUREMENT_UNKNOWN)
    if window_truncated:
        return _step(
            "CYCLE_CLOSED",
            state=STEP_UNKNOWN,
            measurement=MEASUREMENT_PARTIAL,
            note="cycle_closed_window_truncated",
        )
    return _step(
        "CYCLE_CLOSED",
        state=STEP_REACHED,
        at=closed.get("closedAt"),
        facts=[_fact("pnl", closed.get("pnl")), _fact("reason", closed.get("reason", "flat"))],
    )


def _cycle_window_truncated(
    cycle_id: str,
    *,
    fills_by_cycle: Mapping[str, Sequence[Any]],
    fills_total_by_cycle: Mapping[str, int] | None,
    fills_window_full: bool,
) -> bool:
    """Si la ventana de fills de ESTE ciclo pudo truncarse.

    Con el agregado ``fills_total_by_cycle`` (``count_by_cycle_ids``) la completitud se decide
    ciclo a ciclo: ``cargados < total conocido`` ⇒ truncada (y un ciclo sin filas no aparece en
    el mapa, así que no se marca). Sin agregado disponible (``None``, lectura caída) se cae al
    suelo GLOBAL declarado por el llamante (``fills_window_full``): la ventana pudo truncarse
    para todos, y no se puede afirmar lo contrario.
    """
    if fills_total_by_cycle is not None:
        expected = int(fills_total_by_cycle.get(cycle_id, 0))
        return len(fills_by_cycle.get(cycle_id, ())) < expected
    return fills_window_full


def _protection_is_newer(candidate: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    """(PURA) si ``candidate`` es un hecho de protección más reciente que ``current``.

    Un ciclo puede tener VARIAS transiciones de protección; el paso expone la ÚLTIMA. Se
    compara por instante declarado (``at``/``created_at``) y, si no es parseable, se conserva
    lo ya visto (fail-closed: no se inventa un orden que no consta).
    """
    candidate_at = _parse_instant(_get(candidate, "at", "created_at", "createdAt"))
    if candidate_at is None:
        return False
    current_at = _parse_instant(_get(current, "at", "created_at", "createdAt"))
    if current_at is None:
        return True
    return candidate_at >= current_at


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
    protection_by_cycle: Mapping[str, Mapping[str, Any]] | None = None,
    window_truncated: bool = False,
    duplicate_settlement: bool = False,
) -> dict[str, Any]:
    reservation = reservations[0] if reservations else None
    cycle_journal = _journal_for_cycle(journal, cycle_id)
    cycle_fills = list(fills_by_cycle.get(cycle_id, ()))
    orders = list(orders_by_cycle.get(cycle_id, ()))
    closed = closed_by_cycle.get(cycle_id)
    settlement = (settlement_by_cycle or {}).get(cycle_id)
    protection = (protection_by_cycle or {}).get(cycle_id)
    net, unclassified_fills = _net_open_qty(cycle_fills)
    is_open = net > 1e-9
    side = str(_get(reservation, "side") or "").strip().lower() if reservation else ""

    steps = [
        _entry_decision_step("SIGNAL", cycle_journal, note_absent="signal_not_durable"),
        _entry_decision_step("TOP_N", cycle_journal, note_absent="top_n_not_durable"),
        _entry_decision_step("RISK", cycle_journal, note_absent="risk_not_durable"),
        _reservation_step(reservation),
        _order_step(orders, cycle_journal),
        _fill_step(cycle_fills, window_full=window_truncated),
        _protection_step(positions_by_cycle.get(cycle_id), protection),
        _settlement_step(settlement, cycle_fills, duplicate=duplicate_settlement),
        _cycle_closed_step(closed, window_truncated=window_truncated),
    ]
    notes: list[str] = []
    for step in steps:
        if step["state"] == STEP_UNKNOWN and step["note"]:
            notes.append(step["note"])
    if duplicate_settlement:
        # Se declara en el resumen del ciclo (no sólo en el paso): un settlement duplicado
        # es una CONTRADICCIÓN de la identidad del ciclo, no un detalle del paso.
        notes.append("duplicate_settlement_cycle")
    # ``closed`` deja de ser un booleano ciego: con la ventana truncada o un ``side`` no
    # clasificable no se puede AFIRMAR el cierre (el neto puede estar incompleto), así que
    # viaja ``None`` + ``PARTIAL``. Con la ventana completa se afirma True/False sin ambigüedad.
    if window_truncated or unclassified_fills > 0:
        closed_value: bool | None = None
        closed_measurement: MeasurementStatus = MEASUREMENT_PARTIAL
    else:
        closed_value = closed is not None and not is_open
        closed_measurement = MEASUREMENT_COMPLETE
    return {
        "cycleId": cycle_id,
        "instrumentId": _get(reservation, "instrument_id", "instrumentId"),
        "strategyVersion": _get(reservation, "strategy_version_id", "strategyVersionId"),
        "direction": "short" if side == "sell" else "long",
        "closed": closed_value,
        "closedMeasurement": closed_measurement,
        "steps": steps,
        # El PnL reconstruido sale de la ventana de fills: truncada, un suelo no es un
        # resultado. Se declara ausente antes que publicar una cifra sobre evidencia parcial.
        # La condición NO repite sólo ``window_truncated``: un ``side`` no clasificable también
        # degrada el cierre a ``PARTIAL`` (arriba), así que ``result`` se rige por la MISMA
        # medición ya calculada (``closed_measurement``) y deja de publicar una cifra de dinero
        # cuando el cierre no se puede afirmar.
        "result": (
            None
            if closed is None or closed_measurement != MEASUREMENT_COMPLETE
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
                # Medición DECLARADA de cada campo (la calcula ``build_reservation_reconciliation_entry``):
                # sin ella la UI no puede distinguir un valor NO MEDIDO de un valor vacío/`0`.
                # Si el payload no la trae se declara UNKNOWN, nunca se asume COMPLETE.
                "reasonMeasurement": payload.get("reasonMeasurement") or MEASUREMENT_UNKNOWN,
                "callerMeasurement": payload.get("callerMeasurement") or MEASUREMENT_UNKNOWN,
                "agedMeasurement": payload.get("agedMeasurement") or MEASUREMENT_UNKNOWN,
                "graceWindowMeasurement": (
                    payload.get("graceWindowMeasurement") or MEASUREMENT_UNKNOWN
                ),
                "reconciliationMeasurement": (
                    payload.get("reconciliationMeasurement") or MEASUREMENT_UNKNOWN
                ),
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
    # ``activity`` es la fase operacional REAL del último tick (telemetría). Se expone con su
    # medición: un valor presente es ``COMPLETE``; su ausencia (fila anterior al sello o motor
    # que no la emite) es ``UNKNOWN`` y la UI la declara «Sin dato todavía», nunca una fase.
    activity = _get(engine, "activity") if engine else None
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
        "currentActivity": activity,
        "currentActivityMeasurement": (
            MEASUREMENT_COMPLETE if activity is not None else MEASUREMENT_UNKNOWN
        ),
        "currentActivityAt": _iso(last_tick) if activity is not None else None,
        "currentActivityAtMeasurement": (
            MEASUREMENT_COMPLETE
            if (activity is not None and last_tick is not None)
            else MEASUREMENT_UNKNOWN
        ),
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
    counts: Mapping[str, Any] | None = None,
    claims_total: int | None = None,
    reconciliations_total: int | None = None,
    forced_releases_total: int | None = None,
    reservations_window_full: bool = False,
) -> dict[str, Any]:
    # Se DECLARAN por separado: ``claimAttempts`` (todo intento auditado), ``successfulClaims``
    # (``claimed=True``), ``lostClaims`` (``claimed=False``) y ``raceConflicts`` (conflicto de
    # carrera DECLARADO por el productor). ``claimed=False`` NO equivale a carrera: puede ser
    # invalid/expired/already_released/wrong_state; por eso la carrera se lee de
    # ``payload.conflict`` y no se infiere del claim perdido.
    #
    # Los contadores salen del AGREGADO en base (``counts``) cuando está disponible: así no
    # dependen del ``limit`` de lectura y no se declaran ``COMPLETE`` estando truncados. Sin
    # agregado se cae a las filas cargadas y se marca ``PARTIAL`` cuando el total conocido
    # demuestra que la ventana se truncó. Un hueco se declara ``UNKNOWN``, nunca un ``0``.
    if counts is not None:
        # El agregado en base SE EJECUTÓ: un ``0`` es evidencia de "cero eventos", no un hueco.
        # Distinguir "consulta no disponible" (``counts is None``) de "consulta disponible y
        # COUNT(*) = 0" es justo lo que evita declarar UNKNOWN una medición que sí se hizo.
        claim_attempts: int | None = int(counts.get("claimAttempts") or 0)
        successful_claims: int | None = int(counts.get("successfulClaims") or 0)
        lost_claims_count: int | None = int(counts.get("lostClaims") or 0)
        race_conflicts: int | None = int(counts.get("raceConflicts") or 0)
        undeclared_conflicts: int = int(counts.get("lostClaimsUndeclaredConflict") or 0)
        reconciliations_count: int | None = int(counts.get("reconciliations") or 0)
        grace_keeps: int | None = int(counts.get("graceWindowKeeps") or 0)
        claims_measured = True
        reconciliations_measured = True
        # El desglose por estado sale del universo completo (agregado): es COMPLETE. Solo la
        # carrera se degrada a PARTIAL si hay claims perdidos sin ``conflict`` declarado.
        claim_breakdown_measurement: MeasurementStatus = MEASUREMENT_COMPLETE
        race_conflicts_measurement: MeasurementStatus = (
            MEASUREMENT_PARTIAL if undeclared_conflicts > 0 else MEASUREMENT_COMPLETE
        )
        reconciliation_breakdown_measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    else:
        claim_attempts = (
            claims_total if claims_total is not None else (len(claims) if claims else None)
        )
        # Con el total del universo conocido (aunque sea ``0``) los subcontadores se pueden
        # AFIRMAR si la página trae todo el universo; si no, viajan como SUELO con ``PARTIAL``.
        # Un total ``0`` es una medición completa de "cero claims", no un hueco.
        if claim_attempts == 0:
            successful_claims = 0
            lost_claims_count = 0
            race_conflicts = 0
        else:
            successful_claims = (
                sum(1 for entry in claims if _entry_payload(entry).get("claimed") is True)
                if claims
                else None
            )
            lost_claims_count = (
                sum(1 for entry in claims if _entry_payload(entry).get("claimed") is False)
                if claims
                else None
            )
            race_conflicts = (
                sum(1 for entry in claims if _entry_payload(entry).get("conflict") is True)
                if claims
                else None
            )
        reconciliations_count = (
            reconciliations_total
            if reconciliations_total is not None
            else (len(reconcilations) if reconcilations else None)
        )
        if reconciliations_count == 0:
            grace_keeps = 0
        else:
            grace_keeps = (
                sum(
                    1
                    for entry in reconcilations
                    if _entry_payload(entry).get("reason") == GRACE_WINDOW_KEEP
                )
                if reconcilations
                else None
            )
        claims_measured = claim_attempts is not None
        reconciliations_measured = reconciliations_count is not None
        claim_breakdown_measurement = (
            MEASUREMENT_PARTIAL
            if claim_attempts is not None and len(claims) < claim_attempts
            else (MEASUREMENT_COMPLETE if claims_measured else MEASUREMENT_UNKNOWN)
        )
        reconciliation_breakdown_measurement = (
            MEASUREMENT_PARTIAL
            if reconciliations_count is not None and len(reconcilations) < reconciliations_count
            else (MEASUREMENT_COMPLETE if reconciliations_measured else MEASUREMENT_UNKNOWN)
        )
        # Paridad con el agregado: un claim perdido con ``conflict`` NO declarado degrada la
        # carrera a ``PARTIAL`` (aunque la ventana no contenga la carrera, el hueco se declara).
        undeclared_conflicts = (
            sum(
                1
                for entry in claims
                if _entry_payload(entry).get("claimed") is False
                and _entry_payload(entry).get("conflict") is None
            )
            if claims
            else 0
        )
        race_conflicts_measurement = (
            MEASUREMENT_PARTIAL
            if claims_measured and undeclared_conflicts > 0
            else claim_breakdown_measurement
        )

    claim_measurement: MeasurementStatus = (
        MEASUREMENT_COMPLETE if claims_measured else MEASUREMENT_UNKNOWN
    )
    reconciliation_measurement: MeasurementStatus = (
        MEASUREMENT_COMPLETE if reconciliations_measured else MEASUREMENT_UNKNOWN
    )
    # La ventana de filas de claims está truncada si el total conocido supera las filas cargadas.
    claim_window_truncated = claim_attempts is not None and len(claims) < claim_attempts
    # ``forcedReleases`` sale del AGREGADO en base cuando está disponible (universo completo,
    # sin depender de la ventana de reservas). Sin agregado se cuenta la ventana y se declara
    # ``PARTIAL`` si la ventana está LLENA (``len == limit`` ⇒ pudo truncarse): el mismo criterio
    # que los claims, porque la ventana de reservas también está limitada.
    if forced_releases_total is not None:
        forced_releases: int | None = forced_releases_total
        forced_releases_measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    else:
        forced_releases = sum(
            1
            for row in reservations
            if str(_get(row, "release_reason", "releaseReason") or "") in _FORCED_RELEASE_REASONS
        )
        forced_releases_measurement = (
            MEASUREMENT_PARTIAL if reservations_window_full else MEASUREMENT_COMPLETE
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
    # Último conflicto: la carrera de claim DECLARADA (``conflict is True``) más reciente. Un
    # claim perdido sin ``conflict`` declarado NO es una carrera y no entra aquí. Si la ventana
    # de filas está truncada el valor se declara ``PARTIAL``: no puede afirmarse como el ÚLTIMO.
    declared_conflicts = [
        entry for entry in claims if _entry_payload(entry).get("conflict") is True
    ]
    if declared_conflicts:
        latest = max(
            declared_conflicts, key=lambda e: str(_get(e, "created_at", "createdAt") or "")
        )
        latest_payload = _entry_payload(latest)
        last_conflict: dict[str, Any] | None = {
            "at": _iso(_parse_instant(_get(latest, "created_at", "createdAt"))),
            "reservationId": latest_payload.get(
                "reservation_id", latest_payload.get("reservationId")
            ),
            "loserSession": latest_payload.get("caller"),
        }
        last_conflict_measurement: MeasurementStatus = (
            MEASUREMENT_PARTIAL if claim_window_truncated else MEASUREMENT_COMPLETE
        )
    else:
        last_conflict = None
        if claim_window_truncated:
            last_conflict_measurement = MEASUREMENT_PARTIAL
        elif claims_measured:
            last_conflict_measurement = MEASUREMENT_COMPLETE
        else:
            last_conflict_measurement = MEASUREMENT_UNKNOWN
    return {
        "activeSessions": active_sessions,
        "activeSessionsMeasurement": (
            MEASUREMENT_PARTIAL if active_sessions is not None else MEASUREMENT_UNKNOWN
        ),
        "heartbeatsPersisted": engine_ticks,
        "claimAttempts": claim_attempts,
        "claimAttemptsMeasurement": claim_measurement,
        "successfulClaims": successful_claims,
        "successfulClaimsMeasurement": claim_breakdown_measurement,
        "lostClaims": lost_claims_count,
        "lostClaimsMeasurement": claim_breakdown_measurement,
        "raceConflicts": race_conflicts,
        "raceConflictsMeasurement": race_conflicts_measurement,
        "reconciliations": reconciliations_count,
        "reconciliationsMeasurement": reconciliation_measurement,
        "graceWindowKeeps": grace_keeps,
        "graceWindowKeepsMeasurement": reconciliation_breakdown_measurement,
        "forcedReleases": forced_releases,
        "forcedReleasesMeasurement": forced_releases_measurement,
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
    protection_events: Sequence[Any] = (),
    granularity: Mapping[str, Any] | None = None,
    interval_seconds: float | None = None,
    grace_seconds: float | None = None,
    real_price_enabled: bool = False,
    cycle_id: str | None = None,
    limit: int = 20,
    as_of: str | None = None,
    concurrency_counts: Mapping[str, Any] | None = None,
    claims_total: int | None = None,
    reconciliations_total: int | None = None,
    forced_releases_total: int | None = None,
    header_decision_entries: Sequence[Any] | None = None,
    fills_window_full: bool = False,
    fills_total_by_cycle: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """(PURA) construye el DTO del monitor desde el estado durable ya leído. Sin I/O.

    No sintetiza pasos: cada etapa viene de un hecho durable concreto y lo que no existe se
    declara ``unknown``/``absent`` con su nota. Un ``cycle_id`` filtra a un único ciclo (para el
    drill-down); sin él se devuelven los ciclos de la ventana (``limit``).

    ``header_decision_entries`` es la lectura GLOBAL del último ``auto_entry_decision`` durable
    (independiente de los ciclos/reservas visibles): sin ella, el header cae al ``journal`` del
    ciclo para no romper llamadas puras antiguas.
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
    # ``unknown``; nunca se deriva de ``CYCLE_CLOSED``. DOS settlements del mismo ciclo NO se
    # pisan en silencio: se conserva el PRIMERO de forma determinista y el ciclo se marca
    # contradictorio (``duplicate_settlement_cycle``), igual que la conciliación de PAPER-2.1.
    # El ``dedupe_key`` ya lo previene en escritura; esto cubre filas legacy o un productor
    # sin identidad determinista.
    settlement_by_cycle: dict[str, Mapping[str, Any]] = {}
    duplicate_settlement_cycles: set[str] = set()
    for row in settlements:
        key = _cycle_id_of(row)
        if not key or not isinstance(row, Mapping):
            continue
        if key in settlement_by_cycle:
            duplicate_settlement_cycles.add(key)
            continue
        settlement_by_cycle[key] = row

    # v2.88.26 — HECHOS durables de protección por ciclo. Un ciclo puede tener VARIAS
    # transiciones (nacimiento, ratchet, T1/T2, salida): el paso expone la ÚLTIMA, comparando
    # por instante declarado (nunca por el orden accidental de la lista).
    protection_by_cycle: dict[str, Mapping[str, Any]] = {}
    for row in protection_events:
        key = _cycle_id_of(row)
        if not key or not isinstance(row, Mapping):
            continue
        previous = protection_by_cycle.get(key)
        if previous is None or _protection_is_newer(row, previous):
            protection_by_cycle[key] = row

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
            protection_by_cycle=protection_by_cycle,
            window_truncated=_cycle_window_truncated(
                key,
                fills_by_cycle=fills_by_cycle,
                fills_total_by_cycle=fills_total_by_cycle,
                fills_window_full=fills_window_full,
            ),
            duplicate_settlement=key in duplicate_settlement_cycles,
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

    decision_entries = (
        journal if header_decision_entries is None else header_decision_entries
    )
    header = _header(
        engine,
        engine_ticks=engine_ticks,
        granularity=granularity_view,
        interval_seconds=interval_seconds,
        real_price_enabled=real_price_enabled,
        grace_seconds=grace_seconds,
        last_decision_at=_last_decision_instant(decision_entries),
        as_of=stamp,
    )
    concurrency = _concurrency(
        engine_ticks=engine_ticks,
        reservations=reservations,
        reconcilations=reconciliations,
        claims=list(claim_entries),
        journal=journal,
        counts=concurrency_counts,
        claims_total=claims_total,
        reconciliations_total=reconciliations_total,
        forced_releases_total=forced_releases_total,
        reservations_window_full=limit > 0 and len(reservations) >= limit,
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
    fills_window_full = False
    fills_total_by_cycle: Mapping[str, int] | None = None
    if cycle_ids:
        fill_limit = max(limit * 50, 200)
        fills = await context_store.list_by_cycle_ids(
            account_id, cycle_ids, limit=fill_limit
        )
        # ``len == limit`` ⇒ la ventana pudo truncarse: el suelo GLOBAL que se declara cuando
        # no hay agregado por ciclo. Con el agregado (abajo) la completitud se decide ciclo a
        # ciclo y una ventana global llena con ciclos cortos NO degrada a los que están completos.
        fills_window_full = len(fills) >= fill_limit
        # Completitud POR CICLO: cuántos fills existen de cada ciclo, sin cargarlos. Si falla,
        # se declara (queda ``None``) y el lector cae al suelo global. Nunca se finge un total.
        try:
            fills_total_by_cycle = await context_store.count_by_cycle_ids(
                account_id, cycle_ids
            )
        except Exception:  # noqa: BLE001
            logger.warning("auto monitor: fill per-cycle counts unavailable", exc_info=True)
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
    reconciliation_total: int | None = None
    claim_total: int | None = None
    decision_ids = [d for d in (cycle_decision_id(cid) for cid in cycle_ids) if d]
    if decision_ids:
        try:
            journal = await repository.list_by_decision_ids(decision_ids)
        except Exception:  # noqa: BLE001
            logger.warning("auto monitor: decision journal unavailable", exc_info=True)
    # v2.88.25 — HECHOS durables del ciclo que viajan en el spine y NO requieren query nueva:
    # la orden de entrada y la liquidación. El PnL del settlement se publica con su medición;
    # sin evento, el paso ``SETTLEMENT`` sigue declarando ``settlement_not_durable``.
    settlements: list[dict[str, Any]] = []
    # v2.88.26 — el HECHO durable de protección (``auto_protection_event``): un ciclo puede
    # tener VARIAS transiciones; el read model se queda con la más reciente por instante.
    protections: list[dict[str, Any]] = []
    for entry in journal:
        event_type = _get(entry, "event_type", "eventType")
        if event_type == AUTO_CYCLE_SETTLEMENT_EVENT:
            payload = _entry_payload(entry)
            if payload:
                settlements.append(dict(payload))
        elif event_type == AUTO_PROTECTION_EVENT:
            payload = _entry_payload(entry)
            if payload:
                protections.append(dict(payload))
    # Lectura GLOBAL del último ``auto_entry_decision`` durable, independiente de las reservas
    # visibles: por índice de ``event_type``, más nueva primero (``limit=1``). Sin esto
    # ``lastDecisionAt`` quedaba atado a los ciclos de la ventana y podía ocultar una decisión
    # real. Se acota por ``engine_id`` (A4): la "última decisión" es la de ESTE motor, no la de
    # otro motor de la misma cuenta. Si la consulta falla se deja ``None``: el header cae al
    # journal del ciclo.
    header_decision_entries: list[Any] | None = None
    try:
        header_decision_entries, _ = await repository.list_entries(
            account_id=account_id,
            event_type=AUTO_ENTRY_DECISION_EVENT,
            engine_id=engine_id,
            limit=1,
        )
    except Exception:  # noqa: BLE001
        logger.warning("auto monitor: latest decision unavailable", exc_info=True)
    try:
        reconciliation_entries, reconciliation_total = await repository.list_entries(
            account_id=account_id,
            event_type=AUTO_RESERVATION_RECONCILIATION_EVENT,
            limit=max(limit * 10, 100),
        )
    except Exception:  # noqa: BLE001
        logger.warning("auto monitor: reconciliation journal unavailable", exc_info=True)
    try:
        claim_entries, claim_total = await repository.list_entries(
            account_id=account_id,
            event_type=AUTO_RESERVATION_CLAIM_EVENT,
            limit=max(limit * 10, 100),
        )
    except Exception:  # noqa: BLE001
        logger.warning("auto monitor: claim journal unavailable", exc_info=True)

    # Contadores GLOBALES de concurrencia agregados en base: NO dependen del ``limit`` de lectura
    # (cargar las filas truncaba el universo y lo declaraba ``COMPLETE``). Si el agregado falla,
    # el monitor cae a las filas cargadas y marca ``PARTIAL`` cuando el total las supera.
    concurrency_counts: dict[str, Any] | None = None
    try:
        concurrency_counts = await repository.aggregate_auto_operational_audit(
            account_id=account_id,
            claim_event_type=AUTO_RESERVATION_CLAIM_EVENT,
            reconciliation_event_type=AUTO_RESERVATION_RECONCILIATION_EVENT,
            grace_window_reason=GRACE_WINDOW_KEEP,
        )
    except Exception:  # noqa: BLE001
        logger.warning("auto monitor: concurrency aggregate unavailable", exc_info=True)

    # ``forcedReleases`` también es agregado en base: la ventana de reservas está limitada y no
    # puede sostener un conteo global sin declararlo truncado.
    forced_releases_total: int | None = None
    try:
        forced_releases_total = await reservation_store.count_forced_releases(
            account_id, reasons=_FORCED_RELEASE_REASONS
        )
    except Exception:  # noqa: BLE001
        logger.warning("auto monitor: forced releases aggregate unavailable", exc_info=True)

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
        settlements=settlements,
        protection_events=protections,
        granularity=granularity_view_from_env(),
        interval_seconds=interval_seconds,
        grace_seconds=grace_seconds,
        real_price_enabled=real_price_enabled_from_env(),
        cycle_id=cycle_id,
        limit=limit,
        concurrency_counts=concurrency_counts,
        claims_total=claim_total,
        reconciliations_total=reconciliation_total,
        forced_releases_total=forced_releases_total,
        header_decision_entries=header_decision_entries,
        fills_window_full=fills_window_full,
        fills_total_by_cycle=fills_total_by_cycle,
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
