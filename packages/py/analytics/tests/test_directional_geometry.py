"""Contratos de la casa ÚNICA de geometría direccional (``directional_geometry``).

La regla long/short vivía reimplementada (y en un caso, mal escrita) en varios módulos. Aquí
se fija el contrato compartido: la dirección es un PARÁMETRO, un valor desconocido degrada la
medición (nunca se asume larga) y un stop del lado equivocado NO es un riesgo de ``0``.
"""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.directional_geometry import (
    coerce_direction,
    risk_distance,
    signed_r,
    target_r,
)


def test_coerce_direction_normalizes_and_rejects_unknown() -> None:
    assert coerce_direction("long") == "long"
    assert coerce_direction(" SHORT ") == "short"
    assert coerce_direction("flat") is None
    assert coerce_direction(None) is None
    assert coerce_direction(1) is None


def test_risk_distance_requires_the_stop_on_the_correct_side() -> None:
    assert risk_distance(entry=100.0, stop=97.0) == pytest.approx(3.0)
    assert risk_distance(entry=100.0, stop=103.0) is None
    assert risk_distance(entry=100.0, stop=103.0, direction="short") == pytest.approx(3.0)
    assert risk_distance(entry=100.0, stop=97.0, direction="short") is None


def test_risk_distance_fails_closed_on_unknown_direction_or_bad_prices() -> None:
    assert risk_distance(entry=100.0, stop=97.0, direction="flat") is None
    assert risk_distance(entry=0.0, stop=-1.0) is None
    assert risk_distance(entry=100.0, stop=100.0) is None  # riesgo no medible, no cero


def test_signed_r_is_the_mirror_in_a_short() -> None:
    # Largo: premio si el precio SUBE por encima de la entrada.
    assert signed_r(direction="long", entry=100.0, risk=5.0, price=110.0) == pytest.approx(2.0)
    assert signed_r(direction="long", entry=100.0, risk=5.0, price=95.0) == pytest.approx(-1.0)
    # Corto: premio si el precio BAJA por debajo de la entrada.
    assert signed_r(direction="short", entry=100.0, risk=5.0, price=90.0) == pytest.approx(2.0)
    assert signed_r(direction="short", entry=100.0, risk=5.0, price=105.0) == pytest.approx(-1.0)


def test_signed_r_rejects_unknown_direction_and_unmeasurable_inputs() -> None:
    assert signed_r(direction="flat", entry=100.0, risk=5.0, price=110.0) is None
    assert signed_r(direction="long", entry=100.0, risk=0.0, price=110.0) is None
    assert signed_r(direction="long", entry=100.0, risk=5.0, price=0.0) is None


def test_target_r_measures_the_reward_towards_the_target() -> None:
    assert target_r(entry=100.0, stop=95.0, target=110.0) == pytest.approx(2.0)
    assert target_r(entry=100.0, stop=105.0, target=90.0, direction="short") == pytest.approx(2.0)
    # Un target del lado equivocado no es un premio negativo: es geometría no medible.
    assert target_r(entry=100.0, stop=95.0, target=90.0) is None