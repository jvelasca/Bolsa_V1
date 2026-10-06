"""TST-02 — la admisión de venta compara Decimal con Decimal."""

from decimal import Decimal

from bolsa_infrastructure.database.repositories.portfolio_repository import (
    sell_quantity_exceeds_held,
)


def test_sell_gate_rejects_float_roundtrip_above_held() -> None:
    """``float`` colapsa 999999999999.000062 y ``Decimal(str(float))`` pide más."""
    held = Decimal("999999999999.000062")
    quantity = float(held)
    assert not (float(held) < quantity)
    assert Decimal(str(quantity)) > held
    assert sell_quantity_exceeds_held(held, quantity) is True


def test_sell_gate_allows_exact_held() -> None:
    held = Decimal("10.000000")
    assert sell_quantity_exceeds_held(held, 10.0) is False
