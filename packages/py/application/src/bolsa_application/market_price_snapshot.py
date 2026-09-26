"""V2.76 · AUTO-MATERIAL-4 — precio de MERCADO para el PAPER forward (I/O fuera del hot path).

Qué resuelve: el ``AutoSimulationWorker`` sólo recibe precio por UN seam inyectable,
``PriceScript = Callable[[str, int], float]`` (``price_script``), cuyo default es
``flat_price_script`` (100.0 constante). En producción ``AutoSimRuntime`` no inyecta precio, así
que el motor marcha con un precio PLANO: sin movimiento no hay stop que se rompa, no hay ciclo y
no hay material. Esta pieza es el adaptador que convierte cotización/cierre de MERCADO en ese
``price_script``, **sin tocar el worker congelado**.

La forma es la MISMA que ``AtrSource``/``DiscoveryRegimeSource`` (``auto_v2_entry.py``):

* ``refresh()`` es la parte **async** (I/O: trae cotización live y/o cierre durable y forma el
  cache). El llamante la invoca una vez por tick, en el bucle del runner, NUNCA dentro del worker.
* ``__call__(symbol, minute)`` es la lectura **SÍNCRONA** del hot path (la firma exacta de
  ``PriceScript``), de modo que decidir no depende de la red.

Procedencia DECLARADA (no se adivina): cada símbolo viaja con la fuente que sirvió su precio
(``market_live`` para la cotización viva, ``market_close`` para el último cierre durable). El
runner puede publicar ese reparto.

Fail-closed: un proveedor que revienta, un valor no finito o no positivo o la ausencia de dato
dejan el símbolo **SIN precio** (``0.0``). No se inventa un precio para poder operar: con precio
``0`` el motor veta la candidata (``entry_price=None`` ⇒ sin asignación) y no marca posiciones.
El motor sigue siendo el único que decide; aquí sólo se sirve el dato de mercado.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = [
    "PRICE_SOURCE_CLOSE",
    "PRICE_SOURCE_LIVE",
    "CloseProvider",
    "MarketPriceSnapshot",
    "QuoteProvider",
]

#: Procedencia declarada del precio servido por el cache.
PRICE_SOURCE_LIVE = "market_live"
PRICE_SOURCE_CLOSE = "market_close"

#: Proveedor de cotización VIVA (broker): símbolos pedidos → ``{symbol: price}``.
QuoteProvider = Callable[[Sequence[str]], Awaitable[Mapping[str, float]]]
#: Proveedor de CIERRE duradero (barras): símbolos pedidos → ``{symbol: price}``.
CloseProvider = Callable[[Sequence[str]], Awaitable[Mapping[str, float]]]


def _usable_price(value: object) -> float | None:
    """Precio utilizable (finito y ``> 0``) o ``None``: nunca se sirve un cero inflado.

    Un ``None``, un ``NaN`` o un ``0``/negativo NO son un precio: el símbolo queda sin dato y el
    motor lo trata como tal (fail-closed). Convertir cualquiera de ellos en un número inventado
    sería exactamente el fallo que esta pieza existe para no cometer.
    """
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")) or number <= 0:
        return None
    return number


@dataclass
class MarketPriceSnapshot:
    """``price_script`` de mercado: cotización viva con respaldo del último cierre durable.

    ``quotes_provider`` es la fuente PRIMARIA (broker, precio vivo); ``closes_provider`` es el
    RESPALDO declarado para los símbolos que la primaria no sirvió (p. ej. bridge caído o símbolo
    sin cotización). La resolución es por símbolo: un símbolo con cotización viva no se sobrescribe
    con el cierre.

    ``refresh(symbols)`` reconstruye el cache ENTERO cada vez (no acumula símbolos de ticks
    previos: un símbolo retirado del watch no puede seguir sirviendo un precio viejo). Devuelve
    cuántos símbolos quedaron con precio.
    """

    quotes_provider: QuoteProvider
    closes_provider: CloseProvider | None = None
    _price_by_symbol: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _source_by_symbol: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    async def refresh(self, symbols: Sequence[str]) -> int:
        """Reforma el cache de precios. Devuelve cuántos símbolos tienen precio utilizable."""
        wanted = [text for text in (str(s).strip() for s in symbols) if text]
        if not wanted:
            self._price_by_symbol = {}
            self._source_by_symbol = {}
            return 0
        # Sólo se acepta lo PEDIDO: un proveedor que devuelva símbolos fuera del watch no puede
        # colarles un precio (ni sobrevivir al símbolo retirado del watch en el tick anterior).
        watch = set(wanted)

        prices: dict[str, float] = {}
        sources: dict[str, str] = {}

        live = await self._fetch(self.quotes_provider, wanted, label="live")
        for symbol, value in live.items():
            number = _usable_price(value)
            key = str(symbol).strip()
            if number is not None and key in watch and key not in prices:
                prices[key] = number
                sources[key] = PRICE_SOURCE_LIVE

        missing = [symbol for symbol in wanted if symbol not in prices]
        if missing and self.closes_provider is not None:
            closes = await self._fetch(self.closes_provider, missing, label="close")
            for symbol, value in closes.items():
                number = _usable_price(value)
                key = str(symbol).strip()
                if number is not None and key in watch and key not in prices:
                    prices[key] = number
                    sources[key] = PRICE_SOURCE_CLOSE

        self._price_by_symbol = prices
        self._source_by_symbol = sources
        return len(prices)

    async def _fetch(
        self,
        provider: Callable[[Sequence[str]], Awaitable[Mapping[str, float]]],
        symbols: Sequence[str],
        *,
        label: str,
    ) -> Mapping[str, float]:
        """Llama a un proveedor declarando el fallo; sin feed no hay precio (fail-closed)."""
        try:
            return await provider(symbols) or {}
        except Exception:  # noqa: BLE001 — sin feed el símbolo queda sin precio, no inventado.
            logger.exception("market price %s refresh failed (symbols=%d)", label, len(symbols))
            return {}

    def price_for(self, symbol: str) -> float | None:
        """Lectura síncrona del precio cacheado (``None`` si no hay dato verificable)."""
        return self._price_by_symbol.get(str(symbol or "").strip())

    def source_for(self, symbol: str) -> str | None:
        """Procedencia declarada del precio de un símbolo (``None`` si no hay dato)."""
        return self._source_by_symbol.get(str(symbol or "").strip())

    def sources(self) -> dict[str, str]:
        """Copia del reparto ``symbol → fuente`` del último refresco (para publicar)."""
        return dict(self._source_by_symbol)

    def __call__(self, symbol: str, _minute: int) -> float:
        """Firma de ``PriceScript``: precio del símbolo o ``0.0`` (sin dato, fail-closed)."""
        return self.price_for(symbol) or 0.0
