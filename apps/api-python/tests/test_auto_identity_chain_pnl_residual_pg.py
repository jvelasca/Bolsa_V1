"""El dinero del ciclo, medido sobre el ciclo REAL: cuantización por fill y su residuo.

Este nodo verifica el contrato de ADR-051 sobre un ciclo cerrado por el camino productivo:

    pnl publicado = Σ signo_i · round6(q_i·p_i)   (lo que movió el libro)
    pnl exacto    = FIFO de siempre
    libro − exacto = Σ signo_i · ( round6(q_i·p_i) − q_i·p_i )

Es decir: el libro aplicado mueve ``round6(q×p)`` **fill a fill** (cada columna monetaria es
``NUMERIC(18, 6)``) mientras el FIFO del ciclo suma exacto. Bajo la política vigente el número
PUBLICADO es el del libro —igualdad exacta, sin tolerancia— y el FIFO exacto viaja aparte para
que el residuo siga siendo medible y ninguna fuga pueda disfrazarse de redondeo.

Se reutiliza el arnés de la batería de identidad (``_drive_cycle``/``_teardown``) para no
duplicar el motor ni sembrar hechos a mano: si el arnés cambia, este nodo mide el cambio.

Cuatro aserciones, todas con dientes:

1. el PnL aplicado cuadra **EXACTO** con el libro aplicado (la igualdad que el defecto rompía);
2. la identidad aritmética exacta entre libro, ``pnlExact`` y los residuos por fill;
3. una divergencia libro↔exacto solo es admisible si existe residuo que la explique (un
   hueco con residuo cero sería una FUGA de dinero, no aritmética de precisión);
4. la cota declarada (``≤ n × 5e-7``) que impide citar una tolerancia fija de un quantum.

Y una declaración de política: el hecho durable y el ciclo dicen con qué aritmética se midieron.
"""

from __future__ import annotations

import asyncio
import sys
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.cycle_pnl_policy import CYCLE_PNL_POLICY

# Arnés del MISMO camino productivo (no se duplica el motor ni la siembra). La fixture de BD
# se importa para que la conexión, la migración y el gate de skip/fail sean los de la
# batería de identidad y no una copia que pueda divergir.
from tests.test_auto_identity_chain_battery_pg import (
    _IDENTITY_SOURCE,
    _drive_cycle,
    _only_cycle,
    _read_evidence,
    _teardown,
    identity_pg_factory,  # noqa: F401 — fixture: se solicita por su NOMBRE
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: Quantum del DINERO (``NUMERIC(18, 6)`` en ``ledger_entries``/``transactions``/``accounts``).
_MONEY = Decimal("0.000001")
#: Media unidad del quantum: el residuo máximo de UN fill (redondeo al más cercano).
_HALF_QUANTUM = _MONEY / 2


def _money(value: Decimal) -> Decimal:
    """Redondeo del dinero a su quantum, como PostgreSQL ``NUMERIC(18, 6)``."""
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


async def _cycle_fills(
    factory: async_sessionmaker[AsyncSession], *, account_id: str, cycle_id: str
) -> list[tuple[str, Decimal, Decimal]]:
    """``(side, quantity, price)`` de los fills APLICADOS del ciclo, en orden durable.

    Se filtra por ``status = 'APPLIED'`` porque esa es la única fuente de verdad del
    realizado (un contexto sin fill aplicado es capital planificado, no dinero movido) y por
    ``cycle_id`` porque la columna se sella en el settle (migración 044); sin sello el nodo
    declara el hueco en vez de adivinar vecinos por fecha.
    """
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        rows = (
            await session.execute(
                select(
                    SimFillFinanceContextRow.side,
                    SimFillFinanceContextRow.quantity,
                    SimFillFinanceContextRow.price,
                )
                .join(
                    ExecutionEventRow,
                    ExecutionEventRow.execution_id == SimFillFinanceContextRow.execution_id,
                )
                .where(
                    SimFillFinanceContextRow.account_id == account_id,
                    SimFillFinanceContextRow.cycle_id == cycle_id,
                    ExecutionEventRow.status == "APPLIED",
                )
                .order_by(
                    SimFillFinanceContextRow.created_at,
                    SimFillFinanceContextRow.execution_id,
                )
            )
        ).all()
    return [
        (str(side).strip().lower(), Decimal(str(quantity)), Decimal(str(price)))
        for side, quantity, price in rows
    ]


def _residual_rows(
    fills: list[tuple[str, Decimal, Decimal]],
) -> list[dict[str, Any]]:
    """Residuo de cuantización POR FILL, con el signo con el que entra en el libro.

    ``signedResidual = +r`` en una venta y ``−r`` en una compra: así la suma de la columna
    es exactamente ``libro − ciclo`` cuando el libro queda plano.
    """
    rows: list[dict[str, Any]] = []
    for side, quantity, price in fills:
        product = quantity * price
        residual = _money(product) - product
        rows.append(
            {
                "side": side,
                "quantity": quantity,
                "price": price,
                "product": product,
                "applied": _money(product),
                "signedResidual": residual if side == "sell" else -residual,
            }
        )
    return rows


def _residual_table(rows: list[dict[str, Any]]) -> str:
    """Tabla por fill para el mensaje de fallo (sin ella, el rojo no dice dónde mirar)."""
    lines = ["  lado    cantidad        precio          q*p                    round6(q*p)     residuo"]
    for row in rows:
        lines.append(
            f"  {row['side']:<6}  {row['quantity']:>14}  {row['price']:>14}  "
            f"{row['product']:>22}  {row['applied']:>14}  {row['signedResidual']:>+14}"
        )
    return "\n".join(lines)


async def _assert_residual_identity(
    factory: async_sessionmaker[AsyncSession], state: dict[str, Any]
) -> None:
    """Identidad libro ↔ ciclo ↔ residuos, sobre el ciclo todavía durable."""
    from tests.applied_fill_equity import realized_notional_from_applied_fills

    account_id = state["accountId"]
    engine_id = state["engineId"]
    instrument_id = state["instrumentId"]
    cycle_id = state["cycleId"]

    artifact = await _read_evidence(
        factory,
        account_id=account_id,
        engine_id=engine_id,
        study_instruments=[instrument_id],
    )
    cycle = await _only_cycle(artifact, instrument_id)
    pnl = cycle["pnl"]

    # El producto declara conciliado el ciclo contra el settlement: son dos derivados de la
    # MISMA autoridad, por eso la garantía es de consistencia de publicación. Se afirma para
    # fijar ese hecho, no para avalarlo.
    assert pnl["reconciled"] is True, pnl
    assert pnl["cycleClosedPnl"] is not None and pnl["settlementPnl"] is not None, pnl
    # ADR-051 — bajo la política vigente el dinero publicado ES el del libro. La magnitud de
    # atribución (FIFO exacto) viaja aparte para poder seguir midiendo el residuo.
    assert pnl["policy"] == CYCLE_PNL_POLICY, pnl
    assert pnl["settlementPolicy"] == CYCLE_PNL_POLICY, pnl
    assert pnl["cycleExactPnl"] is not None, (
        "sin la magnitud exacta el residuo no es medible: el nodo no puede afirmar nada"
    )

    fills = await _cycle_fills(factory, account_id=account_id, cycle_id=cycle_id)
    assert fills, (
        "el ciclo cerrado debe tener fills APLICADOS con su cycle_id sellado; sin ellos la "
        "identidad no es medible y el nodo no puede afirmar nada"
    )

    bought = sum((row[1] for row in fills if row[0] == "buy"), Decimal("0"))
    sold = sum((row[1] for row in fills if row[0] == "sell"), Decimal("0"))
    assert bought == sold, (
        "la identidad exige libro PLANO (toda la cantidad emparejada): con inventario vivo "
        f"el coste abierto entraría sin venta. comprado={bought} vendido={sold}"
    )

    async with factory() as session:
        ledger = await realized_notional_from_applied_fills(session, account_id)

    cycle_published = Decimal(str(pnl["cycleClosedPnl"]))
    cycle_exact = Decimal(str(pnl["cycleExactPnl"]))
    rows = _residual_rows(fills)
    expected = sum((row["signedResidual"] for row in rows), Decimal("0"))

    # (1) El DINERO publicado no tolera diferencia: es exactamente lo que movió el libro.
    assert ledger == cycle_published, (
        "el P&L aplicado del ciclo debe cuadrar EXACTO con el libro aplicado (sin tolerancia):\n"
        f"  libro={ledger}  pnl publicado={cycle_published}  hueco={ledger - cycle_published}\n"
        f"{_residual_table(rows)}"
    )

    # (2) El residuo sigue siendo medible contra la magnitud de ATRIBUCIÓN: si el hueco no es
    # exactamente la suma de los redondeos por fill, hay una causa que este diagnóstico no cubre.
    assert ledger - cycle_exact == expected, (
        "el hueco libro↔ciclo exacto debe ser EXACTAMENTE la suma de los residuos de "
        "cuantización por fill (si no, hay una causa distinta que este diagnóstico no cubre):\n"
        f"  libro={ledger}  exacto={cycle_exact}  hueco={ledger - cycle_exact}\n"
        f"  Σ residuos={expected}\n{_residual_table(rows)}"
    )

    # (3) Un hueco SOLO se admite si hay residuo que lo explique: con residuo cero el libro
    # estaría perdiendo o ganando dinero, que es un defecto de otra naturaleza.
    assert ledger == cycle_exact or expected != 0, (
        "un libro distinto del ciclo con residuo CERO no es aritmética de precisión: es una "
        f"fuga. libro={ledger} exacto={cycle_exact}"
    )

    # (4) Cota declarada: el hueco NO se acota con un quantum fijo, sino con medio quantum por
    # fill. Una tolerancia de «1 quantum» sobre los totales quedaría corta en una jornada
    # con muchos tramos.
    assert abs(ledger - cycle_exact) <= _HALF_QUANTUM * len(fills), (
        f"el hueco ({ledger - cycle_exact}) supera medio quantum por fill "
        f"({len(fills)} fills): hay algo más que redondeo"
    )


@pytest.mark.asyncio
async def test_the_sub_cent_residual_is_the_quantization_of_each_fill_pg(
    identity_pg_factory: async_sessionmaker[AsyncSession],  # noqa: F811 — fixture del arnés
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ciclo productivo completo ⇒ el hueco libro↔ciclo queda descompuesto fill a fill.

    El prefijo es el de la batería de identidad a propósito: ``_filling_instrument_id`` es
    determinista por día, así que reutilizarlo reproduce el MISMO instrumento sintético, el
    MISMO troceado y el MISMO residuo que el nodo rojo (medido: ``libro=-29.248900`` frente
    a ``ciclo=-29.248900720000``, hueco de ``7,2e-7`` en dos fills de venta). Los dos nodos
    no comparten estado —cada uno siembra y limpia su cuenta e instrumento— y la suite no
    corre en paralelo.
    """
    state = await _drive_cycle(
        identity_pg_factory,
        monkeypatch,
        source=_IDENTITY_SOURCE,
        prefix="inst-idch-",
    )
    try:
        await _assert_residual_identity(identity_pg_factory, state)
    finally:
        await _teardown(identity_pg_factory, state)
