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
"""

from __future__ import annotations

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
    }
)

__all__ = [
    "EXIT_QTY_OVER_POSITION",
    "FILL_NOT_MATERIALIZED",
    "FILL_PARTIALLY_MATERIALIZED",
    "LIFECYCLE_RESOLUTION_MISSING",
    "LIFECYCLE_STATE_UNVERIFIED",
    "LIFECYCLE_TRANSITION_REJECTED",
    "MATERIALIZATION_REASONS",
    "NO_MARK_DATA",
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
]
