"""AUTO v2.88.25 — vocabulario canónico de la FUENTE de precio realmente usada por un fill.

Qué cierra: hasta hoy el header del monitor declaraba ``realPriceEnabled`` —la **configuración**
(``AUTO_ENGINE_SIM_REAL_PRICE``)—, no la fuente que de verdad construyó el precio de una operación.
Una operación podía sellarse con ``SYNTHETIC`` (el ``100.0`` hermético) mientras el flag decía ON, y
el hueco no tenía dónde viajar. Este módulo fija el vocabulario con el que la fuente se **persiste**
por fill (``sim_fill_finance_context.price_source``, migración 047) y se lee sin ambigüedad.

Regla dura (misma que ``reference_mid``): la ausencia se DECLARA. Un valor fuera del vocabulario no
se convierte en un literal inventado ni en una cadena libre — se normaliza a ``None`` (``NULL`` =
"fila anterior al sello / fuente no medible"), nunca a un ``"UNKNOWN"`` que parecería una medición.

Autoridad canónica (v2.88.27): la fuente de verdad es ``sim_fill_finance_context.price_source``
(el fill). ``auto_entry_order.priceSource`` y ``auto_cycle_settlement.priceSource`` son SNAPSHOTS de
auditoría, no una segunda medida: si algún día contradicen al fill, gana el fill
(``canonical_price_source``) y la discrepancia se declara (``price_source_snapshot_disagrees``).
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
    "canonical_price_source",
    "price_source_snapshot_disagrees",
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


def canonical_price_source(
    fill_price_source: object, event_price_source: object = None
) -> str | None:
    """(PURA, v2.88.27) fuente CANÓNICA cuando el fill y su snapshot de auditoría difieren.

    Autoridad declarada: la fuente del FILL (``sim_fill_finance_context.price_source``), que es
    el hecho del que el precio realmente salió. ``auto_entry_order``/``auto_cycle_settlement``
    llevan un ``priceSource`` que es un **snapshot** para el journal, NO una segunda verdad: si
    contradicen al fill, no lo sobreescriben. Un fill no medido (``None``) tampoco se rellena con
    el snapshot: la ausencia también es autoridad.
    """
    return usable_price_source(fill_price_source)


def price_source_snapshot_disagrees(
    fill_price_source: object, event_price_source: object
) -> bool | None:
    """(PURA) ``True``/``False`` si fill y snapshot están MEDIDOS y difieren; ``None`` si no.

    Discrepar exige dos mediciones: si alguna falta, no hay discrepancia que afirmar (sería
    confundir "no medido" con "distinto"). Es la comprobación de observabilidad de la regla de
    autoridad — cuando devuelve ``True``, gana ``canonical_price_source`` (el fill).
    """
    fill = usable_price_source(fill_price_source)
    snapshot = usable_price_source(event_price_source)
    if fill is None or snapshot is None:
        return None
    return fill != snapshot
