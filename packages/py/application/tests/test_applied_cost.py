"""AUTO-16 (V2.57) — la fricción APLICADA por el simulador, medida por pata y por ciclo.

Test hermético del módulo puro ``applied_cost``: no toca base de datos. Fija las tres reglas que
el R neto va a heredar, y las fija con CONTROL, porque son las que un descuido convertiría en R
regalado:

1. La fricción es un **coste** en las dos direcciones (el comprador paga por encima del mid y el
   vendedor cobra por debajo). Una pata favorable —imposible en el schedule adverso— se declara.
2. Sin referencia (o con un precio/cantidad/lado inservibles) **no** hay fricción: nunca un ``0``,
   que diría "fricción gratis".
3. Un agregado que solo suma lo que sabe medir es un **SUELO**: la ida y vuelta exige las dos
   patas, y quien decida con el número tiene que exigir ``COMPLETE``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.applied_cost import (
    APPLIED_COST_FAVOURABLE_LEG,
    APPLIED_COST_UNBALANCED_ROUND_TRIP,
    APPLIED_COST_UNUSABLE_LEG,
    APPLIED_COST_WITHOUT_CYCLE_CLOSURE,
    APPLIED_COST_WITHOUT_LEG,
    APPLIED_COST_WITHOUT_REFERENCE,
    APPLIED_COST_WITHOUT_ROUND_TRIP,
    applied_cost_from_fills,
    applied_cost_is_complete,
    applied_leg,
)

_CYCLE = "cyc-abc"


@dataclass(frozen=True, slots=True)
class _Fill:
    """Fill mínimo: lo que el contrato puro lee, ni un campo más."""

    execution_id: str
    side: str
    price: Decimal
    quantity: Decimal
    reference_mid: Decimal | None
    cycle_id: str | None = _CYCLE


def _buy(price: str, *, mid: str | None = "100", qty: str = "10", cycle: str | None = _CYCLE) -> _Fill:
    return _Fill(
        execution_id="venue#1",
        side="buy",
        price=Decimal(price),
        quantity=Decimal(qty),
        reference_mid=None if mid is None else Decimal(mid),
        cycle_id=cycle,
    )


def _sell(
    price: str, *, mid: str | None = "100", qty: str = "10", cycle: str | None = _CYCLE
) -> _Fill:
    return _Fill(
        execution_id="venue#2",
        side="sell",
        price=Decimal(price),
        quantity=Decimal(qty),
        reference_mid=None if mid is None else Decimal(mid),
        cycle_id=cycle,
    )


def test_a_buy_pays_above_the_mid_and_a_sell_collects_below_it() -> None:
    """Las dos direcciones cuestan: la convención de signo se mide, no se supone.

    Un comprador a ``100.15`` sobre un mid de ``100`` paga ``0.15 × 10``; un vendedor a ``99.90``
    cobra ``0.10 × 10`` menos. Los dos son COSTE, y por eso el agregado los suma en vez de
    compensarlos.
    """
    buy = applied_leg(_buy("100.15"))
    sell = applied_leg(_sell("99.90"))

    assert buy.friction == Decimal("1.500000")
    assert sell.friction == Decimal("1.000000")
    assert buy.adverse is True and sell.adverse is True


def test_a_round_trip_is_complete_and_sums_both_legs() -> None:
    """Ida y vuelta medida ⇒ ``COMPLETE``, y su coste es la suma de las DOS patas."""
    costs = applied_cost_from_fills(
        [_CYCLE], [_buy("100.15"), _sell("99.90")]
    )
    cost = costs[_CYCLE]

    assert cost.measurement == MEASUREMENT_COMPLETE
    assert cost.friction == Decimal("2.500000")
    assert (cost.legs, cost.unmeasured_legs) == (2, 0)
    assert applied_cost_is_complete(cost) is True


def test_half_a_trip_is_a_declared_floor_not_the_cost_of_the_cycle() -> None:
    """Solo la entrada medida ⇒ ``PARTIAL``: leer medio viaje como el total daría R de más.

    El número sigue publicándose (es un SUELO, como manda ``MeasurementStatus``), pero la
    condición para decidir con él es falsa y el motivo viaja en ``notes``.
    """
    cost = applied_cost_from_fills([_CYCLE], [_buy("100.15")])[_CYCLE]

    assert cost.friction == Decimal("1.500000")
    assert cost.measurement == MEASUREMENT_PARTIAL
    assert APPLIED_COST_WITHOUT_ROUND_TRIP in cost.notes
    assert applied_cost_is_complete(cost) is False


def test_a_leg_without_a_reference_is_never_a_zero_friction() -> None:
    """Sin ``reference_mid`` no hay fricción: ``0`` diría "fricción gratis" y regalaría R."""
    leg = applied_leg(_buy("100.15", mid=None))
    assert leg.friction is None
    assert leg.measured is False
    assert APPLIED_COST_WITHOUT_REFERENCE in leg.notes

    # Y contamina el ciclo como hueco, no como una pata barata.
    cost = applied_cost_from_fills([_CYCLE], [_buy("100.15", mid=None), _sell("99.90")])[_CYCLE]
    assert cost.measurement == MEASUREMENT_PARTIAL
    assert cost.unmeasured_legs == 1
    assert applied_cost_is_complete(cost) is False


def test_a_cycle_without_fills_declares_its_gap() -> None:
    """Un ciclo pedido y sin fills aparece con su hueco: ``UNKNOWN``, nunca un ``0``."""
    cost = applied_cost_from_fills([_CYCLE], [])[_CYCLE]

    assert cost.friction is None
    assert cost.measurement == MEASUREMENT_UNKNOWN
    assert cost.notes == (APPLIED_COST_WITHOUT_LEG,)
    assert applied_cost_is_complete(cost) is False


def test_a_cycle_that_was_not_requested_is_never_invented() -> None:
    """El mapa tiene una entrada por ciclo PEDIDO: lo que traiga la lectura no crea ciclos."""
    costs = applied_cost_from_fills(
        ["cyc-pedido"], [_buy("100.15", cycle="cyc-otro"), _sell("99.90", cycle="cyc-otro")]
    )

    assert list(costs) == ["cyc-pedido"]
    assert costs["cyc-pedido"].measurement == MEASUREMENT_UNKNOWN


def test_a_favourable_leg_is_measured_but_declared_so_it_cannot_read_as_a_discount() -> None:
    """Una compra POR DEBAJO del mid es imposible en el schedule adverso: se declara.

    Se mide igual (la magnitud es un coste), pero el hecho se publica para que nadie lo lea como
    un premio por operar ni lo reste del coste del ciclo.
    """
    leg = applied_leg(_buy("99.90"))
    assert leg.friction == Decimal("1.000000")
    assert leg.adverse is False
    assert APPLIED_COST_FAVOURABLE_LEG in leg.notes

    cost = applied_cost_from_fills([_CYCLE], [_buy("99.90"), _sell("99.95")])[_CYCLE]
    assert cost.favourable_legs == 1
    assert APPLIED_COST_FAVOURABLE_LEG in cost.notes


def test_an_unusable_leg_is_declared_unusable_and_not_measured() -> None:
    """Lado, precio o cantidad inservibles ⇒ la pata no se mide (y no se inventa el coste)."""
    leg = applied_leg(
        _Fill(
            execution_id="venue#x",
            side="hold",
            price=Decimal("100"),
            quantity=Decimal("10"),
            reference_mid=Decimal("100"),
        )
    )
    assert leg.friction is None
    assert APPLIED_COST_UNUSABLE_LEG in leg.notes


def test_the_sum_keeps_the_trace_of_how_many_legs_it_could_value() -> None:
    """El agregado lleva su rastro: sin ``legs``/``unmeasured_legs`` el número no es auditable."""
    cost = applied_cost_from_fills(
        [_CYCLE], [_buy("100.15"), _sell("99.90"), _sell("99.80", mid=None)]
    )[_CYCLE]
    payload = cost.as_dict()

    assert payload["legs"] == 3
    assert payload["unmeasuredLegs"] == 1
    assert payload["measurement"] == MEASUREMENT_PARTIAL
    assert payload["friction"] == "2.500000"
    assert payload["cycleId"] == _CYCLE


# ── AUTO-17: la ida y vuelta se PRUEBA con las cantidades, no con la presencia de lados ──


def test_a_round_trip_with_unbalanced_quantities_is_not_complete() -> None:
    """``BUY 100 / SELL 10`` tiene los dos lados y NO es un ciclo cerrado: quedan 90 abiertas.

    Presencia de direcciones no es round-trip. Declararlo ``COMPLETE`` mediría la fricción de
    una operación que no terminó y sobrestimaría el R con un coste de medio viaje.
    """
    cost = applied_cost_from_fills([_CYCLE], [_buy("100.15", qty="100"), _sell("99.90", qty="10")])[
        _CYCLE
    ]

    assert cost.measurement == MEASUREMENT_PARTIAL
    assert APPLIED_COST_UNBALANCED_ROUND_TRIP in cost.notes
    assert applied_cost_is_complete(cost) is False


def test_a_round_trip_that_balances_with_several_legs_is_complete() -> None:
    """``3 BUY + 2 SELL`` que cuadran SÍ es un ciclo cerrado: el balance manda, no el número de patas."""
    fills = [
        _buy("100.15", qty="50"),
        _buy("100.20", qty="50"),
        _sell("99.90", qty="60"),
        _sell("99.85", qty="40"),
    ]
    cost = applied_cost_from_fills([_CYCLE], fills)[_CYCLE]

    assert cost.measurement == MEASUREMENT_COMPLETE
    assert cost.legs == 4
    assert APPLIED_COST_UNBALANCED_ROUND_TRIP not in cost.notes


def test_a_reopened_cycle_is_not_complete_even_with_a_prior_round_trip() -> None:
    """``BUY 100 / SELL 100 / BUY 20`` no es un ciclo cerrado: el último BUY lo deja abierto."""
    fills = [_buy("100.15", qty="100"), _sell("99.90", qty="100"), _buy("100.05", qty="20")]
    cost = applied_cost_from_fills([_CYCLE], fills)[_CYCLE]

    assert cost.measurement == MEASUREMENT_PARTIAL
    assert APPLIED_COST_UNBALANCED_ROUND_TRIP in cost.notes


def test_a_leg_without_a_reference_still_counts_for_the_quantity_balance() -> None:
    """Cierre y medición son ejes independientes: una pata sin mid no aporta fricción pero SÍ cierra.

    El ciclo queda ``PARTIAL`` (le falta la referencia de una pata), pero por la MEDICIÓN, no por
    el balance: si el balance no se probara, el motivo declarado sería otro.
    """
    cost = applied_cost_from_fills([_CYCLE], [_buy("100.15", mid=None, qty="10"), _sell("99.90", qty="10")])[
        _CYCLE
    ]

    assert cost.measurement == MEASUREMENT_PARTIAL
    assert APPLIED_COST_WITHOUT_REFERENCE in cost.notes
    assert APPLIED_COST_UNBALANCED_ROUND_TRIP not in cost.notes
    assert APPLIED_COST_WITHOUT_ROUND_TRIP not in cost.notes


def test_an_unreadable_quantity_cannot_prove_the_balance() -> None:
    """Sin todas las cantidades legibles el balance NO se puede probar: no se afirma el cierre."""
    cost = applied_cost_from_fills(
        [_CYCLE], [_buy("100.15", qty="10"), _sell("99.90", qty="10"), _sell("99.80", qty="0")]
    )[_CYCLE]

    assert cost.measurement == MEASUREMENT_PARTIAL
    assert applied_cost_is_complete(cost) is False


def test_a_cycle_outside_the_closed_set_declares_its_gap_and_never_a_friction() -> None:
    """La autoridad de cierre manda: un ciclo que no está cerrado no recibe fricción aplicada."""
    costs = applied_cost_from_fills(
        [_CYCLE], [_buy("100.15"), _sell("99.90")], closed_cycle_ids=["otro-ciclo"]
    )

    assert costs[_CYCLE].measurement == MEASUREMENT_UNKNOWN
    assert costs[_CYCLE].friction is None
    assert costs[_CYCLE].notes == (APPLIED_COST_WITHOUT_CYCLE_CLOSURE,)
    assert applied_cost_is_complete(costs[_CYCLE]) is False


def test_a_cycle_inside_the_closed_set_is_measured_as_usual() -> None:
    """El control positivo: con el ciclo en el conjunto cerrado, la medición no cambia."""
    costs = applied_cost_from_fills(
        [_CYCLE], [_buy("100.15"), _sell("99.90")], closed_cycle_ids=[_CYCLE]
    )

    assert costs[_CYCLE].measurement == MEASUREMENT_COMPLETE
    assert costs[_CYCLE].friction == Decimal("2.500000")
