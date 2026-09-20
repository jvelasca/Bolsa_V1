"""AUTO-1A / AUTO-1 — catálogo único de los reason codes de materialización, reserva y
no-gestión.

Un motivo de journal es un contrato de observabilidad: si el literal se escribe suelto en
varios sitios, deja de poder afirmarse nada sobre él (el audit-pack v2.40.4 ya trató
``TOP_N_EXCLUDED`` como "dueño del literal"). Este módulo es el dueño de los códigos que
introducen AUTO-1A y AUTO-1, junto a los ya existentes ``REGIME_EXIT``
(``position_manager``) y ``TOP_N_EXCLUDED`` (``opportunity_ranker``).

Tres familias:

* MATERIALIZACIÓN (AUTO-1A) — separan lo PEDIDO de lo APLICADO.
  ``fill_not_materialized``: la orden no movió dinero (ningún chunk aplicado).
  ``fill_partially_materialized``: parte de los chunks quedaron pendientes (``RETRY``) y
  solo lo aplicado es posición. ``exit_qty_over_position``: la venta aplicada excede la
  posición materializada (se declara y se aplana; jamás se inventa un corto).
* RESERVA (AUTO-1) — el ciclo de vida del compromiso. ``reservation_created``: la
  aprobación se materializó en reserva. ``reservation_released_fill`` /
  ``reservation_released_cancel`` / ``reservation_released_restart`` /
  ``reservation_released_rollback``: por qué dejó de consumir presupuesto.
  ``reservation_failed``: no se pudo reservar ⇒ la aprobación se degrada a veto (no existe
  aprobación sin reserva). ``reservation_unmeasurable``: el libro de reservas no es
  legible ⇒ aperturas vetadas (fail-closed). ``reservation_already_live``: ya hay una
  reserva viva para ese instrumento (de un tick anterior, aún sin fill) ⇒ no se apila un
  segundo compromiso sobre el mismo instrumento.
* NO-GESTIÓN (AUTO-1A) — el motor no pudo gestionar una posición viva. ``no_mark_data``:
  sin mark para ese instrumento en el tick. ``mark_rejected``: el ``PositionState`` rechazó
  el mark. ``decision_unavailable``: no se pudo construir la ``PositionDecision``.
* CICLO DE VIDA (AUTO-2) — el FSM explícito de la posición. Los literales de transición
  son dueño único de ``bolsa_analytics.cognitive.position_lifecycle`` (analytics no puede
  importar application: se re-exportan aquí para que el journal tenga una sola casa).
  ``stop_ratchet_applied`` / ``stop_ratchet_rejected``: el stop propuesto por un
  ``PROTECT`` se aplicó (o se rechazó por empeorar sin override auditado).
  ``protect_requested``: hubo intención de proteger sin efecto (nunca mudo).
  ``protection_missing`` / ``reconciliation_required`` / ``lifecycle_state_unverified``:
  la posición no tiene protección verificable y se declara, jamás se asume.

Ninguno de estos códigos es un "hold" silencioso: todos implican que hay algo que el
operador debe poder ver.

V2.42 slice 2c (cierre de `AUTO-2`) añade aquí la **etiqueta del día** del motivo de cierre
(`day_exit_reason`): el journal del día cuenta las salidas por su etiqueta
(`time_exit`/`thesis_exit`/`structural_stop`/...) y las que el decider cierra sin motivo de
protección se cuentan como `undeclared`, nunca como otra cosa.

V2.44 / AUTO-4 añade aquí los motivos del **optimizador de cartera** (``OPTIMIZER_REASONS``):
son la razón por la que una candidata del conjunto no entró en la combinación elegida
(``optimizer_not_selected`` o una infeasibilidad concreta) y la razón por la que el
optimizador no llegó a decidir (``optimizer_enumeration_cap_exceeded``). El literal vive en
``portfolio_optimizer`` (analytics) y se re-exporta aquí para el journal.
"""

from __future__ import annotations

from bolsa_analytics.cognitive.portfolio_optimizer import (
    OPTIMIZER_CAPITAL_EXCEEDED,
    OPTIMIZER_CORRELATION_EXCEEDED,
    OPTIMIZER_CORRELATION_UNKNOWN,
    OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK,
    OPTIMIZER_ENUMERATION_CAP_EXCEEDED,
    OPTIMIZER_EXPECTED_VALUE_UNMEASURED,
    OPTIMIZER_LIQUIDITY_BELOW_MINIMUM,
    OPTIMIZER_LIQUIDITY_UNKNOWN,
    OPTIMIZER_NOT_SELECTED,
    OPTIMIZER_NOTIONAL_UNMEASURED,
    OPTIMIZER_RISK_UNMEASURED,
    OPTIMIZER_SECTOR_EXCEEDED,
    OPTIMIZER_SECTOR_UNMEASURED,
)
from bolsa_analytics.cognitive.position_lifecycle import (
    LIFECYCLE_RESOLUTION_MISSING,
    LIFECYCLE_STATE_UNVERIFIED,
    LIFECYCLE_TRANSITION_REJECTED,
)

NO_MARK_DATA = "no_mark_data"
POSITION_MARK_REJECTED = "mark_rejected"
POSITION_DECISION_UNAVAILABLE = "decision_unavailable"
FILL_NOT_MATERIALIZED = "fill_not_materialized"
FILL_PARTIALLY_MATERIALIZED = "fill_partially_materialized"
EXIT_QTY_OVER_POSITION = "exit_qty_over_position"

# AUTO-1 — ciclo de vida de una reserva (el compromiso explícito de una aprobación).
RESERVATION_CREATED = "reservation_created"
RESERVATION_RELEASED_FILL = "reservation_released_fill"
RESERVATION_RELEASED_CANCEL = "reservation_released_cancel"
RESERVATION_RELEASED_RESTART = "reservation_released_restart"
RESERVATION_RELEASED_ROLLBACK = "reservation_released_rollback"
RESERVATION_FAILED = "reservation_failed"
RESERVATION_UNMEASURABLE = "reservation_unmeasurable"
# AUTO-1b — no se apila un segundo compromiso sobre un instrumento ya reservado.
RESERVATION_ALREADY_LIVE = "reservation_already_live"

# AUTO-2 — FSM de la posición: ratchet de stop y degradación de protección.
STOP_RATCHET_APPLIED = "stop_ratchet_applied"
STOP_RATCHET_REJECTED = "stop_ratchet_rejected"
PROTECT_REQUESTED = "protect_requested"
PROTECTION_MISSING = "protection_missing"
RECONCILIATION_REQUIRED = "reconciliation_required"

# V2.42 slice 2b — cierre del ciclo de vida completo (E1/E3) y procedencia del ATR (E2).
# Son los motivos con los que el worker declara POR QUÉ se pidió salir (el ``primary_reason``
# en minúsculas del plan de salida: ``time_stop``/``thesis_invalidation``) y DE DÓNDE salió la
# geometría de riesgo. Sin ellos, una salida por tiempo o por tesis sería indistinguible de
# un ``EXIT_REQUESTED`` genérico en el journal.
TIME_EXIT = "time_exit"
THESIS_EXIT = "thesis_exit"
ATR_GEOMETRY = "atr_geometry"
#: Valores de ``atrSource`` (procedencia del ATR que construyó la geometría).
ATR_SOURCE_REAL = "real"
ATR_SOURCE_FALLBACK = "fallback"
ATR_SOURCE_MISSING = "missing"
ATR_SOURCES: frozenset[str] = frozenset(
    {ATR_SOURCE_REAL, ATR_SOURCE_FALLBACK, ATR_SOURCE_MISSING}
)

#: Etiqueta del motivo de cierre para el journal del DÍA (``SimJournalRow.reason``).
#: El ``primary_reason`` del plan de salida (el MISMO que atribuye la salida en el journal
#: rico) se traduce aquí al vocabulario del día: ``TIME_STOP`` -> ``time_exit`` y
#: ``THESIS_INVALIDATION`` -> ``thesis_exit``. La traducción es por motivo DECISORIO, así
#: que un stop-out (``STRUCTURAL_STOP``) NO se disfraza de salida por tesis. Un motivo no
#: catalogado se declara en minúsculas tal cual: nunca se inventa una etiqueta.
DAY_EXIT_REASON_UNDECLARED = "undeclared"
_DAY_EXIT_REASON_BY_PRIMARY: dict[str, str] = {
    "TIME_STOP": TIME_EXIT,
    "THESIS_INVALIDATION": THESIS_EXIT,
    "STRUCTURAL_STOP": "structural_stop",
    "PORTFOLIO_RISK": "portfolio_risk",
    "TARGET_1": "target_1",
    "TARGET_2": "target_2",
    "TRAIL": "trail",
    "MANUAL": "manual",
    # V2.44 — exits del gobernador: el día distingue una liquidación de riesgo
    # (``RISK_EXIT``), una salida por régimen (``REGIME_EXIT``) y un halt
    # (``KILL_SWITCH``) de un stop o de un objetivo. Sin estas entradas el motivo
    # quedaría en minúsculas por defecto y el agregado del día lo perdería.
    "RISK_EXIT": "risk_exit",
    "REGIME_EXIT": "regime_exit",
    "KILL_SWITCH": "kill_switch",
}


def day_exit_reason(primary_reason: str | None) -> str:
    """Etiqueta del día para el motivo de cierre (``""`` si no hay motivo decisorio)."""
    raw = str(primary_reason or "").strip()
    if not raw:
        return ""
    key = raw.upper()
    return _DAY_EXIT_REASON_BY_PRIMARY.get(key, key.lower())


# Motivos con los que ``PositionManagerSkip`` declara una gestión no realizada.
POSITION_SKIP_REASONS: frozenset[str] = frozenset(
    {POSITION_MARK_REJECTED, POSITION_DECISION_UNAVAILABLE}
)

# Motivos de materialización: la orden no quedó contabilizada como posición.
MATERIALIZATION_REASONS: frozenset[str] = frozenset(
    {FILL_NOT_MATERIALIZED, FILL_PARTIALLY_MATERIALIZED, EXIT_QTY_OVER_POSITION}
)

# AUTO-1 — motivos del ciclo de vida de una reserva.
RESERVATION_REASONS: frozenset[str] = frozenset(
    {
        RESERVATION_CREATED,
        RESERVATION_RELEASED_FILL,
        RESERVATION_RELEASED_CANCEL,
        RESERVATION_RELEASED_RESTART,
        RESERVATION_RELEASED_ROLLBACK,
        RESERVATION_FAILED,
        RESERVATION_UNMEASURABLE,
        RESERVATION_ALREADY_LIVE,
    }
)

# AUTO-2 — motivos del FSM de la posición (ratchet, protección y degradación).
POSITION_LIFECYCLE_REASONS: frozenset[str] = frozenset(
    {
        STOP_RATCHET_APPLIED,
        STOP_RATCHET_REJECTED,
        PROTECT_REQUESTED,
        PROTECTION_MISSING,
        RECONCILIATION_REQUIRED,
        LIFECYCLE_TRANSITION_REJECTED,
        LIFECYCLE_STATE_UNVERIFIED,
        LIFECYCLE_RESOLUTION_MISSING,
        TIME_EXIT,
        THESIS_EXIT,
        ATR_GEOMETRY,
    }
)

# V2.44/AUTO-4 — motivos del optimizador de cartera: por qué una candidata del conjunto no
# entró en la combinación elegida (``optimizer_not_selected`` o una infeasibilidad concreta)
# o por qué el optimizador no llegó a decidir (``optimizer_enumeration_cap_exceeded``).
OPTIMIZER_REASONS: frozenset[str] = frozenset(
    {
        OPTIMIZER_NOT_SELECTED,
        OPTIMIZER_EXPECTED_VALUE_UNMEASURED,
        OPTIMIZER_NOTIONAL_UNMEASURED,
        OPTIMIZER_RISK_UNMEASURED,
        OPTIMIZER_CORRELATION_UNKNOWN,
        OPTIMIZER_CORRELATION_EXCEEDED,
        OPTIMIZER_LIQUIDITY_UNKNOWN,
        OPTIMIZER_LIQUIDITY_BELOW_MINIMUM,
        OPTIMIZER_CAPITAL_EXCEEDED,
        OPTIMIZER_SECTOR_UNMEASURED,
        OPTIMIZER_SECTOR_EXCEEDED,
        OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK,
        OPTIMIZER_ENUMERATION_CAP_EXCEEDED,
    }
)

__all__ = [
    "ATR_GEOMETRY",
    "ATR_SOURCES",
    "ATR_SOURCE_FALLBACK",
    "ATR_SOURCE_MISSING",
    "ATR_SOURCE_REAL",
    "DAY_EXIT_REASON_UNDECLARED",
    "EXIT_QTY_OVER_POSITION",
    "FILL_NOT_MATERIALIZED",
    "FILL_PARTIALLY_MATERIALIZED",
    "LIFECYCLE_RESOLUTION_MISSING",
    "LIFECYCLE_STATE_UNVERIFIED",
    "LIFECYCLE_TRANSITION_REJECTED",
    "MATERIALIZATION_REASONS",
    "NO_MARK_DATA",
    "OPTIMIZER_CAPITAL_EXCEEDED",
    "OPTIMIZER_CORRELATION_EXCEEDED",
    "OPTIMIZER_CORRELATION_UNKNOWN",
    "OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK",
    "OPTIMIZER_ENUMERATION_CAP_EXCEEDED",
    "OPTIMIZER_EXPECTED_VALUE_UNMEASURED",
    "OPTIMIZER_LIQUIDITY_BELOW_MINIMUM",
    "OPTIMIZER_LIQUIDITY_UNKNOWN",
    "OPTIMIZER_NOT_SELECTED",
    "OPTIMIZER_NOTIONAL_UNMEASURED",
    "OPTIMIZER_REASONS",
    "OPTIMIZER_RISK_UNMEASURED",
    "OPTIMIZER_SECTOR_EXCEEDED",
    "OPTIMIZER_SECTOR_UNMEASURED",
    "POSITION_DECISION_UNAVAILABLE",
    "POSITION_LIFECYCLE_REASONS",
    "POSITION_MARK_REJECTED",
    "POSITION_SKIP_REASONS",
    "PROTECTION_MISSING",
    "PROTECT_REQUESTED",
    "RECONCILIATION_REQUIRED",
    "RESERVATION_ALREADY_LIVE",
    "RESERVATION_CREATED",
    "RESERVATION_FAILED",
    "RESERVATION_REASONS",
    "RESERVATION_RELEASED_CANCEL",
    "RESERVATION_RELEASED_FILL",
    "RESERVATION_RELEASED_RESTART",
    "RESERVATION_RELEASED_ROLLBACK",
    "RESERVATION_UNMEASURABLE",
    "STOP_RATCHET_APPLIED",
    "STOP_RATCHET_REJECTED",
    "THESIS_EXIT",
    "TIME_EXIT",
    "day_exit_reason",
]
