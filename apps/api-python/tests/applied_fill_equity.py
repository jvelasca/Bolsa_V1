"""P&L cerrado del día desde fills APLICADOS (AUTO-1A · P0.6).

El contexto financiero (``sim_fill_finance_context``) se persiste para TODOS los fills
PLANIFICADOS **antes** de mover dinero (``persist_fill_finance_context``); su suma
completa, por tanto, contabiliza chunks que quedaron en ``CAPTURED`` / ``APPLYING`` /
``RETRY`` / ``FAILED`` (dinero NO movido). Ese hueco hacía descuadrar el invariante de
equity de forma **intermitente**, dependiendo de si el tick dejó cola pendiente.

La única fuente de verdad del realizado es ``execution_events.status = 'APPLIED'`` (la
identidad financiera del fill). La cantidad sale del EVENTO; el lado y el precio, del
contexto. Si a un fill aplicado le falta contexto, o la cantidad del evento y la del
contexto no cuadran, el realizado **no es afirmable**: la función lo declara con
``AssertionError`` (fail-closed) en vez de aproximar y dejar pasar el invariante por
casualidad.

Compartido por las suites PG de jornada completa
(``test_auto_scheduler_real_pg_zero_human_intervention`` y
``test_a9_scheduler_process_pg_zero_human``) para que las dos midan el MISMO número.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select

from bolsa_infrastructure.database.models.tables import (
    ExecutionEventRow,
    SimFillFinanceContextRow,
)

# Tolerancia de comparación evento↔contexto (NUMERIC(18,6) en ambas columnas).
_QTY_EPS = Decimal("0.000001")

#: Quantum del DINERO (``NUMERIC(18, 6)`` en ``transactions.total``/``ledger_entries.amount``).
#: Cada fill mueve ``round6(qty × price)``, no el producto de 12 decimales.
_MONEY_SCALE = Decimal("0.000001")


def _money(value: Decimal) -> Decimal:
    """Redondeo del dinero a su quantum, como lo hace PostgreSQL ``NUMERIC(18, 6)``.

    ``ROUND_HALF_UP`` es el redondeo de Postgres (mitad fuera de cero); el default de
    ``Decimal.quantize`` (``ROUND_HALF_EVEN``) discreparía en el caso — improbable pero
    posible— de que el producto caiga justo en la mitad del sexto decimal.
    """
    return value.quantize(_MONEY_SCALE, rounding=ROUND_HALF_UP)


async def realized_notional_from_applied_fills(session: Any, account_id: str) -> Decimal:
    """Neto de notionales de los fills **aplicados** de la cuenta (P&L cerrado del día).

    En un libro plano (sin inventario vivo) este neto ES el resultado realizado: es la
    fuente independiente del ``cash`` que exige ``assert_equity_invariant``.

    Fail-closed: un fill ``APPLIED`` sin contexto financiero, o con cantidad divergente
    entre evento y contexto, no se ignora — se declara (el test debe ponerse rojo, no
    pasar con un número aproximado).
    """
    events = (
        (
            await session.execute(
                select(ExecutionEventRow.execution_id, ExecutionEventRow.qty).where(
                    ExecutionEventRow.account_id == account_id,
                    ExecutionEventRow.status == "APPLIED",
                )
            )
        )
        .all()
    )
    applied: dict[str, Decimal] = {}
    for execution_id, qty in events:
        if qty is None:
            continue
        applied[str(execution_id)] = Decimal(str(qty))

    contexts = (
        (
            await session.execute(
                select(
                    SimFillFinanceContextRow.execution_id,
                    SimFillFinanceContextRow.side,
                    SimFillFinanceContextRow.quantity,
                    SimFillFinanceContextRow.price,
                ).where(SimFillFinanceContextRow.account_id == account_id)
            )
        )
        .all()
    )

    by_id = {str(row[0]): row for row in contexts}
    closed_pnl = Decimal("0")
    for execution_id, qty in sorted(applied.items()):
        row = by_id.get(execution_id)
        assert row is not None, (
            f"fill APPLIED sin contexto financiero: {execution_id} "
            "(el realizado no es medible)"
        )
        _ctx_id, side, ctx_quantity, price = row
        assert ctx_quantity is not None and price is not None, (
            f"contexto financiero ilegible para el fill aplicado {execution_id}"
        )
        context_qty = Decimal(str(ctx_quantity))
        assert abs(context_qty - qty) <= _QTY_EPS, (
            f"cantidad divergente entre execution_events ({qty}) y contexto "
            f"({context_qty}) para {execution_id}"
        )
        # El notional se mide con el QUANTUM DEL DINERO, fill a fill, no con la aritmética
        # de 12 decimales de ``qty × price``: el ledger aplica ``cash ± (qty × price)`` sobre
        # una columna ``NUMERIC(18, 6)`` (``ledger_entries.amount``/``transactions.total``),
        # así que cada fill mueve su notional redondeado. Sumar en 12 decimales y comparar
        # contra un ledger de 6 deja un residuo de hasta 5e-7 por fill (≈2e-6 medidos en una
        # jornada de precio real con tamaño fraccionario) que NO es una fuga de dinero sino
        # aritmética de precisión distinta: el invariante de equity (tol 1e-6) se ponía rojo
        # por ella. Medido así certifica el dinero al último decimal representable y sigue
        # siendo una fuente INDEPENDIENTE del ``cash`` (sale de los eventos + contexto, no de
        # las filas del ledger).
        notional = _money(qty * Decimal(str(price)))
        closed_pnl += notional if (side or "").strip().lower() == "sell" else -notional

    # Un contexto SIN fill aplicado es capital planificado (RETRY): no es realizado y
    # no debe entrar en el invariante (ese era exactamente el hueco intermitente).
    return closed_pnl


__all__ = ["realized_notional_from_applied_fills"]
