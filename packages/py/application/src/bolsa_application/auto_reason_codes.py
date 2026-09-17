"""AUTO-1A — catálogo único de los reason codes de materialización y no-gestión.

Un motivo de journal es un contrato de observabilidad: si el literal se escribe suelto en
varios sitios, deja de poder afirmarse nada sobre él (el audit-pack v2.40.4 ya trató
``TOP_N_EXCLUDED`` como "dueño del literal"). Este módulo es el dueño de los códigos que
introduce AUTO-1A, junto a los ya existentes ``REGIME_EXIT`` (``position_manager``) y
``TOP_N_EXCLUDED`` (``opportunity_ranker``).

Dos familias:

* MATERIALIZACIÓN — separan lo PEDIDO de lo APLICADO. ``fill_not_materialized``: la
  orden no movió dinero (ningún chunk aplicado). ``fill_partially_materialized``: parte
  de los chunks quedaron pendientes (``RETRY``) y solo lo aplicado es posición.
  ``exit_qty_over_position``: la venta aplicada excede la posición materializada (se
  declara y se aplana; jamás se inventa un corto).
* NO-GESTIÓN — el motor no pudo gestionar una posición viva. ``no_mark_data``: sin mark
  para ese instrumento en el tick. ``mark_rejected``: el ``PositionState`` rechazó el
  mark. ``decision_unavailable``: no se pudo construir la ``PositionDecision``.

Ninguno de estos códigos es un "hold" silencioso: todos implican que hay algo que el
operador debe poder ver.
"""

from __future__ import annotations

NO_MARK_DATA = "no_mark_data"
POSITION_MARK_REJECTED = "mark_rejected"
POSITION_DECISION_UNAVAILABLE = "decision_unavailable"
FILL_NOT_MATERIALIZED = "fill_not_materialized"
FILL_PARTIALLY_MATERIALIZED = "fill_partially_materialized"
EXIT_QTY_OVER_POSITION = "exit_qty_over_position"

# Motivos con los que ``PositionManagerSkip`` declara una gestión no realizada.
POSITION_SKIP_REASONS: frozenset[str] = frozenset(
    {POSITION_MARK_REJECTED, POSITION_DECISION_UNAVAILABLE}
)

# Motivos de materialización: la orden no quedó contabilizada como posición.
MATERIALIZATION_REASONS: frozenset[str] = frozenset(
    {FILL_NOT_MATERIALIZED, FILL_PARTIALLY_MATERIALIZED, EXIT_QTY_OVER_POSITION}
)

__all__ = [
    "EXIT_QTY_OVER_POSITION",
    "FILL_NOT_MATERIALIZED",
    "FILL_PARTIALLY_MATERIALIZED",
    "MATERIALIZATION_REASONS",
    "NO_MARK_DATA",
    "POSITION_DECISION_UNAVAILABLE",
    "POSITION_MARK_REJECTED",
    "POSITION_SKIP_REASONS",
]
