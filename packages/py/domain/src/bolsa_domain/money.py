"""Dinero y precios en ``Decimal`` — política única del dominio (Fase 2.3).

Contexto: la auditoría externa señaló que el dominio monetario viajaba en ``float``. El
error binario no es teórico: ``0.1 + 0.2 != 0.3`` y una suma de 10.000 importes de céntimos
deriva. Este módulo fija la respuesta del dominio:

* **Campo monetario ⇒ ``Decimal``.** Nombres ``amount``, ``price``, ``cost``, ``fee``,
  ``commission``, ``balance``, ``equity``, ``cash``, ``pnl``, ``value`` (y sus compuestos
  ``total_equity``, ``avg_cost``, ``balance_after``, ...). Ver
  ``tests/test_money_decimal_guard.py``: es un guard ejecutable, no una convención oral.
* **Ratio ⇒ ``float``.** Nombres ``*_pct`` / ``*_ratio`` (``unrealized_pnl_pct``,
  ``margin_call_level_pct``, ``leverage``) siguen en ``float``: son magnitudes continuas,
  no dinero que se sume en un libro.
* **La conversión desde ``float`` pasa por ``str()``.** ``Decimal(0.1)`` es
  0.1000000000000000055511151231257827; ``Decimal(str(0.1))`` es ``0.1``. ``to_decimal``
  usa la segunda forma, así que un importe que llega de la BD como ``1234.56`` se guarda
  como ``Decimal("1234.56")`` y no arrastra la cola binaria.
* **Cuantizar es explícito, nunca implícito.** ``quantize_money`` (céntimos, HALF_EVEN) y
  ``quantize_price`` (4 decimales, HALF_EVEN) se aplican al *cerrar* una cifra para
  persistirla o publicarla. Construir la entidad **no** redondea: redondear en la puerta
  escondería la diferencia entre «cuánto es» y «cuánto se muestra».

Guardarraíles: se rechazan ``bool`` (``True`` es 1), ``NaN``/``Infinity`` y texto no
numérico. La señal de «no medido» es ``None``, nunca un cero fabricado.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Final

#: Cuantizador de dinero: céntimos. ``ROUND_HALF_EVEN`` (bancario) evita el sesgo al alza
#: de ``ROUND_HALF_UP`` en series largas de redondeos.
MONEY_QUANT: Final[Decimal] = Decimal("0.01")

#: Cuantizador de precio: 4 decimales (los instrumentos del mercado objetivo cotizan en
#: céntimos, pero los precios medios y los FX necesitan una cifra más de margen).
PRICE_QUANT: Final[Decimal] = Decimal("0.0001")


def to_decimal(value: object, *, field: str = "value") -> Decimal:
    """Convierte a ``Decimal`` exacto (vía ``str``) o lanza.

    Acepta ``Decimal`` (se devuelve tal cual, sin re-cuantizar), ``int``, ``float`` y
    ``str`` numérico. Rechaza ``bool``, ``None``, ``NaN``, ``Infinity`` y texto no
    numérico: son datos corruptos, no importes.
    """
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{field}: Decimal no finito ({value!r})")
        return value
    if isinstance(value, bool) or value is None:
        raise TypeError(f"{field}: se esperaba un importe, llegó {type(value).__name__}")
    if isinstance(value, int | float):
        # ``str`` y no ``Decimal(float)``: la cola binaria del float no entra en el libro.
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensa
            raise ValueError(f"{field}: float no convertible ({value!r})") from exc
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError(f"{field}: texto vacío")
        try:
            number = Decimal(raw)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{field}: texto no numérico ({value!r})") from exc
    else:
        raise TypeError(f"{field}: tipo no soportado ({type(value).__name__})")
    if not number.is_finite():
        raise ValueError(f"{field}: importe no finito ({value!r})")
    return number


def to_decimal_or_none(value: object, *, field: str = "value") -> Decimal | None:
    """``to_decimal`` conservando ``None`` como «no medido»."""
    if value is None:
        return None
    return to_decimal(value, field=field)


def quantize_money(value: object, *, field: str = "value") -> Decimal:
    """Cierra un importe a céntimos (HALF_EVEN).

    Solo para el borde de persistencia/publicación: la entidad guarda el ``Decimal``
    exacto y el redondeo se declara donde ocurre.
    """
    return to_decimal(value, field=field).quantize(MONEY_QUANT, rounding=ROUND_HALF_EVEN)


def quantize_price(value: object, *, field: str = "value") -> Decimal:
    """Cierra un precio a 4 decimales (HALF_EVEN)."""
    return to_decimal(value, field=field).quantize(PRICE_QUANT, rounding=ROUND_HALF_EVEN)


def decimal_or_zero(value: object, *, field: str = "value") -> Decimal:
    """``Decimal`` para agregados internos: ``None`` (no medido) suma 0 al total.

    Uso restringido a acumuladores donde la ausencia de una posición sin precio no debe
    invalidar el total (M-1: una posición sin marca no aporta, no rompe). Nunca para
    publicar una cifra: ahí ``None`` sigue siendo «sin dato».
    """
    if value is None:
        return Decimal(0)
    return to_decimal(value, field=field)


def coerce_money_fields(instance: object, *names: str) -> None:
    """Normaliza a ``Decimal`` los campos monetarios de una instancia ya construida.

    Pensado para ``__post_init__`` de dataclasses ``frozen=True, slots=True``: usa
    ``object.__setattr__`` para no pelear con el ``frozen``. ``None`` sigue siendo
    ``None`` («no medido»), nunca 0.
    """
    for name in names:
        object.__setattr__(
            instance,
            name,
            to_decimal_or_none(getattr(instance, name), field=name),
        )


__all__ = [
    "MONEY_QUANT",
    "PRICE_QUANT",
    "coerce_money_fields",
    "decimal_or_zero",
    "quantize_money",
    "quantize_price",
    "to_decimal",
    "to_decimal_or_none",
]
