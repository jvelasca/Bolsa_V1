"""PositionState — autoridad post-entrada (ADR-032 F2 + F2.1).

Tesis ≠ plan ≠ permiso ≠ posición. Thin 5.x/8.x siguen advisory aparte;
este módulo **no** importa ni copia esos mappers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from bolsa_analytics.cognitive.position_lifecycle import (
    LIFECYCLE_STATE_KEY,
    LIFECYCLE_STATE_UNVERIFIED,
    PROTECTED_LIFECYCLE_STATES,
    PositionLifecycleState,
    coerce_lifecycle_state,
    lifecycle_state_is_consistent,
)
from bolsa_analytics.cognitive.position_revision import (
    PositionRevision,
    PositionRevisionOrigin,
    build_position_revision,
    revisions_from_raw,
    stop_or_status_changed,
)

PositionStatus = Literal["OPEN", "PARTIAL", "PROTECTED", "CLOSED"]
PositionExitStatus = Literal["none", "hint", "armed", "done"]
TradePlanDirection = Literal["long", "short", "none"]
TargetLegStatus = Literal["pending", "triggered", "executed", "failed"]

POSITION_STATE_KEY = "positionState"

#: V2.42 slice 2b (E1) — techo de mantenimiento CONGELADO en el nacimiento. Es la entrada
#: que el worker pasa como ``expires_at`` al plan de salida; sin él ``TIME_STOP`` es
#: inalcanzable (``expires_at=None``) y una posición de swing viviría indefinidamente.
HOLDING_DEADLINE_KEY = "holdingDeadlineAt"

#: V2.42 slice 2b (E3) — nivel de invalidación de la tesis congelado en el nacimiento.
INVALIDATION_PRICE_KEY = "invalidationPrice"

#: V2.47 — identidad del ciclo financiero (señal→…→PnL) congelada en el nacimiento. Viaja
#: dentro del JSONB ``position_state`` para que la posición/cierre hereden el ciclo.
CYCLE_ID_KEY = "cycleId"

_VALID_TARGET_LEG = frozenset({"pending", "triggered", "executed", "failed"})


@dataclass(frozen=True, slots=True)
class TargetLeg:
    """V1.52 — estado durable de T1/T2. mark >= T1 ≠ executed."""

    status: TargetLegStatus
    at: str | None = None
    event_id: str | None = None
    fill_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "at": self.at,
            "eventId": self.event_id,
            "fillId": self.fill_id,
        }


def _non_empty_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def target_leg_from_unknown(
    raw: object,
    *,
    price: float | None,
    achieved_at: str | None,
) -> TargetLeg | None:
    if isinstance(raw, dict):
        status = raw.get("status")
        if isinstance(status, str) and status in _VALID_TARGET_LEG:
            return TargetLeg(
                status=status,  # type: ignore[arg-type]
                at=_non_empty_str(raw.get("at")),
                event_id=_non_empty_str(raw.get("eventId")),
                fill_id=_non_empty_str(raw.get("fillId")),
            )
    achieved = _non_empty_str(achieved_at)
    if achieved:
        return TargetLeg(status="executed", at=achieved)
    if price is not None:
        return TargetLeg(status="pending")
    return None


def birth_target_leg(price: float | None) -> TargetLeg | None:
    if price is None:
        return None
    return TargetLeg(status="pending")


def _advance_target_leg(
    current: TargetLeg | None,
    next_status: TargetLegStatus,
    *,
    at: str,
    event_id: str | None = None,
    fill_id: str | None = None,
) -> TargetLeg | None:
    if current is None:
        return None
    if current.status == "executed":
        return current
    if next_status == "failed" and current.status == "pending":
        return current
    return TargetLeg(
        status=next_status,
        at=at,
        event_id=_non_empty_str(event_id) or current.event_id,
        fill_id=_non_empty_str(fill_id) or current.fill_id,
    )


def apply_target_leg(
    position: PositionState,
    *,
    which: Literal["t1", "t2"],
    status: TargetLegStatus,
    at: str | None = None,
    event_id: str | None = None,
    fill_id: str | None = None,
) -> PositionState:
    """V1.52 — pending→triggered→executed|failed. executed es terminal."""
    when = _now_iso(at)
    if which == "t1":
        return replace(
            position,
            target1_leg=_advance_target_leg(
                position.target1_leg,
                status,
                at=when,
                event_id=event_id,
                fill_id=fill_id,
            ),
            updated_at=when,
        )
    return replace(
        position,
        target2_leg=_advance_target_leg(
            position.target2_leg,
            status,
            at=when,
            event_id=event_id,
            fill_id=fill_id,
        ),
        updated_at=when,
    )


def _finite_positive(value: object) -> float | None:
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def _finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


def _is_audited_override(override: object | None) -> bool:
    """H2: reason no vacío. No persiste."""
    if not isinstance(override, dict):
        return False
    reason = override.get("reason")
    return isinstance(reason, str) and bool(reason.strip())


def _stop_worsens(
    direction: TradePlanDirection, current: float | None, nxt: float
) -> bool:
    return does_stop_worsen(direction, current, nxt)


def does_stop_worsen(
    direction: str, current: float | None, nxt: float
) -> bool:
    """H2 — long: new stop lower than current; short: new stop higher.

    Thin wrapper over ``bolsa_domain.lifecycle.stop_worsens`` (single house).
    """
    from bolsa_domain.lifecycle import stop_worsens

    return stop_worsens(direction, current, nxt)


def clamp_stop_not_worsen(
    direction: str, current: float | None, nxt: float
) -> float:
    """V1.29 — trail/protect advisory: nunca proponer un stop que empeore el vigente."""
    if nxt != nxt or nxt <= 0:
        return nxt
    if does_stop_worsen(direction, current, nxt) and current is not None and current > 0:
        return round(float(current) * 10000) / 10000
    return round(float(nxt) * 10000) / 10000


def _now_iso(at: str | None = None) -> str:
    if isinstance(at, str) and at.strip():
        return at
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def holding_deadline_from(
    created_at: str | None, max_holding_period_days: int | None
) -> str | None:
    """``created_at + max_holding_period_days`` en ISO-UTC, o ``None`` si no es calculable.

    El techo se congela en el NACIMIENTO (decisión D1 de 2b): se calcula una vez desde
    ``created_at`` y se persiste, de modo que un reinicio no lo re-deriva con otro reloj ni
    lo mueve. Días no positivos o fecha ilegible ⇒ ``None`` (nunca un deadline inventado:
    ``None`` deja ``TIME_STOP`` inalcanzable, que es el comportamiento explícito de hoy).
    """
    if max_holding_period_days is None or max_holding_period_days <= 0:
        return None
    if not isinstance(created_at, str) or not created_at.strip():
        return None
    raw = created_at.strip().replace("Z", "+00:00")
    try:
        born = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if born.tzinfo is None:
        born = born.replace(tzinfo=UTC)
    deadline = born.astimezone(UTC) + timedelta(days=int(max_holding_period_days))
    return deadline.strftime("%Y-%m-%dT%H:%M:%SZ")


def signed_r_from_price(
    direction: TradePlanDirection,
    entry: float | None,
    risk: float | None,
    price: float,
) -> float | None:
    """R firmado vs entry/risk. Sin inputs válidos → None."""
    if direction not in ("long", "short"):
        return None
    if entry is None or risk is None or risk <= 0:
        return None
    if price <= 0:
        return None
    raw = (price - entry) / risk if direction == "long" else (entry - price) / risk
    return _round4(raw)


def _is_break_even_stop(position: PositionState) -> bool:
    entry = position.actual_entry
    stop = position.current_stop
    if entry is None or stop is None:
        return False
    if position.direction == "long":
        return stop >= entry
    if position.direction == "short":
        return stop <= entry
    return False


def derive_position_status(position: PositionState) -> PositionStatus:
    """Precedencia F2.1: CLOSED > BE→PROTECTED > PARTIAL > OPEN.

    AUTO-2: ``status`` sigue siendo el HECHO de cantidad/break-even (no se duplica la
    autoridad). El FSM ``lifecycle_state`` es aditivo y añade una sola afirmación que el
    stop no puede hacer: ``PROTECTED`` explícito. ``PARTIAL``/``CLOSED`` siguen mandando
    porque son hechos de cantidad, no interpretaciones.
    """
    if position.status == "CLOSED" or position.remaining_quantity <= 0:
        return "CLOSED"
    lifecycle = coerce_lifecycle_state(position.lifecycle_state)
    if lifecycle in PROTECTED_LIFECYCLE_STATES or _is_break_even_stop(position):
        return "PROTECTED"
    if position.remaining_quantity < position.quantity:
        return "PARTIAL"
    return "OPEN"


@dataclass(frozen=True, slots=True)
class PositionState:
    """Ciclo de vida de posición abierta (F2 + F2.1)."""

    position_id: str
    trade_plan_id: str
    instrument_id: str
    direction: TradePlanDirection
    status: PositionStatus
    planned_entry: float | None
    actual_entry: float | None
    initial_stop: float | None
    current_stop: float | None
    target1: float | None
    target2: float | None
    quantity: float
    remaining_quantity: float
    initial_risk: float | None
    realized_r: float
    unrealized_r: float | None
    mfe_mae: dict[str, object]
    thesis_health: dict[str, object] | None
    protection_state: dict[str, object] | None
    trailing: dict[str, object] | None
    exit_status: PositionExitStatus
    created_at: str
    updated_at: str
    target1_achieved_at: str | None = None
    target2_achieved_at: str | None = None
    target1_leg: TargetLeg | None = None
    target2_leg: TargetLeg | None = None
    revisions: tuple[PositionRevision, ...] = ()
    # V1.65 — origen DecisionPackage (≠ trade_plan_id cuando ambos existen).
    decision_id: str | None = None
    # AUTO-2 / V2.42 — FSM explícito del ciclo de vida. ``None`` = no persistido por un
    # tag anterior (se proyecta desde los campos legacy); nunca se inventa al nacer.
    lifecycle_state: PositionLifecycleState | None = None
    # V2.42 slice 2b (E1) — techo de mantenimiento congelado en el nacimiento. ``None``
    # (blob de un tag anterior, adopción sin horizonte, o plantilla sin días) ⇒ el plan de
    # salida no recibe ``expires_at`` y ``TIME_STOP`` queda inalcanzable, jamás adivinado.
    holding_deadline_at: str | None = None
    # V2.42 slice 2b (E3) — nivel de invalidación de la TESIS congelado en el nacimiento.
    # Se lee del plan (``invalidationPrice``) si lo declara; si no, la regla estructural es
    # su propio stop: el nivel en que el setup está muerto. ``None`` ⇒ no hay nivel
    # declarado y la invalidación NO se inventa (fail-closed, no "vende por si acaso").
    invalidation_price: float | None = None
    # V2.47 — identidad del ciclo financiero (señal→…→PnL) que abrió esta posición. Viaja
    # dentro del JSONB ``position_state`` (sin migración) para que el cierre herede el
    # ciclo. ``None`` = no persistido por un tag anterior / fill sin decisión AUTO:
    # desconocido ≠ fabricado.
    cycle_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "positionId": self.position_id,
            "tradePlanId": self.trade_plan_id,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "status": self.status,
            "plannedEntry": self.planned_entry,
            "actualEntry": self.actual_entry,
            "initialStop": self.initial_stop,
            "currentStop": self.current_stop,
            "target1": self.target1,
            "target2": self.target2,
            "target1AchievedAt": self.target1_achieved_at,
            "target2AchievedAt": self.target2_achieved_at,
            "target1Leg": self.target1_leg.to_dict() if self.target1_leg else None,
            "target2Leg": self.target2_leg.to_dict() if self.target2_leg else None,
            "quantity": self.quantity,
            "remainingQuantity": self.remaining_quantity,
            "initialRisk": self.initial_risk,
            "realizedR": self.realized_r,
            "unrealizedR": self.unrealized_r,
            "mfeMae": dict(self.mfe_mae),
            "thesisHealth": self.thesis_health,
            "protectionState": self.protection_state,
            "trailing": self.trailing,
            "exitStatus": self.exit_status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "revisions": [r.to_dict() for r in self.revisions],
        }
        if self.decision_id:
            out["decisionId"] = self.decision_id
        # AUTO-2: se emite sólo si el FSM está definido. Ausente = "no persistido":
        # la rehidratación lo proyecta desde los campos legacy en vez de degradar.
        if self.lifecycle_state is not None:
            out["lifecycleState"] = self.lifecycle_state
        # V2.42 slice 2b: el techo congelado se emite sólo si existe (misma doctrina:
        # ausente = "no persistido", no "None" disfrazado de dato).
        if self.holding_deadline_at is not None:
            out[HOLDING_DEADLINE_KEY] = self.holding_deadline_at
        # V2.42 slice 2b: el nivel de invalidación congelado, si existe.
        if self.invalidation_price is not None:
            out[INVALIDATION_PRICE_KEY] = self.invalidation_price
        # V2.47: el ciclo financiero se emite sólo si existe (misma doctrina: ausente =
        # "no persistido", nunca "None" disfrazado de dato).
        if self.cycle_id:
            out[CYCLE_ID_KEY] = self.cycle_id
        return out


def _trim_id(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    t = value.strip()
    return t if t else None


def _iso_or_none(value: object | None) -> str | None:
    """Instante ISO persistido o ``None``. Un valor no-string no se coacciona."""
    if not isinstance(value, str):
        return None
    t = value.strip()
    return t if t else None


def _invalidation_level(trade_plan: dict[str, object], initial_stop: float | None) -> float | None:
    """Nivel de invalidación de la tesis, congelado: lo que declare el plan, o el stop.

    V2.42 slice 2b (E3). El plan puede traerlo explícito (``invalidationPrice``); si no,
    la regla estructural es su propio stop (el nivel en el que el setup está muerto). NO se
    inventa un nivel: sin stop ni declaración ⇒ ``None`` y la invalidación no se deriva.
    """
    declared = _finite_positive(trade_plan.get(INVALIDATION_PRICE_KEY))
    if declared is not None:
        return declared
    return initial_stop


def _resolve_revision_decision_id(
    position: PositionState,
    decision_id: str | None = None,
) -> str | None:
    return _trim_id(decision_id) or _trim_id(position.decision_id)


def position_state_from_dict(raw: dict[str, object] | None) -> PositionState | None:
    """P3 — rehidrata JSONB persistido. Inverso de ``to_dict``. Sin campos nuevos.

    Claves de bookkeeping (``_…``) se ignoran. Dict inválido → None.
    """
    if not isinstance(raw, dict):
        return None
    direction = raw.get("direction")
    if direction not in ("long", "short"):
        return None
    status = raw.get("status")
    if status not in ("OPEN", "PARTIAL", "PROTECTED", "CLOSED"):
        return None
    position_id = raw.get("positionId")
    trade_plan_id = raw.get("tradePlanId")
    instrument_id = raw.get("instrumentId")
    if not isinstance(position_id, str) or not position_id.strip():
        return None
    if not isinstance(trade_plan_id, str) or not trade_plan_id.strip():
        return None
    if not isinstance(instrument_id, str) or not instrument_id.strip():
        return None
    qty = _finite_positive(raw.get("quantity"))
    remaining = _finite(raw.get("remainingQuantity"))
    if qty is None or remaining is None or remaining < 0:
        return None
    exit_status = raw.get("exitStatus")
    if exit_status not in ("none", "hint", "armed", "done"):
        exit_status = "none"
    created = raw.get("createdAt")
    updated = raw.get("updatedAt")
    if not isinstance(created, str) or not created.strip():
        return None
    if not isinstance(updated, str) or not updated.strip():
        updated = created
    mfe_raw = raw.get("mfeMae")
    mfe_mae: dict[str, object]
    if isinstance(mfe_raw, dict):
        mfe_mae = dict(mfe_raw)
    else:
        mfe_mae = {"mfeR": None, "maeR": None, "source": "none"}
    realized = _finite(raw.get("realizedR"))
    if realized is None:
        realized = 0.0
    stub_health = raw.get("thesisHealth")
    stub_protect = raw.get("protectionState")
    stub_trail = raw.get("trailing")
    t1_at = (
        raw.get("target1AchievedAt").strip()
        if isinstance(raw.get("target1AchievedAt"), str)
        and str(raw.get("target1AchievedAt")).strip()
        else None
    )
    t2_at = (
        raw.get("target2AchievedAt").strip()
        if isinstance(raw.get("target2AchievedAt"), str)
        and str(raw.get("target2AchievedAt")).strip()
        else None
    )
    t1_price = _finite(raw.get("target1"))
    t2_price = _finite(raw.get("target2"))
    decision_id = _trim_id(raw.get("decisionId"))
    # AUTO-2: clave ausente ⇒ None (un blob de un tag anterior se proyecta desde los
    # campos legacy). Clave presente pero inválida ⇒ RECONCILIATION_REQUIRED: un estado
    # no verificable nunca se interpreta como "sin protección".
    lifecycle_raw = raw.get(LIFECYCLE_STATE_KEY)
    lifecycle_state: PositionLifecycleState | None = None
    #: ``True`` sólo si la degradación la IMPUSO la rehidratación (valor desconocido o
    #: inconsistente con el hecho de cantidad). Un estado degradado PERSISTIDO de verdad
    #: conserva su ``protection_state`` rico (``PROTECTION_MISSING`` + source): forzarlo
    #: al stub genérico perdería la fuente de la degradación (auditoría).
    forced_degradation = False
    if LIFECYCLE_STATE_KEY in raw and lifecycle_raw is not None:
        coerced = coerce_lifecycle_state(lifecycle_raw)
        if coerced is None or not lifecycle_state_is_consistent(
            coerced, remaining_quantity=remaining, quantity=qty
        ):
            # Estado no verificable contra el hecho de cantidad (p. ej. CLOSED con
            # posición viva) o inventado: degrada, nunca se confía en él.
            lifecycle_state = "RECONCILIATION_REQUIRED"
            forced_degradation = True
        else:
            lifecycle_state = coerced
    elif LIFECYCLE_STATE_KEY in raw:
        # H-6 del §9 del pack: clave PRESENTE con valor ``null`` no es "no persistido"
        # (eso es la AUSENCIA): alguien escribió un FSM nulo ⇒ no verificable ⇒ degrada.
        lifecycle_state = "RECONCILIATION_REQUIRED"
        forced_degradation = True
    if lifecycle_state is None and not (
        (status == "CLOSED" and remaining <= 0) or (status != "CLOSED" and remaining > 0)
    ):
        # H-6: sin FSM persistido, el HECHO de cantidad sigue siendo la autoridad. Un blob
        # de un tag anterior con ``status`` que desmiente la cantidad (CLOSED con posición
        # viva, o una familia abierta sin cantidad) no se proyecta como verificado.
        lifecycle_state = "RECONCILIATION_REQUIRED"
        forced_degradation = True
    protection_state = dict(stub_protect) if isinstance(stub_protect, dict) else {"status": "none"}
    if forced_degradation:
        protection_state = {
            "state": "RECONCILIATION_REQUIRED",
            "source": "none",
            "reason": LIFECYCLE_STATE_UNVERIFIED,
        }
    return PositionState(
        position_id=position_id.strip(),
        trade_plan_id=trade_plan_id.strip(),
        instrument_id=instrument_id.strip(),
        direction=direction,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        planned_entry=_finite(raw.get("plannedEntry")),
        actual_entry=_finite(raw.get("actualEntry")),
        initial_stop=_finite(raw.get("initialStop")),
        current_stop=_finite(raw.get("currentStop")),
        target1=t1_price,
        target2=t2_price,
        quantity=_round4(qty),
        remaining_quantity=_round4(remaining),
        initial_risk=_finite(raw.get("initialRisk")),
        realized_r=_round4(realized),
        unrealized_r=_finite(raw.get("unrealizedR")),
        mfe_mae=mfe_mae,
        thesis_health=dict(stub_health) if isinstance(stub_health, dict) else {"status": "none"},
        protection_state=protection_state,
        trailing=dict(stub_trail) if isinstance(stub_trail, dict) else {"status": "none"},
        exit_status=exit_status,  # type: ignore[arg-type]
        created_at=created.strip(),
        updated_at=updated.strip() if isinstance(updated, str) else created.strip(),
        target1_achieved_at=t1_at,
        target2_achieved_at=t2_at,
        target1_leg=target_leg_from_unknown(
            raw.get("target1Leg"), price=t1_price, achieved_at=t1_at
        ),
        target2_leg=target_leg_from_unknown(
            raw.get("target2Leg"), price=t2_price, achieved_at=t2_at
        ),
        revisions=revisions_from_raw(raw.get("revisions")),
        decision_id=decision_id,
        lifecycle_state=lifecycle_state,
        # Round-trip exacto del techo YA congelado: no se re-deriva con otro reloj.
        holding_deadline_at=_iso_or_none(raw.get(HOLDING_DEADLINE_KEY)),
        invalidation_price=_finite_positive(raw.get(INVALIDATION_PRICE_KEY)),
        cycle_id=_trim_id(raw.get(CYCLE_ID_KEY)),
    )


def build_position_state_from_fill(
    trade_plan: dict[str, object] | None,
    *,
    fill_price: float | None,
    fill_quantity: float | None,
    filled_at: str | None = None,
    position_id: str | None = None,
    override: dict[str, object] | None = None,
    max_holding_period_days: int | None = None,
    cycle_id: str | None = None,
) -> PositionState | None:
    """Factory F2: TradePlan dict + fill → OPEN.

    H2: exige status TRIGGERED, o override auditado. WATCH/ARMED no nacen.
    Sin plan/fill válido → None.

    V2.42 slice 2b (E1): ``max_holding_period_days`` (de la plantilla de salida) se
    CONGELA aquí como ``holding_deadline_at = filled_at + días``. Llega como parámetro y no
    desde el ``TradePlan`` porque el plan expresa su propia validez de ENTRADA
    (``expiresAt``), no el horizonte de mantenimiento (decisión D1 de 2b).
    """
    if not isinstance(trade_plan, dict):
        return None
    direction = trade_plan.get("direction")
    if direction not in ("long", "short"):
        return None
    status = trade_plan.get("status")
    if status != "TRIGGERED" and not _is_audited_override(override):
        return None
    price = _finite_positive(fill_price)
    qty = _finite_positive(fill_quantity)
    if price is None or qty is None:
        return None

    decision_id = trade_plan.get("decisionId")
    if not isinstance(decision_id, str) or not decision_id.strip():
        return None
    decision_id = decision_id.strip()
    trade_plan_id_raw = trade_plan.get("tradePlanId")
    trade_plan_id = (
        trade_plan_id_raw.strip()
        if isinstance(trade_plan_id_raw, str) and trade_plan_id_raw.strip()
        else decision_id
    )
    instrument_id = trade_plan.get("instrumentId")
    if not isinstance(instrument_id, str) or not instrument_id.strip():
        return None

    planned_entry = _finite(trade_plan.get("entry"))
    planned_stop = _finite(trade_plan.get("structuralStop"))
    actual_entry = _round4(price)
    initial_stop = planned_stop
    if initial_stop is not None:
        initial_risk = _round4(abs(actual_entry - initial_stop))
    elif planned_entry is not None and planned_stop is not None:
        initial_risk = _round4(abs(planned_entry - planned_stop))
    else:
        initial_risk = None
    if initial_risk is not None and initial_risk <= 0:
        initial_risk = None

    now = filled_at if isinstance(filled_at, str) and filled_at else ""
    if not now:
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    stub = {"status": "none"}
    qty_r = _round4(qty)
    pid = position_id.strip() if isinstance(position_id, str) and position_id.strip() else str(uuid4())
    t1 = _finite(trade_plan.get("target1"))
    t2 = _finite(trade_plan.get("target2"))

    return PositionState(
        position_id=pid,
        decision_id=decision_id,
        trade_plan_id=trade_plan_id,
        instrument_id=instrument_id,
        direction=direction,  # type: ignore[arg-type]
        status="OPEN",
        planned_entry=planned_entry,
        actual_entry=actual_entry,
        initial_stop=initial_stop,
        current_stop=initial_stop,
        target1=t1,
        target2=t2,
        quantity=qty_r,
        remaining_quantity=qty_r,
        initial_risk=initial_risk,
        realized_r=0.0,
        unrealized_r=None,
        mfe_mae={"mfeR": None, "maeR": None, "source": "none"},
        thesis_health=dict(stub),
        protection_state=dict(stub),
        trailing=dict(stub),
        exit_status="none",
        created_at=now,
        updated_at=now,
        target1_leg=birth_target_leg(t1),
        target2_leg=birth_target_leg(t2),
        revisions=(),
        # V2.42 slice 2b (E1): techo de mantenimiento congelado al nacer.
        holding_deadline_at=holding_deadline_from(now, max_holding_period_days),
        # V2.42 slice 2b (E3): nivel de invalidación congelado al nacer. El plan puede
        # declararlo (``invalidationPrice``); si no, la regla estructural es su stop.
        invalidation_price=_invalidation_level(trade_plan, initial_stop),
        # V2.47: el ciclo se hereda del llamante (fuente única: el motor de entrada). Si no
        # se pasa, se acepta el que declare el plan; nunca se inventa.
        cycle_id=_trim_id(cycle_id) or _trim_id(trade_plan.get(CYCLE_ID_KEY)),
    )


def _with_revision_if_changed(
    previous: PositionState,
    next_pos: PositionState,
    *,
    origin: PositionRevisionOrigin,
    reason: str | None,
    at: str,
    decision_id: str | None = None,
    policy_id: str | None = None,
) -> PositionState:
    if not stop_or_status_changed(
        previous_stop=previous.current_stop,
        next_stop=next_pos.current_stop,
        previous_status=previous.status,
        next_status=next_pos.status,
    ):
        return next_pos
    rev = build_position_revision(
        at=at,
        previous_stop=previous.current_stop,
        next_stop=next_pos.current_stop,
        previous_status=previous.status,
        next_status=next_pos.status,
        origin=origin,
        reason=reason,
        decision_id=_resolve_revision_decision_id(previous, decision_id),
        policy_id=policy_id,
    )
    return replace(next_pos, revisions=previous.revisions + (rev,))


def apply_position_mark(
    position: PositionState | None,
    mark_price: float,
    *,
    at: str | None = None,
) -> PositionState | None:
    """F2.1 mark → unrealized_r + picos MFE/MAE. No cambia status."""
    if position is None or position.status == "CLOSED":
        return None
    price = _finite_positive(mark_price)
    if price is None:
        return None

    unrealized = signed_r_from_price(
        position.direction,
        position.actual_entry,
        position.initial_risk,
        price,
    )

    mfe_mae = dict(position.mfe_mae)
    if unrealized is not None:
        prev_mfe = _finite(mfe_mae.get("mfeR"))
        prev_mae = _finite(mfe_mae.get("maeR"))
        base_mfe = prev_mfe if prev_mfe is not None else unrealized
        base_mae = prev_mae if prev_mae is not None else unrealized
        source = mfe_mae.get("source")
        if source == "none":
            source = "close_proxy"
        elif source not in ("bars", "close_proxy"):
            source = "close_proxy"
        mfe_mae = {
            "mfeR": _round4(max(base_mfe, unrealized)),
            "maeR": _round4(min(base_mae, unrealized)),
            "source": source,
        }

    # AUTO-2: extremo favorable en PRECIO (distinto del MFE en R). Es el ancla del
    # trailing en R: sin este pico no hay trailing posible y el stop quedaría congelado.
    trailing = dict(position.trailing) if isinstance(position.trailing, dict) else {}
    anchor = _finite_positive(position.actual_entry)
    prev_hw = _finite_positive(trailing.get("highWatermark"))
    extreme: float | None = None
    if position.direction == "long":
        candidates = [c for c in (prev_hw, anchor, price) if c is not None]
        extreme = max(candidates)
    elif position.direction == "short":
        candidates = [c for c in (prev_hw, anchor, price) if c is not None]
        extreme = min(candidates)
    if extreme is not None:
        trailing["highWatermark"] = _round4(extreme)
        trailing["updatedAt"] = _now_iso(at)

    return replace(
        position,
        unrealized_r=unrealized,
        mfe_mae=mfe_mae,
        trailing=trailing or position.trailing,
        updated_at=_now_iso(at),
    )


def apply_position_reduce(
    position: PositionState | None,
    qty: float,
    *,
    exit_price: float | None = None,
    at: str | None = None,
    origin: PositionRevisionOrigin = "reduce",
    reason: str | None = None,
    mark_target1_achieved: bool = False,
    mark_target2_achieved: bool = False,
    fill_id: str | None = None,
    event_id: str | None = None,
    decision_id: str | None = None,
    policy_id: str | None = None,
) -> PositionState | None:
    """F2.1 reduce → remaining / realized_r / PARTIAL|CLOSED.

    OI-5: append revisión si status cambia.
    V1.21: ``mark_target1_achieved`` fija ``target1_achieved_at``.
    V1.27: ``mark_target2_achieved`` fija ``target2_achieved_at``.
    """
    if position is None or position.status == "CLOSED":
        return None
    cut_in = _finite_positive(qty)
    if cut_in is None:
        return None
    if cut_in > position.remaining_quantity + 1e-12:
        return None

    cut = _round4(min(cut_in, position.remaining_quantity))
    remaining = _round4(position.remaining_quantity - cut)
    realized = position.realized_r
    exit_p = _finite_positive(exit_price) if exit_price is not None else None
    if exit_p is not None and position.quantity > 0:
        slice_r = signed_r_from_price(
            position.direction,
            position.actual_entry,
            position.initial_risk,
            exit_p,
        )
        if slice_r is not None:
            realized = _round4(realized + slice_r * (cut / position.quantity))

    updated = _now_iso(at)
    t1_at = (
        position.target1_achieved_at or updated
        if mark_target1_achieved
        else position.target1_achieved_at
    )
    t2_at = (
        position.target2_achieved_at or updated
        if mark_target2_achieved
        else position.target2_achieved_at
    )
    t1_leg = (
        _advance_target_leg(
            position.target1_leg,
            "executed",
            at=updated,
            event_id=event_id,
            fill_id=fill_id,
        )
        if mark_target1_achieved
        else position.target1_leg
    )
    t2_leg = (
        _advance_target_leg(
            position.target2_leg,
            "executed",
            at=updated,
            event_id=event_id,
            fill_id=fill_id,
        )
        if mark_target2_achieved
        else position.target2_leg
    )
    if (
        remaining <= 0
        and t2_leg is not None
        and t2_leg.status == "triggered"
        and fill_id
    ):
        t2_leg = _advance_target_leg(
            t2_leg,
            "executed",
            at=updated,
            event_id=event_id,
            fill_id=fill_id,
        )
        if not t2_at:
            t2_at = updated
    if remaining <= 0:
        next_pos = replace(
            position,
            remaining_quantity=0.0,
            realized_r=realized,
            status="CLOSED",
            exit_status="done",
            target1_achieved_at=t1_at,
            target2_achieved_at=t2_at,
            target1_leg=t1_leg,
            target2_leg=t2_leg,
            updated_at=updated,
        )
        return _with_revision_if_changed(
            position,
            next_pos,
            origin=origin,
            reason=reason,
            at=updated,
            decision_id=decision_id,
            policy_id=policy_id,
        )

    mid = replace(
        position,
        remaining_quantity=remaining,
        realized_r=realized,
        target1_achieved_at=t1_at,
        target2_achieved_at=t2_at,
        target1_leg=t1_leg,
        target2_leg=t2_leg,
        updated_at=updated,
    )
    next_pos = replace(mid, status=derive_position_status(mid))
    return _with_revision_if_changed(
        position,
        next_pos,
        origin=origin,
        reason=reason,
        at=updated,
        decision_id=decision_id,
        policy_id=policy_id,
    )


def apply_position_current_stop(
    position: PositionState | None,
    stop: float,
    *,
    at: str | None = None,
    override: dict[str, object] | None = None,
    origin: PositionRevisionOrigin | None = None,
    reason: str | None = None,
    decision_id: str | None = None,
    policy_id: str | None = None,
) -> PositionState | None:
    """F2.1 current_stop geométrico → posible PROTECTED (BE).

    H2: no empeora el stop sin override auditado.
    OI-5: append revisión si stop o status cambian de verdad.
    """
    if position is None or position.status == "CLOSED":
        return None
    stop_p = _finite_positive(stop)
    if stop_p is None:
        return None
    worsens = _stop_worsens(position.direction, position.current_stop, stop_p)
    if worsens and not _is_audited_override(override):
        return None

    updated = _now_iso(at)
    mid = replace(
        position,
        current_stop=_round4(stop_p),
        updated_at=updated,
    )
    next_pos = replace(mid, status=derive_position_status(mid))

    resolved_origin: PositionRevisionOrigin
    if origin is not None:
        resolved_origin = origin
    elif worsens:
        resolved_origin = "override"
    else:
        resolved_origin = "stop"

    override_reason = None
    if isinstance(override, dict):
        raw_reason = override.get("reason")
        if isinstance(raw_reason, str) and raw_reason.strip():
            override_reason = raw_reason.strip()
    resolved_reason = reason if reason is not None else override_reason

    return _with_revision_if_changed(
        position,
        next_pos,
        origin=resolved_origin,
        reason=resolved_reason,
        at=updated,
        decision_id=decision_id,
        policy_id=policy_id,
    )
