"""M15: una ampliación mezcla el coste de entrada (coste medio ponderado).

El P&L realizado se mide contra UNA referencia (``_entry_price``, la misma que usa la
protección) y esa referencia es la que la ampliación mezcla. Aquí se fija la aritmética
del coste y la invariante de que una venta (parcial o total) NO reescribe la base de
coste: si la reescribiera, el P&L de las ventas siguientes se mediría contra otro precio
y la serie de drawdown dejaría de ser comparable.
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_api.background.auto_simulation_worker import _blend_entry_price


def test_add_blends_to_weighted_average() -> None:
    blended = _blend_entry_price(Decimal("100"), Decimal("100"), Decimal("110"), Decimal("100"))
    assert blended == Decimal("105")


def test_weights_follow_quantities() -> None:
    blended = _blend_entry_price(Decimal("100"), Decimal("300"), Decimal("120"), Decimal("100"))
    assert blended == Decimal("105")


def test_zero_total_keeps_prior() -> None:
    assert _blend_entry_price(Decimal("100"), Decimal("0"), Decimal("120"), Decimal("0")) == Decimal(
        "100"
    )


def test_pnl_of_a_blended_position_is_measured_against_the_weighted_cost() -> None:
    """100@100 + 100@110 ⇒ coste 105; vender 200@115 son 2.000, no los 3.000 del primer fill."""
    cost = _blend_entry_price(Decimal("100"), Decimal("100"), Decimal("110"), Decimal("100"))
    realized = (Decimal("115") - cost) * Decimal("200")
    assert realized == Decimal("2000"), f"el P&L debe usar el coste medio, no la 1ª entrada: {realized}"


def test_repeated_adds_converge_to_the_true_average() -> None:
    """Tres ampliaciones, aplicadas una a una, dan el mismo promedio que el cálculo directo."""
    cost = Decimal("100")
    held = Decimal("0")
    for price, qty in ((Decimal("100"), Decimal("100")), (Decimal("110"), Decimal("100"))):
        cost = _blend_entry_price(cost, held, price, qty)
        held += qty
    cost = _blend_entry_price(cost, held, Decimal("120"), Decimal("200"))
    # (100*100 + 110*100 + 120*200) / 400 = 45.000/400 = 112,5.
    assert cost == Decimal("112.5"), cost
