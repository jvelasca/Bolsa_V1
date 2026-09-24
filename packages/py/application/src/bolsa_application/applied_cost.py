"""AUTO-16 (V2.57) — la fricción que el SIMULADOR APLICÓ, por fill y por ciclo.

Qué mide, exactamente: el precio de un fill SIM se **construye** sobre un mid de referencia con
una fricción determinista y adversa (``simulated_broker.simulated_fill_schedule``:
``px = base_mid ± |adverse_slippage_bps·i + spread_bps/2|``). Esa fricción es **medible**
(``|price − reference_mid| × qty``) y **no** es reconstruible desde el precio solo: el precio ya
la lleva dentro. Este módulo la recompone a partir del hecho crudo que el settlement persiste
(``reference_mid``, migración ``046``) y la agrega **por ciclo**, incluidas las dos patas.

Tres reglas duras, declaradas en vez de asumidas:

* **Siempre es un COSTE, nunca una rebaja.** El monto por pata es la MAGNITUD del desvío contra
  el mid (``|signed|``): el simulador hace el precio adverso por construcción —el comprador paga
  por encima del mid y el vendedor cobra por debajo—, así que restar el neto nunca puede
  convertirse en un premio por operar. Una pata que aterriza del lado **favorable** es un hecho
  imposible en el schedule actual: se mide igual pero se **DECLARA**
  (``applied_cost_favourable_leg``) en vez de leerse como un descuento.
* **Sin referencia no hay fricción, y jamás es ``0``.** Una fila anterior a ``2.57``, o un mid
  que no es un precio, deja la pata **sin medir**: publicar ``0`` diría "fricción gratis", que es
  regalar R. Es el mismo trato que ``AUTO-9`` da al coste que no se pudo cerrar.
* **Un agregado que solo suma lo que sabe medir es un SUELO.** La fricción de un ciclo es la
  suma de sus PATAS medidas y su ``measurement`` declara cuántas quedaron fuera; quien decida con
  el número tiene que exigir ``COMPLETE``. Y una ida y vuelta exige **las dos patas** (una compra
  y una venta): con una sola, el coste es ``PARTIAL`` aunque esté medida —sumar medio viaje
  subestimaría el coste del ciclo entero y sobrestimaría su R—.

Puro y determinista: sin I/O, sin reloj, sin estado. La lectura de las filas es del llamante.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)

__all__ = [
    "APPLIED_COST_FAVOURABLE_LEG",
    "APPLIED_COST_UNUSABLE_LEG",
    "APPLIED_COST_WITHOUT_LEG",
    "APPLIED_COST_WITHOUT_REFERENCE",
    "APPLIED_COST_WITHOUT_ROUND_TRIP",
    "AppliedCost",
    "AppliedLeg",
    "applied_cost_from_fills",
    "applied_cost_is_complete",
    "applied_leg",
]

#: La pata no lleva referencia utilizable ⇒ su fricción no se puede afirmar (nunca ``0``).
APPLIED_COST_WITHOUT_REFERENCE = "applied_cost_without_reference"
#: La pata no trae precio/cantidad/lado utilizables ⇒ no hay fricción que medir.
APPLIED_COST_UNUSABLE_LEG = "applied_cost_unusable_leg"
#: La pata aterrizó del lado FAVORABLE del mid: imposible en el schedule adverso, se declara.
APPLIED_COST_FAVOURABLE_LEG = "applied_cost_favourable_leg"
#: El ciclo no tiene ninguna pata con la que medir fricción.
APPLIED_COST_WITHOUT_LEG = "applied_cost_without_leg"
#: El ciclo tiene una sola dirección (falta la entrada o la salida): su coste ida-y-vuelta no
#: está completo, y leer medio viaje como el total subestimaría el coste del ciclo.
APPLIED_COST_WITHOUT_ROUND_TRIP = "applied_cost_without_round_trip"

_QTY = Decimal("0.000001")


def _dec(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = Decimal(str(value))
    except (ArithmeticError, ValueError, InvalidOperation):
        return None
    return out if out.is_finite() else None


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _positive(value: Any) -> Decimal | None:
    out = _dec(value)
    if out is None or out <= 0:
        return None
    return out


@dataclass(frozen=True, slots=True)
class AppliedLeg:
    """La fricción aplicada de UNA pata (un fill), o su hueco declarado.

    ``friction`` es la magnitud del desvío contra el mid de referencia, en moneda de la cuenta:
    un **coste**. ``adverse`` dice si la pata aterrizó del lado que el schedule adverso produce
    (``True`` por construcción); ``False`` es el caso imposible que se declara.
    """

    execution_id: str
    side: str
    friction: Decimal | None = None
    adverse: bool = True
    notes: tuple[str, ...] = ()

    @property
    def measured(self) -> bool:
        return self.friction is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "executionId": self.execution_id,
            "side": self.side,
            "friction": None if self.friction is None else str(self.friction),
            "adverse": self.adverse,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class AppliedCost:
    """La fricción aplicada de un ciclo: lo medido, cuánto falta y con qué motivo.

    ``friction`` es la suma de las patas **medidas**; con ``measurement != COMPLETE`` es un
    SUELO, no el total (la ausencia de una pata o su falta de referencia lo declaran los
    ``notes``). ``legs``/``unmeasured_legs`` son el rastro de la suma: sin ellos el número no
    es auditable. El **patrón de medida** es el mid de referencia de cada pata, no un precio
    de mercado: lo que se mide es la fricción que ESTE simulador aplicó.
    """

    cycle_id: str
    friction: Decimal | None = None
    measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    legs: int = 0
    unmeasured_legs: int = 0
    favourable_legs: int = 0
    notes: tuple[str, ...] = ()

    @property
    def measured(self) -> bool:
        return self.friction is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycleId": self.cycle_id,
            "friction": None if self.friction is None else str(self.friction),
            "measurement": self.measurement,
            "legs": self.legs,
            "unmeasuredLegs": self.unmeasured_legs,
            "favourableLegs": self.favourable_legs,
            "notes": list(self.notes),
        }


def applied_leg(fill: Any) -> AppliedLeg:
    """(PURA) la fricción aplicada de un fill, desde su precio y su mid de referencia.

    Se lee por atributo (``getattr``) para no acoplar el contrato puro al dataclass del store:
    lo que se exige es ``execution_id``/``side``/``price``/``quantity``/``reference_mid``.

    Convención de signo, que es la mitad de este módulo: en una **compra** el coste es
    ``(price − mid) × qty`` y en una **venta** ``(mid − price) × qty`` —en ambos casos lo que se
    pagó de más contra el mid—. El monto publicado es su magnitud, así que una pata favorable
    ``(signed < 0)`` se mide igual pero se declara en vez de restar.
    """
    execution_id = _text(getattr(fill, "execution_id", None))
    side = _text(getattr(fill, "side", None)).lower()
    price = _positive(getattr(fill, "price", None))
    quantity = _positive(getattr(fill, "quantity", None))
    reference = _positive(getattr(fill, "reference_mid", None))

    if side not in {"buy", "sell"} or price is None or quantity is None:
        return AppliedLeg(
            execution_id=execution_id,
            side=side,
            notes=(APPLIED_COST_UNUSABLE_LEG,),
        )
    if reference is None:
        return AppliedLeg(
            execution_id=execution_id,
            side=side,
            notes=(APPLIED_COST_WITHOUT_REFERENCE,),
        )

    signed = (price - reference) if side == "buy" else (reference - price)
    adverse = signed >= 0
    friction = (abs(signed) * quantity).quantize(_QTY)
    notes: tuple[str, ...] = () if adverse else (APPLIED_COST_FAVOURABLE_LEG,)
    return AppliedLeg(
        execution_id=execution_id,
        side=side,
        friction=friction,
        adverse=adverse,
        notes=notes,
    )


def _cycle_applied_cost(cycle_id: str, fills: Sequence[Any]) -> AppliedCost:
    legs = [applied_leg(fill) for fill in fills]
    measured = [leg for leg in legs if leg.measured]
    unmeasured = len(legs) - len(measured)
    favourable = sum(1 for leg in legs if leg.measured and not leg.adverse)
    notes: list[str] = []

    if not legs:
        notes.append(APPLIED_COST_WITHOUT_LEG)
    if unmeasured:
        # Un agregado que suma solo lo que sabe medir es un SUELO: se declara tal cual.
        notes.append(APPLIED_COST_WITHOUT_REFERENCE)
    if favourable:
        notes.append(APPLIED_COST_FAVOURABLE_LEG)

    friction: Decimal | None = None
    if measured:
        friction = sum((leg.friction for leg in measured if leg.friction is not None), Decimal("0"))

    sides = {leg.side for leg in legs if leg.measured}
    round_trip = {"buy", "sell"} <= sides
    if not legs:
        measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    elif not measured:
        measurement = MEASUREMENT_UNKNOWN
    elif unmeasured or not round_trip:
        # Falta una pata o su referencia: lo medido es un suelo, no el coste del ciclo.
        if not round_trip:
            notes.append(APPLIED_COST_WITHOUT_ROUND_TRIP)
        measurement = MEASUREMENT_PARTIAL
    else:
        measurement = MEASUREMENT_COMPLETE

    return AppliedCost(
        cycle_id=cycle_id,
        friction=friction,
        measurement=measurement,
        legs=len(legs),
        unmeasured_legs=unmeasured,
        favourable_legs=favourable,
        notes=tuple(dict.fromkeys(notes)),
    )


def applied_cost_from_fills(
    cycle_ids: Iterable[str],
    fills: Iterable[Any],
) -> dict[str, AppliedCost]:
    """(PURA) la fricción aplicada de CADA ciclo pedido, a partir de sus fills.

    Devuelve una entrada por **cada** ciclo pedido, incluidas las que declaran su hueco: una
    ausencia silenciosa en el mapa sería "no lo miré", no "no lo hay" —el mismo contrato que
    ``cycle_risk_from_reservations``—. Las filas de un ciclo que no se pidió se ignoran: no se
    inventan ciclos nuevos por lo que aparezca en la lectura.

    Sin I/O: el llamante trae las filas (``list_by_cycle_ids``) y este módulo solo agrega.
    """
    keys: list[str] = []
    seen: set[str] = set()
    for raw in cycle_ids:
        key = _text(raw)
        if key and key not in seen:
            seen.add(key)
            keys.append(key)

    grouped: dict[str, list[Any]] = {}
    for fill in fills:
        key = _text(getattr(fill, "cycle_id", None))
        if key and key in seen:
            grouped.setdefault(key, []).append(fill)

    return {key: _cycle_applied_cost(key, grouped.get(key, ())) for key in keys}


def applied_cost_is_complete(cost: AppliedCost | None) -> bool:
    """Predicado: solo un coste aplicado ``COMPLETE`` puede entrar al R neto.

    Se publica para que el llamante no improvise la condición: un ``PARTIAL`` (una pata sin
    medir) es un suelo, y usarlo como total sobrestimaría el R del ciclo.
    """
    return cost is not None and cost.measurement == MEASUREMENT_COMPLETE and cost.friction is not None
