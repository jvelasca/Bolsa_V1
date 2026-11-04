"""M15: una ampliación mezcla el coste de entrada (coste medio ponderado)."""

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
