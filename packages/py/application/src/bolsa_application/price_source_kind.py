"""AUTO v2.88.25 — vocabulario canónico de la FUENTE de precio realmente usada por un fill.

Qué cierra: hasta hoy el header del monitor declaraba ``realPriceEnabled`` —la **configuración**
(``AUTO_ENGINE_SIM_REAL_PRICE``)—, no la fuente que de verdad construyó el precio de una operación.
Una operación podía sellarse con ``SYNTHETIC`` (el ``100.0`` hermético) mientras el flag decía ON, y
el hueco no tenía dónde viajar. Este módulo fija el vocabulario con el que la fuente se **persiste**
por fill (``sim_fill_finance_context.price_source``, migración 047) y se lee sin ambigüedad.

Regla dura (misma que ``reference_mid``): la ausencia se DECLARA. Un valor fuera del vocabulario no
se convierte en un literal inventado ni en una cadena libre — se normaliza a ``None`` (``NULL`` =
"fila anterior al sello / fuente no medible"), nunca a un ``"UNKNOWN"`` que parecería una medición.
"""

from __future__ import annotations

__all__ = [
    "PRICE_SOURCE_KINDS",
    "PRICE_SOURCE_MAPPING",
    "PRICE_SOURCE_MARKET_CLOSE",
    "PRICE_SOURCE_REPLAY",
    "PRICE_SOURCE_SCRIPT",
    "PRICE_SOURCE_SYNTHETIC",
    "PRICE_SOURCE_XTB",
    "usable_price_source",
]

#: Barra real leída del repositorio OHLCV (``OhlcvPriceSource``): ``close(B-1)`` para decisión,
#: ``open(B)`` para ejecución. Es la fuente de precio REAL del motor.
PRICE_SOURCE_MARKET_CLOSE = "MARKET_CLOSE"
#: ``PriceScript`` hermético por defecto (``flat_price_script`` → ``100.0``): precio FABRICADO, no
#: de mercado. El sello lo declara para que "ON en configuración" no se lea como "precio real".
PRICE_SOURCE_SYNTHETIC = "SYNTHETIC"
#: ``PriceScript`` inyectado (replay/tests) sin envolver en un ``PriceSource`` explícito.
PRICE_SOURCE_SCRIPT = "SCRIPT"
#: ``MappingPriceSource`` — mapa estático (tests/dry-run).
PRICE_SOURCE_MAPPING = "MAPPING"
#: Replay determinista (OOS/forward) que use un ``PriceSource`` dedicado. Reservado.
PRICE_SOURCE_REPLAY = "REPLAY"
#: Feed vivo XTB. Reservado para cuando exista un productor real (hoy el venue está PARKED).
PRICE_SOURCE_XTB = "XTB"

#: Vocabulario cerrado: lo que un lector puede encontrar en la columna durable.
PRICE_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        PRICE_SOURCE_MARKET_CLOSE,
        PRICE_SOURCE_SYNTHETIC,
        PRICE_SOURCE_SCRIPT,
        PRICE_SOURCE_MAPPING,
        PRICE_SOURCE_REPLAY,
        PRICE_SOURCE_XTB,
    }
)


def usable_price_source(raw: object) -> str | None:
    """(PURA) la fuente de precio UTILIZABLE, o ``None`` si no pertenece al vocabulario.

    Un valor ausente o ajeno al vocabulario NO se rellena con un literal: se declara como
    "no medido" (``None`` → ``NULL``). Normaliza el texto (mayúsculas/espacios) para que el
    mismo hecho no viaje escrito de dos formas.
    """
    text = str(raw or "").strip().upper()
    return text if text in PRICE_SOURCE_KINDS else None
