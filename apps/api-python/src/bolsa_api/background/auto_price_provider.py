"""W4 / v2.88.17-beta — Proveedor de precio REAL del motor AUTO (frontera **MIXTA**).

Motivo (medido en W3.3, `evidence/v2.88.16.3`): el simulado sorteaba el venue sobre un
``base_mid`` **plano de 100.0** (``flat_price_script``), y la banda del instrumento OOS
salía de ``R −37,72`` a ``+0,82`` con ``σ(R) = 10,14``, **cruzando el cero**. Sin precio
real el book es casi todo ruido ⇒ ninguna lectura de mérito es separable del dado.

Este módulo define el **seam** que puede decir «**no hay precio**» — algo que
``PriceScript = Callable[[str, int], float]`` NO puede expresar (su único recurso era
mentir con ``100.0`` o ``0``). Dos fronteras, decididas por el propietario (2026-10-01):

  * ``mid(...)``       — referencia de **DECISIÓN** (señal, geometría, régimen, ATR):
    ``close`` de la última barra **CERRADA** (``<= B-1``). Es la frontera de W3
    (``last_closed_bar_day``), estrictamente **sin lookahead**.
  * ``execution(...)`` — **EJECUCIÓN** (*mid* del fill) y **MARCA** (equity, protección):
    ``open``/último precio de la barra **CORRIENTE**. Es el ancla que W3 ya declaró
    (``OPEN(D+1)``) y **es conocido**: no es lookahead.

**Fail-closed (por símbolo).** ``None`` no es un valor: es el estado «no hay precio». El
motor NO lo degrada a una constante: ese símbolo no puede ejecutar (``HOLD``, declarado y
contado) y si **ningún** símbolo tiene precio el turno se declara ``BLOCKED``. Aquí vive
el contrato; la política de turno vive en el worker.

**``Δ = 0`` por construcción.** ``ConstantPriceSource`` envuelve el ``PriceScript``
inyectable (reloj + script del replay y de los tests) devolviendo **exactamente** lo que
el script devolvía, y **nunca** ``None``. Adoptar este seam no mueve un solo precio del
camino hermético: sólo hace *explícito* el default que antes era silencioso.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, cast, runtime_checkable

#: Contrato histórico del precio por ``(símbolo, tick de BARRA)``. Se conserva para el
#: camino inyectable (replay/tests); ``ConstantPriceSource`` lo adapta a ``PriceSource``.
PriceScript = Callable[[str, int], float]


@runtime_checkable
class PriceSource(Protocol):
    """Precio por símbolo en el tick de barra corriente — o ``None`` si **no hay precio**.

    ``refresh`` fija la foto del tick (una vez por tick/barra); las consultas son puras
    y deterministas dentro del tick. Implementarla NO obliga a heredar de nada: basta con
    los cuatro métodos (Protocol estructural).
    """

    def refresh(self, *, tick: int, symbols: Sequence[str]) -> None:
        """Precarga la foto del tick de barra ``tick`` para ``symbols`` (una vez/tick)."""
        ...

    def mid(self, symbol: str) -> float | None:
        """Precio de **DECISIÓN**: ``close`` de la última barra cerrada (``<= B-1``)."""
        ...

    def execution(self, symbol: str) -> float | None:
        """Precio de **EJECUCIÓN/MARCA**: ``open`` de la barra corriente (conocido, no lookahead)."""
        ...

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        """Símbolos de ``symbols`` SIN precio de ejecución ⇒ no ejecutables (``HOLD``)."""
        ...


class ConstantPriceSource:
    """Adapta un ``PriceScript`` constante/inyectable a ``PriceSource`` **sin cambiar nada**.

    ``mid`` y ``execution`` devuelven EXACTAMENTE ``script(símbolo, tick)`` y **nunca**
    ``None`` (salvo que el propio script devuelva ``None``, que ningún script histórico
    hace). Es la garantía de ``Δ = 0`` para replay y tests: adoptar el seam no mueve un
    precio del camino hermético.
    """

    __slots__ = ("_script", "_tick")

    def __init__(self, script: PriceScript) -> None:
        if not callable(script):
            raise TypeError("ConstantPriceSource exige un PriceScript invocable")
        self._script = script
        self._tick = 0

    def refresh(self, *, tick: int, symbols: Sequence[str]) -> None:  # noqa: ARG002 (paridad de firma)
        self._tick = int(tick)

    def _price(self, symbol: str) -> float | None:
        value = self._script(symbol, self._tick)
        return None if value is None else float(value)

    def mid(self, symbol: str) -> float | None:
        return self._price(symbol)

    def execution(self, symbol: str) -> float | None:
        return self._price(symbol)

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        return tuple(s for s in symbols if self._price(s) is None)


class MappingPriceSource:
    """Fuente de precio desde un ``{símbolo: precio}`` — pura, para tests y *dry-run*.

    Un símbolo **ausente** del mapa ⇒ ``None`` (no hay precio), **nunca** un valor por
    defecto. Es el doble que permite ejercitar el fail-closed sin tocar PG.
    """

    __slots__ = ("_prices", "_tick", "_refreshes")

    def __init__(self, prices: Mapping[str, float | None] | None = None) -> None:
        self._prices: dict[str, float | None] = dict(prices or {})
        self._tick = 0
        self._refreshes = 0

    def refresh(self, *, tick: int, symbols: Sequence[str]) -> None:  # noqa: ARG002
        self._tick = int(tick)
        self._refreshes += 1

    def mid(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def execution(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        return tuple(s for s in symbols if self._prices.get(s) is None)

    @property
    def refreshes(self) -> int:
        """Nº de ``refresh`` observados (prueba de que la foto es una por tick)."""
        return self._refreshes


def as_price_source(provided: PriceSource | PriceScript) -> PriceSource:
    """Normaliza el seam: un ``PriceScript`` se envuelve; un ``PriceSource`` pasa tal cual.

    **Sin default silencioso**: aquí NO se elige ``100.0`` ni ``0``. Quien no tenga fuente
    debe decidirlo explícitamente (el worker conserva ``flat_price_script`` como default
    *declarado* del camino hermético, no como fallback invisible).
    """
    if hasattr(provided, "mid") and hasattr(provided, "execution"):
        return cast("PriceSource", provided)  # ya es un PriceSource (estructural)
    if not callable(provided):
        raise TypeError(
            "as_price_source exige un PriceSource o un PriceScript; "
            f"recibido {type(provided).__name__}",
        )
    return ConstantPriceSource(provided)
