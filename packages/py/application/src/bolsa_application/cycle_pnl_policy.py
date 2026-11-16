"""ADR-051 — política de cuantización del DINERO del ciclo (vocabulario y aritmética).

Qué fija este módulo, y por qué vive aparte
-------------------------------------------
El libro aplicado mueve ``round6(q × p)`` **fill a fill** porque todas sus columnas monetarias
son ``NUMERIC(18, 6)`` (``ledger_entries.amount``/``transactions.total``/``accounts.cash``). El
FIFO del ciclo, en cambio, suma ``(salida − entrada) × cantidad`` en aritmética exacta y solo se
cuantizaba al publicar. Esa asimetría producía un hueco de menos de un quantum por movimiento::

    libro − ciclo = Σ signo_i · ( round6(q_i·p_i) − q_i·p_i )

El contrato vigente (**A1**, ADR-051) elige la magnitud que el dinero **de verdad** mueve: el
``pnl`` publicado de un ciclo es la suma de sus movimientos ya cuantizados. El FIFO exacto NO se
elimina —viaja como ``pnlExact``— porque es lo que permite atribuir qué compra casó con qué venta
y seguir demostrando la identidad del residuo.

Vocabulario (una cosa, un nombre):

* ``applied_per_fill_v1`` — política vigente. ``pnl`` = ``Σ signo · round6(q·p)`` de los fills
  emparejados del ciclo.
* ``fifo_exact_v0`` — política histórica (o un hecho anterior a este contrato): ``pnl`` = FIFO
  exacto, cuantizado solo al publicar. Un hecho que NO declara política se lee así, porque eso es
  lo que de verdad hizo.

Los dos consumidores duros de este vocabulario son el hecho durable de settlement (``pnlPolicy``
en el payload, y la clave de deduplicación versionada) y los lectores que deciden si un cierre es
el VIGENTE o está superado.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

__all__ = [
    "CYCLE_PNL_POLICY",
    "CYCLE_PNL_POLICY_LEGACY",
    "MONEY_QUANTUM",
    "declared_policy",
    "is_current_policy",
    "money",
]

#: Política VIGENTE: el dinero del ciclo es la suma de sus movimientos cuantizados.
CYCLE_PNL_POLICY = "applied_per_fill_v1"
#: Política HISTÓRICA: FIFO exacto cuantizado al publicar (hechos sin ``pnlPolicy``).
CYCLE_PNL_POLICY_LEGACY = "fifo_exact_v0"

#: Quantum del DINERO: ``NUMERIC(18, 6)`` en todas las columnas monetarias del ledger.
MONEY_QUANTUM = Decimal("0.000001")


def money(value: Decimal) -> Decimal:
    """Redondeo del dinero a su quantum, como PostgreSQL ``NUMERIC(18, 6)``.

    ``ROUND_HALF_UP`` es el redondeo de Postgres (mitad fuera de cero): replicarlo es lo que
    permite afirmar la igualdad EXACTA con el libro aplicado en vez de tolerarla.
    """
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def declared_policy(value: Any) -> str:
    """Política que el hecho DECLARA; sin declaración es la histórica (no se adivina).

    Un payload anterior a ADR-051 no lleva ``pnlPolicy``: afirmar que es la vigente sería
    atribuirle un contrato que no cumplió. La ausencia se lee como ``fifo_exact_v0``.
    """
    text = str(value).strip() if isinstance(value, str) else ""
    return text or CYCLE_PNL_POLICY_LEGACY


def is_current_policy(value: Any) -> bool:
    """``True`` solo si el hecho declara la política VIGENTE (la ausencia NO lo es)."""
    return declared_policy(value) == CYCLE_PNL_POLICY
