"""AUTO-16 (V2.57) — el contexto del fill guarda la REFERENCIA con la que se construyó.

Test hermético del espejo durable (``InMemorySimFillFinanceContextStore``, el mismo Protocol
que el store Postgres): no toca PostgreSQL, fija la SEMÁNTICA que la fricción APLICADA necesita
después. Tres hechos, y ninguno es cosmético:

1. La referencia **viaja con el fill** y se puede leer **por ciclo** —incluida la pata de ENTRADA
   liquidada en otro tick—, que es lo que un reinicio perdería si viviera en memoria.
2. Un ciclo sin filas (o un fill sin ciclo) **no** casa: el hueco lo declara el llamante, no se
   rellena con una fricción de ceros.
3. Una referencia inservible (``0``, negativa, ``NaN``, ausente) se declara **sin referencia**:
   nunca un ``0``, que diría "fricción gratis" y regalaría R.

Y una cuarta, que es la misma lección de `AUTO-15`: una fila de **otra cuenta** no puede aportar
la fricción de este ciclo.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)

_ACCOUNT = "acc-1"
_OTHER_ACCOUNT = "acc-2"
_CYCLE = "cyc-abc"
_OTHER_CYCLE = "cyc-xyz"
_ENGINE = "auto-sim"


def _context(
    execution_id: str,
    *,
    side: str = "buy",
    price: str = "100.15",
    quantity: str = "10",
    reference_mid: object = "100",
    cycle_id: str | None = _CYCLE,
    account_id: str | None = _ACCOUNT,
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        reference_mid=reference_mid if reference_mid is None else Decimal(str(reference_mid)),
        account_id=account_id,
        venue="simulated",
        cycle_id=cycle_id,
    )


@pytest.mark.asyncio
async def test_the_reference_survives_the_store_and_is_read_back_by_cycle() -> None:
    """Las DOS patas del ciclo se leen juntas, y cada una con SU referencia.

    Es la costura que hace medible la fricción aplicada: la entrada se liquidó en otro tick
    (posiblemente otro proceso) y sin esta lectura solo se mediría media fricción.
    """
    store = InMemorySimFillFinanceContextStore()
    await store.save(_context("venue#1", side="buy", price="100.15", reference_mid="100"))
    await store.save(_context("venue#2", side="sell", price="99.90", reference_mid="100"))

    rows = await store.list_by_cycle_ids(_ACCOUNT, [_CYCLE])

    assert [row.execution_id for row in rows] == ["venue#1", "venue#2"]
    assert [row.reference_mid for row in rows] == [Decimal("100"), Decimal("100")]
    assert [row.side for row in rows] == ["buy", "sell"]


@pytest.mark.asyncio
async def test_a_cycle_without_rows_is_an_absent_cycle_not_a_zeroed_one() -> None:
    """Un ciclo sin filas ⇒ ``[]``: el hueco lo declara quien lee, no se rellena de ceros."""
    store = InMemorySimFillFinanceContextStore()
    await store.save(_context("venue#1"))

    assert await store.list_by_cycle_ids(_ACCOUNT, [_OTHER_CYCLE]) == []
    # Sin ciclos pedidos no se consulta nada (ni se inventa un resultado vacío de rebote).
    assert await store.list_by_cycle_ids(_ACCOUNT, []) == []


@pytest.mark.asyncio
async def test_a_fill_without_cycle_never_matches_a_requested_cycle() -> None:
    """Una fila sin ``cycle_id`` (anterior a 2.47) no casa nunca: "sin ciclo" no es un ciclo."""
    store = InMemorySimFillFinanceContextStore()
    await store.save(_context("venue#nocycle", cycle_id=None))

    assert await store.list_by_cycle_ids(_ACCOUNT, [_CYCLE]) == []


@pytest.mark.asyncio
async def test_a_fill_of_another_account_never_pays_for_this_cycle() -> None:
    """La lectura se acota por cuenta: la fricción de otro libro no entra en este ciclo.

    Sin el filtro, dos cuentas con el mismo nombre de ciclo se contaminarían la medida —y la
    contaminación sería invisible, porque el número seguiría "pareciendo" una fricción.
    """
    store = InMemorySimFillFinanceContextStore()
    await store.save(_context("venue#mine"))
    await store.save(_context("venue#theirs", account_id=_OTHER_ACCOUNT, reference_mid="50"))

    rows = await store.list_by_cycle_ids(_ACCOUNT, [_CYCLE])

    assert [row.execution_id for row in rows] == ["venue#mine"]


@pytest.mark.parametrize("reference", [None, "0", "-1", "NaN"])
def test_an_unusable_reference_is_declared_absent_and_never_a_zero(reference: object) -> None:
    """Un mid que no es un precio se declara AUSENTE: ``0`` diría "fricción gratis"."""
    row = SimFillFinanceContext(
        execution_id="venue#1",
        instrument_id="AAA",
        side="buy",
        quantity=Decimal("10"),
        price=Decimal("100.15"),
        reference_mid=None if reference is None else Decimal(str(reference)),
        account_id=_ACCOUNT,
        venue="simulated",
        cycle_id=_CYCLE,
    )

    assert row.reference_mid is None


def test_a_usable_reference_is_normalized_to_decimal() -> None:
    """La misma referencia no viaja con dos tipos: un ``float`` válido entra como ``Decimal``."""
    row = SimFillFinanceContext(
        execution_id="venue#1",
        instrument_id="AAA",
        side="buy",
        quantity=Decimal("10"),
        price=Decimal("100.15"),
        reference_mid=100.0,  # type: ignore[arg-type]
        account_id=_ACCOUNT,
        venue="simulated",
        cycle_id=_CYCLE,
    )

    assert row.reference_mid == Decimal("100")
    assert isinstance(row.reference_mid, Decimal)
