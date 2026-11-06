"""P9 (auditoría .183) — normalizador numérico FINITO del camino de dinero.

El bug que se cierra: los ``_finite`` repartidos por ``bolsa_analytics`` comprobaban
``number != number`` (solo ``NaN``). Un ``inf`` —el resultado de una división por cero, de un
overflow o de un parser roto— atravesaba el filtro y, como ``inf > 0``, el motor lo aceptaba como
precio o cantidad. Aquí se fija el contrato de la ÚNICA respuesta canónica.
"""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from bolsa_domain.numeric import (
    finite_float,
    finite_positive,
    finite_range,
    positive_price,
    positive_quantity,
)

#: Todo lo que NO es un número utilizable. ``bool`` incluido: ``True`` se colaría como 1.0.
_REJECTED = (
    None,
    True,
    False,
    "",
    "   ",
    "-",
    "abc",
    "nan",
    "inf",
    "-inf",
    "Infinity",
    float("nan"),
    float("inf"),
    float("-inf"),
    Decimal("NaN"),
    Decimal("Infinity"),
    Decimal("-Infinity"),
    object(),
    [],
    {},
)


@pytest.mark.parametrize("value", _REJECTED)
def test_finite_float_rejects_every_non_number(value: object) -> None:
    assert finite_float(value) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0.0),
        (-3, -3.0),
        (1.5, 1.5),
        ("2.25", 2.25),
        (" 7 ", 7.0),
        (Decimal("4.5"), 4.5),
        (-0.0, 0.0),
    ],
)
def test_finite_float_accepts_finite_numbers(value: object, expected: float) -> None:
    result = finite_float(value)
    assert result is not None
    assert math.isclose(result, expected, abs_tol=0.0)


def test_finite_float_rejects_values_beyond_the_sanity_band() -> None:
    """``1e19`` no es un precio ni una cantidad: solo puede venir de un overflow."""
    assert finite_float(1e19) is None
    assert finite_float(-1e19) is None


@pytest.mark.parametrize("value", [0, -1, -0.5, "0", float("inf"), float("nan"), None, "abc"])
def test_finite_positive_requires_strictly_positive(value: object) -> None:
    assert finite_positive(value) is None


@pytest.mark.parametrize(("value", "expected"), [(1, 1.0), ("0.5", 0.5), (Decimal("2"), 2.0)])
def test_finite_positive_accepts_positive_finite(value: object, expected: float) -> None:
    assert finite_positive(value) == expected


@pytest.mark.parametrize("value", [0, -2, float("inf"), float("nan"), "abc", None])
def test_positive_price_rejects_what_cannot_be_a_price(value: object) -> None:
    assert positive_price(value) is None


def test_positive_price_accepts_a_real_price() -> None:
    assert positive_price("101.25") == 101.25


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), "abc", None, True])
def test_positive_quantity_rejects_unusable_quantities(value: object) -> None:
    assert positive_quantity(value) is None


def test_positive_quantity_returns_an_exact_decimal() -> None:
    quantity = positive_quantity("150.5")
    assert quantity == Decimal("150.5")
    assert isinstance(quantity, Decimal)


def test_positive_quantity_never_yields_a_non_finite_decimal() -> None:
    """El filtro va ANTES de ``Decimal``: no puede construirse ``Decimal('Infinity')``."""
    assert positive_quantity(Decimal("Infinity")) is None
    assert positive_quantity(1e19) is None


@pytest.mark.parametrize(
    ("low", "high", "expected"),
    [
        (1, 2, (1.0, 2.0)),
        (2, 2, (2.0, 2.0)),
        ("1.5", 3, (1.5, 3.0)),
    ],
)
def test_finite_range_accepts_a_well_formed_range(
    low: object, high: object, expected: tuple[float, float]
) -> None:
    assert finite_range(low, high) == expected


@pytest.mark.parametrize(
    ("low", "high"),
    [
        (2, 1),  # invertido: dato corrupto
        (float("inf"), 3),
        (1, float("nan")),
        (None, 1),
        (1, None),
        ("abc", 1),
    ],
)
def test_finite_range_rejects_a_corrupt_range(low: object, high: object) -> None:
    assert finite_range(low, high) is None
