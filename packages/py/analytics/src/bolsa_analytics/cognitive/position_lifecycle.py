"""PositionLifecycle — FSM explícito del ciclo de vida de una posición (AUTO-2 / V2.42).

Antes de AUTO-2 el ciclo de vida era un ``PositionStatus`` de cuatro valores **derivado**
(``OPEN``/``PARTIAL``/``PROTECTED``/``CLOSED``) más dos ejes sueltos (``exitStatus`` y
``TargetLeg.status``). Ese derivado no distingue "abierta" de "entrada pendiente", no
registra T1 como transición, no tiene estados de degradación y no puede afirmar que una
posición esté sin protección. Este módulo añade la máquina de estados **explícita**:

* ``PositionLifecycleState`` — el estado persistido y verificable.
* ``PositionLifecycleEvent`` — la entrada que provoca una transición.
* ``ALLOWED_TRANSITIONS`` — la tabla de transiciones válidas (todo lo demás se RECHAZA).
* ``apply_lifecycle_event`` — función pura, **fail-closed**: una transición no listada no
  avanza y devuelve el motivo; un estado desconocido degrada a ``RECONCILIATION_REQUIRED``
  (invariante del roadmap: un estado no verificable nunca es "sin protección").

Invariantes que este módulo sostiene:

* **Ninguna salida protectora se veta jamás**: desde cualquier estado con posición viva,
  ``EXIT_FILLED`` conduce a ``CLOSED`` y ``EXIT_REQUESTED`` a ``EXIT_PENDING``.
* **No hay dos autoridades**: ``status`` sigue siendo el hecho de cantidad/break-even
  (``derive_position_status``); ``lifecycle_state`` es la autoridad del FSM y es aditivo.
* **Puro**: sin I/O, sin reloj propio (``at`` se inyecta) y sin importar ``application``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, TypedDict

from bolsa_analytics.cognitive.exit_policy import trail_distance_r_from_width

if TYPE_CHECKING:  # pragma: no cover - sólo para tipado (evita ciclo de import)
    from bolsa_analytics.cognitive.position_state import PositionState

PositionLifecycleState = Literal[
    "FLAT",
    "ENTRY_PENDING",
    "OPEN",
    "PROTECTED",
    "T1_REACHED",
    "PARTIAL_EXIT",
    "TRAILING",
    "EXIT_PENDING",
    "CLOSED",
    "ERROR",
    "UNKNOWN",
    "RECONCILIATION_REQUIRED",
    "PROTECTION_MISSING",
]

PositionLifecycleEvent = Literal[
    "ENTRY_SUBMITTED",
    "ENTRY_FILLED",
    "ENTRY_CANCELLED",
    "PROTECT_APPLIED",
    "T1_HIT",
    "PARTIAL_FILL",
    "TRAIL_ARMED",
    "TRAIL_ADVANCED",
    "EXIT_REQUESTED",
    "EXIT_FILLED",
    "MANAGEMENT_SKIPPED",
    "STATE_UNVERIFIED",
    "PROTECTION_UNVERIFIED",
    "RECONCILED",
]

LIFECYCLE_STATE_KEY = "lifecycleState"

#: Motivos del FSM (dueño único del literal; ``auto_reason_codes`` los re-expone).
LIFECYCLE_TRANSITION_REJECTED = "lifecycle_transition_rejected"
LIFECYCLE_STATE_UNVERIFIED = "lifecycle_state_unverified"
LIFECYCLE_RESOLUTION_MISSING = "lifecycle_resolution_missing"

#: Estados con posición verificable (la familia "abierta" + los terminales).
VERIFIED_LIFECYCLE_STATES: frozenset[PositionLifecycleState] = frozenset(
    {
        "FLAT",
        "ENTRY_PENDING",
        "OPEN",
        "PROTECTED",
        "T1_REACHED",
        "PARTIAL_EXIT",
        "TRAILING",
        "EXIT_PENDING",
        "CLOSED",
    }
)

#: Estados degradados: la posición NO está sin protección por el hecho de degradar.
DEGRADED_LIFECYCLE_STATES: frozenset[PositionLifecycleState] = frozenset(
    {"ERROR", "UNKNOWN", "RECONCILIATION_REQUIRED", "PROTECTION_MISSING"}
)

#: Familia abierta: posición viva que todavía puede recibir gestión.
ACTIVE_LIFECYCLE_STATES: frozenset[PositionLifecycleState] = frozenset(
    {"OPEN", "PROTECTED", "T1_REACHED", "PARTIAL_EXIT", "TRAILING", "EXIT_PENDING"}
)

#: Estados desde los que una salida protectora SIEMPRE es aceptada (nunca se veta).
#: ``FLAT`` no tiene posición y ``CLOSED`` es terminal: fuera por definición.
PROTECTIVE_EXIT_ALLOWED_STATES: frozenset[PositionLifecycleState] = frozenset(
    (ACTIVE_LIFECYCLE_STATES | DEGRADED_LIFECYCLE_STATES) | {"ENTRY_PENDING"}
)

#: ``CLOSED`` implica PROTECTED lógico sólo si el FSM lo afirma explícitamente.
#: ``TRAILING`` no implica break-even (depende de la anchura en R): lo decide el stop.
PROTECTED_LIFECYCLE_STATES: frozenset[PositionLifecycleState] = frozenset({"PROTECTED"})

_LIFECYCLE_INACTIVE_STATES: frozenset[str] = frozenset({"FLAT", "CLOSED"})

_MANAGEMENT_EVENTS: dict[PositionLifecycleEvent, PositionLifecycleState] = {
    "PROTECT_APPLIED": "PROTECTED",
    "T1_HIT": "T1_REACHED",
    "PARTIAL_FILL": "PARTIAL_EXIT",
    "TRAIL_ARMED": "TRAILING",
    # Un trail que AVANZA es un hecho observable sobre una posición viva: vale desde
    # cualquier estado de gestión (T1 alcanzado ⇒ trailing armado ⇒ el stop sube) y
    # RE-VERIFICA los degradados. Sin esto, el ratchet real desde ``T1_REACHED`` se
    # rechazaba por tabla y el estado quedaba congelado mientras el stop subía.
    "TRAIL_ADVANCED": "TRAILING",
    "EXIT_REQUESTED": "EXIT_PENDING",
    "EXIT_FILLED": "CLOSED",
    "MANAGEMENT_SKIPPED": "RECONCILIATION_REQUIRED",
    "STATE_UNVERIFIED": "RECONCILIATION_REQUIRED",
    "PROTECTION_UNVERIFIED": "PROTECTION_MISSING",
}

#: Tabla EXPLÍCITA de transiciones: estado → evento → estado destino.
#: Se construye por composición para no repetir la familia abierta, pero el resultado
#: es un mapa total y auditable (``ALLOWED_TRANSITIONS``).
_TRANSITIONS: dict[PositionLifecycleState, dict[PositionLifecycleEvent, PositionLifecycleState]] = {
    "FLAT": {"ENTRY_SUBMITTED": "ENTRY_PENDING"},
    "ENTRY_PENDING": {
        "ENTRY_FILLED": "OPEN",
        "ENTRY_CANCELLED": "FLAT",
        "EXIT_FILLED": "CLOSED",
        "EXIT_REQUESTED": "EXIT_PENDING",
        "STATE_UNVERIFIED": "RECONCILIATION_REQUIRED",
        "MANAGEMENT_SKIPPED": "RECONCILIATION_REQUIRED",
    },
    "OPEN": dict(_MANAGEMENT_EVENTS),
    "PROTECTED": {**_MANAGEMENT_EVENTS, "PROTECT_APPLIED": "PROTECTED"},
    "T1_REACHED": {
        **_MANAGEMENT_EVENTS,
        "PROTECT_APPLIED": "PROTECTED",
        "T1_HIT": "T1_REACHED",
    },
    "PARTIAL_EXIT": {
        **_MANAGEMENT_EVENTS,
        "PARTIAL_FILL": "PARTIAL_EXIT",
    },
    "TRAILING": {
        **_MANAGEMENT_EVENTS,
        "PROTECT_APPLIED": "TRAILING",
        "TRAIL_ARMED": "TRAILING",
        "TRAIL_ADVANCED": "TRAILING",
    },
    "EXIT_PENDING": {
        "EXIT_FILLED": "CLOSED",
        "EXIT_REQUESTED": "EXIT_PENDING",
        "PARTIAL_FILL": "PARTIAL_EXIT",
        "MANAGEMENT_SKIPPED": "RECONCILIATION_REQUIRED",
        "STATE_UNVERIFIED": "RECONCILIATION_REQUIRED",
    },
    # ``CLOSED`` es terminal: sólo la idempotencia del cierre.
    "CLOSED": {"EXIT_FILLED": "CLOSED"},
    # Degradados: un HECHO observable (fill, T1, ratchet de stop, salida) RE-VERIFICA el
    # estado. No son estados terminales: la degradación se declara, no se esconde, y se
    # sale de ella con la misma tabla de gestión. ``RECONCILED`` (resolución explícita a
    # un estado verificado) se atiende aparte en ``apply_lifecycle_event``.
    "UNKNOWN": dict(_MANAGEMENT_EVENTS),
    "ERROR": dict(_MANAGEMENT_EVENTS),
    "RECONCILIATION_REQUIRED": dict(_MANAGEMENT_EVENTS),
    "PROTECTION_MISSING": dict(_MANAGEMENT_EVENTS),
}

#: Vista estado → estados alcanzables (contrato público de la tabla).
ALLOWED_TRANSITIONS: dict[PositionLifecycleState, frozenset[PositionLifecycleState]] = {
    state: frozenset(targets.values()) for state, targets in _TRANSITIONS.items()
}

#: Todos los eventos del FSM (contrato público para el producto cartesiano de tests).
LIFECYCLE_EVENTS: tuple[PositionLifecycleEvent, ...] = (
    "ENTRY_SUBMITTED",
    "ENTRY_FILLED",
    "ENTRY_CANCELLED",
    "PROTECT_APPLIED",
    "T1_HIT",
    "PARTIAL_FILL",
    "TRAIL_ARMED",
    "TRAIL_ADVANCED",
    "EXIT_REQUESTED",
    "EXIT_FILLED",
    "MANAGEMENT_SKIPPED",
    "STATE_UNVERIFIED",
    "PROTECTION_UNVERIFIED",
    "RECONCILED",
)

_VALID_EVENTS: frozenset[str] = frozenset(LIFECYCLE_EVENTS)


def lifecycle_state_is_consistent(
    state: object,
    *,
    remaining_quantity: float | None,
    quantity: float | None,
) -> bool:
    """¿El estado persistido es verificable contra el hecho de cantidad?

    Un FSM que afirma ``CLOSED`` con cantidad viva (o ``FLAT`` con posición) no es
    verificable: el llamante debe degradarlo a ``RECONCILIATION_REQUIRED``, nunca
    confiar en él. Ausencia de cantidad ⇒ no se puede verificar (fail-closed).
    """
    parsed = coerce_lifecycle_state(state)
    if parsed is None:
        return False
    if remaining_quantity is None:
        return False
    if parsed in ("CLOSED", "FLAT"):
        return remaining_quantity <= 0
    if parsed in ACTIVE_LIFECYCLE_STATES:
        return remaining_quantity > 0
    # Degradados y ``ENTRY_PENDING``: el FSM ya declara que no pudo verificar.
    return True


class TrailingStateDict(TypedDict, total=False):
    """Contenido tipado de ``PositionState.trailing`` (antes ``dict`` sin esquema).

    ``status``: ``inactive`` | ``armed`` | ``active`` (el stub de nacimiento ``none`` se
    lee como ``inactive``). ``highWatermark`` es el extremo favorable alcanzado en PRECIO
    (no en R). ``trailDistanceR`` es la anchura vigente y ``anchorR`` el R del ancla.
    """

    status: str
    highWatermark: float | None
    trailDistanceR: float | None
    anchorR: float | None
    updatedAt: str | None


class ProtectionStateDict(TypedDict, total=False):
    """Contenido tipado de ``PositionState.protection_state``.

    ``state``: ``ACTIVE`` | ``PROTECTION_MISSING`` | ``RECONCILIATION_REQUIRED`` | ``NONE``.
    ``source``: ``plan`` | ``reconstructed`` | ``none``.
    """

    state: str
    source: str
    reason: str | None
    at: str | None


def _now_iso(at: str | None = None) -> str:
    if isinstance(at, str) and at.strip():
        return at
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _finite_positive(value: object) -> float | None:
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def coerce_lifecycle_state(value: object) -> PositionLifecycleState | None:
    """Estado válido o ``None``. Nunca inventa un estado por defecto."""
    if isinstance(value, str):
        trimmed = value.strip().upper()
        if trimmed in VERIFIED_LIFECYCLE_STATES or trimmed in DEGRADED_LIFECYCLE_STATES:
            return trimmed
    return None


def _coerce_event(value: object) -> PositionLifecycleEvent | None:
    if isinstance(value, str):
        trimmed = value.strip().upper()
        if trimmed in _VALID_EVENTS:
            return trimmed  # type: ignore[return-value]
    return None


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    """Una transición del FSM, aceptada o rechazada, con su motivo."""

    from_state: PositionLifecycleState
    #: El evento TAL COMO se intentó (``str``): un evento desconocido se journaliza tal cual.
    event: str
    to_state: PositionLifecycleState
    accepted: bool
    reason: str | None
    at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fromState": self.from_state,
            "event": self.event,
            "toState": self.to_state,
            "accepted": self.accepted,
            "reason": self.reason,
            "at": self.at,
        }


def apply_lifecycle_event(
    state: object,
    event: object,
    *,
    at: str | None = None,
    resolved_state: object = None,
) -> LifecycleTransition:
    """Aplica un evento al estado del FSM. Fail-closed.

    * Transición no listada ⇒ ``accepted=False`` y el estado NO avanza.
    * Estado de entrada desconocido ⇒ degrada a ``RECONCILIATION_REQUIRED`` (un estado
      no verificable nunca se interpreta como "sin protección").
    * ``RECONCILED`` sólo sale de la degradación con un ``resolved_state`` verificado
      explícito; sin él se rechaza (no se adivina el estado de vuelta).
    """
    when = _now_iso(at)
    parsed_event = _coerce_event(event)
    current = coerce_lifecycle_state(state)
    if current is None:
        # Estado no verificable: degrada (nunca se interpreta como "sin protección").
        return LifecycleTransition(
            from_state="UNKNOWN",
            event=str(event),
            to_state="RECONCILIATION_REQUIRED",
            accepted=True,
            reason=LIFECYCLE_STATE_UNVERIFIED,
            at=when,
        )
    if parsed_event is None:
        # El estado es válido; el EVENTO no. No se degrada el estado por un evento basura.
        return LifecycleTransition(
            from_state=current,
            event=str(event),
            to_state=current,
            accepted=False,
            reason=LIFECYCLE_TRANSITION_REJECTED,
            at=when,
        )
    if parsed_event == "RECONCILED":
        resolved = coerce_lifecycle_state(resolved_state)
        if resolved is None or resolved in DEGRADED_LIFECYCLE_STATES:
            return LifecycleTransition(
                from_state=current,
                event=parsed_event,
                to_state=current,
                accepted=False,
                reason=LIFECYCLE_RESOLUTION_MISSING,
                at=when,
            )
        return LifecycleTransition(
            from_state=current,
            event=parsed_event,
            to_state=resolved,
            accepted=True,
            reason=None,
            at=when,
        )
    target = _TRANSITIONS.get(current, {}).get(parsed_event)
    if target is None:
        return LifecycleTransition(
            from_state=current,
            event=parsed_event,
            to_state=current,
            accepted=False,
            reason=LIFECYCLE_TRANSITION_REJECTED,
            at=when,
        )
    return LifecycleTransition(
        from_state=current,
        event=parsed_event,
        to_state=target,
        accepted=True,
        reason=None,
        at=when,
    )


def advance_lifecycle(
    position: PositionState,
    event: PositionLifecycleEvent | str,
    *,
    at: str | None = None,
    resolved_state: object = None,
    mark_trailing: bool = False,
    trail_distance_r: float | None = None,
    anchor_r: float | None = None,
) -> tuple[PositionState, LifecycleTransition]:
    """Aplica el evento y devuelve ``(posición, transición)``.

    Si la transición se rechaza, la posición se devuelve **intacta**: el llamante tiene
    la transición para journalizar el rechazo (nunca un avance silencioso). Si se acepta,
    se actualiza ``lifecycle_state`` y se re-deriva ``status`` con la autoridad nueva.
    """
    transition = apply_lifecycle_event(
        derive_lifecycle_state(position), event, at=at, resolved_state=resolved_state
    )
    if not transition.accepted:
        return position, transition

    trailing = dict(position.trailing) if isinstance(position.trailing, dict) else {}
    if mark_trailing:
        # ``armed`` marca el momento en que T1 habilitó el trailing; ``active`` que el
        # stop ya lo refleja. Nunca se degrada un trailing ya activo.
        if transition.to_state == "TRAILING":
            trailing["status"] = "active"
        elif trailing.get("status") not in ("armed", "active"):
            trailing["status"] = "armed"
        if trail_distance_r is not None:
            trailing["trailDistanceR"] = round(float(trail_distance_r), 4)
        if anchor_r is not None:
            trailing["anchorR"] = round(float(anchor_r), 4)
        trailing["updatedAt"] = transition.at

    # Import diferido: ``position_state`` importa el literal de este módulo.
    from bolsa_analytics.cognitive.position_state import derive_position_status

    mid = replace(
        position,
        lifecycle_state=transition.to_state,
        trailing=trailing or position.trailing,
        updated_at=transition.at,
    )
    return replace(mid, status=derive_position_status(mid)), transition


def derive_lifecycle_state(position: PositionState | None) -> PositionLifecycleState:
    """Proyección de retrocompatibilidad desde los campos legacy.

    Si el FSM está persistido, MANDA. Si no (posición de un tag anterior, o adoptada),
    se proyecta sin inventar: ``CLOSED`` por cantidad, degradación declarada, y la
    familia abierta por T1/parcial/trailing/stop. Nunca devuelve un estado no verificado
    como si fuera verificado.
    """
    if position is None:
        return "FLAT"
    persisted = coerce_lifecycle_state(position.lifecycle_state)
    if persisted is not None:
        return persisted
    if position.status == "CLOSED" or position.remaining_quantity <= 0:
        return "CLOSED"
    protection = position.protection_state
    if isinstance(protection, dict):
        protection_name = str(protection.get("state") or protection.get("status") or "")
        if protection_name == "RECONCILIATION_REQUIRED":
            return "RECONCILIATION_REQUIRED"
        if protection_name == "PROTECTION_MISSING":
            return "PROTECTION_MISSING"
    if position.exit_status in ("armed", "hint"):
        return "EXIT_PENDING"
    if trailing_is_active(position):
        return "TRAILING"
    if position.remaining_quantity < position.quantity:
        return "PARTIAL_EXIT"
    if position.target1_achieved_at or _leg_done(position.target1_leg):
        return "T1_REACHED"
    if position.current_stop is not None and position.actual_entry is not None:
        if position.direction == "long" and position.current_stop >= position.actual_entry:
            return "PROTECTED"
        if position.direction == "short" and position.current_stop <= position.actual_entry:
            return "PROTECTED"
    return "OPEN"


def _leg_done(leg: object) -> bool:
    status = getattr(leg, "status", None)
    return status in ("triggered", "executed")


def trailing_status(position: PositionState | None) -> Literal["inactive", "armed", "active"]:
    """Estado del trailing tipado. El stub de nacimiento (``none``) es ``inactive``."""
    if position is None:
        return "inactive"
    trailing = position.trailing
    if not isinstance(trailing, dict):
        return "inactive"
    raw = str(trailing.get("status") or "").strip().lower()
    if raw == "active":
        return "active"
    if raw == "armed":
        return "armed"
    return "inactive"


def trailing_is_active(position: PositionState | None) -> bool:
    return trailing_status(position) == "active"


def high_watermark_from_position(position: PositionState | None) -> float | None:
    """Extremo favorable en precio registrado por ``apply_position_mark``."""
    if position is None:
        return None
    trailing = position.trailing
    if isinstance(trailing, dict):
        hw = _finite_positive(trailing.get("highWatermark"))
        if hw is not None:
            return hw
    return None


def is_trail_armed(position: PositionState | None) -> bool:
    """El trailing sólo se arma tras T1 (misma regla que el motor legacy: T1 ⇒ trailing)."""
    if position is None:
        return False
    if trailing_status(position) in ("armed", "active"):
        return True
    if position.target1_achieved_at:
        return True
    if _leg_done(position.target1_leg):
        return True
    return position.lifecycle_state in ("T1_REACHED", "PARTIAL_EXIT", "TRAILING")


def compute_trail_stop(
    position: PositionState | None,
    *,
    trail_width: str | None = None,
    high_watermark: float | None = None,
    armed: bool | None = None,
) -> float | None:
    """Stop de trailing en R sobre el extremo favorable. ``None`` si no es calculable.

    ``stop = highWatermark ∓ trail_distance_r × initial_risk`` (long/short) y **nunca**
    empeora el stop vigente (H2). No inventa riesgo: sin ``initial_risk`` no hay trailing
    (y el llamante debe declararlo, no sustituirlo por un porcentaje del precio).
    """
    if position is None or position.status == "CLOSED":
        return None
    if position.direction not in ("long", "short"):
        return None
    risk = _finite_positive(position.initial_risk)
    if risk is None:
        return None
    if armed is None:
        armed = is_trail_armed(position)
    if not armed:
        return None
    hw = _finite_positive(high_watermark)
    if hw is None:
        hw = high_watermark_from_position(position)
    if hw is None:
        hw = _finite_positive(position.actual_entry)
    if hw is None:
        return None
    distance = trail_distance_r_from_width(trail_width) * risk
    proposed = hw - distance if position.direction == "long" else hw + distance
    if proposed <= 0:
        return None
    current = _finite_positive(position.current_stop)
    if current is not None:
        from bolsa_domain.lifecycle import stop_worsens

        if stop_worsens(position.direction, current, proposed):
            return round(current * 10000) / 10000
    return round(proposed * 10000) / 10000


def trailing_state_dict(
    *,
    status: Literal["inactive", "armed", "active"],
    high_watermark: float | None = None,
    trail_distance_r: float | None = None,
    anchor_r: float | None = None,
    at: str | None = None,
) -> dict[str, object]:
    """``trailing`` tipado (``TrailingStateDict``) listo para persistir en el JSONB."""
    typed = TrailingStateDict(
        status=status,
        highWatermark=high_watermark,
        trailDistanceR=trail_distance_r,
        anchorR=anchor_r,
        updatedAt=at or _now_iso(),
    )
    return {**typed}


def protection_state_dict(
    state: Literal["ACTIVE", "PROTECTION_MISSING", "RECONCILIATION_REQUIRED", "NONE"],
    *,
    source: Literal["plan", "reconstructed", "none"] = "plan",
    reason: str | None = None,
    at: str | None = None,
) -> dict[str, object]:
    """``protection_state`` tipado (``ProtectionStateDict``) listo para persistir."""
    typed = ProtectionStateDict(
        state=state,
        source=source,
        reason=reason,
        at=at or _now_iso(),
    )
    return {**typed}


def protection_state_name(position: PositionState | None) -> str:
    """``ACTIVE`` | ``PROTECTION_MISSING`` | ``RECONCILIATION_REQUIRED`` | ``NONE``."""
    if position is None:
        return "NONE"
    raw = position.protection_state
    if not isinstance(raw, dict):
        return "NONE"
    name = str(raw.get("state") or raw.get("status") or "").strip().upper()
    if name in ("ACTIVE", "PROTECTION_MISSING", "RECONCILIATION_REQUIRED"):
        return name
    # El stub de nacimiento (``{"status": "none"}``) NO es una afirmación de protección.
    return "NONE"


def is_open_lifecycle(state: object) -> bool:
    parsed = coerce_lifecycle_state(state)
    return parsed is not None and parsed not in _LIFECYCLE_INACTIVE_STATES
