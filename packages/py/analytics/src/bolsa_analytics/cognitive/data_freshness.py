"""Frescura POR DIMENSIÓN de los datos que alimentan una decisión (AUTO-3 slice 2).

Hasta ahora la frescura era un único booleano/etiqueta (``data_freshness``): "los datos
están frescos o no". Eso mezcla dimensiones con relojes distintos y, peor, no distingue
lo que puede esperar de lo que no. Este módulo separa cuatro relojes:

* ``market_data`` — la barra/precio sobre la que se decide. Su vejez invalida CUALQUIER
  apertura (decidir contra un precio viejo es decidir contra un hecho falso).
* ``atr`` — la geometría de riesgo. Su vejez degrada el dimensionamiento (un ``None``
  ya es fail-closed en el motor, así que esto lo declara, no lo inventa).
* ``quote`` — el precio de referencia de ejecución.
* ``volume`` — la liquidez.

Invariante de la casa que este módulo hace explícito: **stale ⇒ NO ENTRY, pero las
salidas protectoras siguen permitidas**. Por eso el veredicto se publica como
``blocks_new_entry`` (veto de aperturas) y NUNCA como un halt que congelaría también
las salidas. La reconciliación veta aperturas, jamás una salida que reduce riesgo.

Módulo puro y determinista: recibe instantes en segundos (epoch) o ISO-8601 y un
``now``; no lee reloj ni red.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

FreshnessStatus = Literal["fresh", "stale", "unknown"]

FRESHNESS_FRESH: FreshnessStatus = "fresh"
FRESHNESS_STALE: FreshnessStatus = "stale"
FRESHNESS_UNKNOWN: FreshnessStatus = "unknown"

#: Dimensiones canónicas (contrato con el journal).
FRESHNESS_DIMENSIONS: tuple[str, ...] = ("market_data", "atr", "quote", "volume")


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Umbral de edad (segundos) por dimensión. ``None`` ⇒ la dimensión no ata.

    Un umbral ``None`` NO es "libre": es "no se mide esta dimensión aquí". La dimensión
    sigue apareciendo como ``unknown`` si no hay dato; lo que no hace es declarar stale
    algo que nadie pidió medir.
    """

    max_market_data_age_s: float | None = 300.0
    max_atr_age_s: float | None = 3600.0
    max_quote_age_s: float | None = 60.0
    max_volume_age_s: float | None = 3600.0

    def __post_init__(self) -> None:
        for field_name in (
            "max_market_data_age_s",
            "max_atr_age_s",
            "max_quote_age_s",
            "max_volume_age_s",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be >= 0 or None")


@dataclass(frozen=True, slots=True)
class DimensionFreshness:
    """Lectura de UNA dimensión: instante, edad y estado."""

    dimension: str
    last_at: float | None
    age_seconds: float | None
    status: FreshnessStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "lastAt": self.last_at,
            "ageSeconds": self.age_seconds,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class FreshnessAssessment:
    """Lectura agregada de las cuatro dimensiones."""

    dimensions: tuple[DimensionFreshness, ...]
    as_of: float

    def dimension(self, name: str) -> DimensionFreshness | None:
        for reading in self.dimensions:
            if reading.dimension == name:
                return reading
        return None

    @property
    def market_data_stale(self) -> bool:
        """True SOLO si la dimensión de mercado declara ``stale`` (``unknown`` no es stale)."""
        reading = self.dimension("market_data")
        return reading is not None and reading.status == FRESHNESS_STALE

    @property
    def blocks_new_entry(self) -> bool:
        """El veto de aperturas: mercado no-fresco (stale o sin dato) ⇒ no se abre.

        ``unknown`` bloquea igual que ``stale``: no se abre contra un dato que no se pudo
        fechar. Las otras dimensiones NO bloquean la apertura por sí solas (degradan el
        dimensionamiento, que ya es fail-closed río abajo).
        """
        reading = self.dimension("market_data")
        return reading is None or reading.status != FRESHNESS_FRESH

    @property
    def data_freshness(self) -> str:
        """Etiqueta para el ``AutoPortfolioSnapshot`` (``fresh`` o ``stale``).

        ``unknown`` se publica como ``stale`` a propósito: el snapshot tiene un eje
        booleano (``data_is_fresh``) y "no sé" jamás puede leerse como fresco.
        """
        return FRESHNESS_FRESH if not self.blocks_new_entry else FRESHNESS_STALE

    def to_dict(self) -> dict[str, Any]:
        return {
            "asOf": self.as_of,
            "dimensions": [reading.to_dict() for reading in self.dimensions],
            "marketDataStale": self.market_data_stale,
            "blocksNewEntry": self.blocks_new_entry,
            "dataFreshness": self.data_freshness,
        }


def _epoch(value: Any) -> float | None:
    """Normaliza un instante (epoch numérico o ISO-8601) a segundos; ``None`` si no se puede.

    Un instante no interpretable ⇒ ``None`` (dimensión ``unknown``), nunca 0 (que sería
    "muy viejo" y fabricaría un stale).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number else None
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.timestamp()
    return None


def dimension_freshness(
    dimension: str,
    last_at: Any,
    *,
    now: float,
    max_age_seconds: float | None,
) -> DimensionFreshness:
    """Estado de una dimensión desde su último instante y el umbral declarado."""
    instant = _epoch(last_at)
    if instant is None:
        return DimensionFreshness(dimension, None, None, FRESHNESS_UNKNOWN)
    age = max(0.0, float(now) - instant)
    if max_age_seconds is not None and age > float(max_age_seconds):
        return DimensionFreshness(dimension, instant, age, FRESHNESS_STALE)
    return DimensionFreshness(dimension, instant, age, FRESHNESS_FRESH)


def assess_data_freshness(
    *,
    now: float,
    market_data_at: Any = None,
    atr_at: Any = None,
    quote_at: Any = None,
    volume_at: Any = None,
    policy: FreshnessPolicy | None = None,
) -> FreshnessAssessment:
    """Lectura agregada por dimensión. Ver ``FreshnessAssessment.blocks_new_entry``."""
    resolved = policy if policy is not None else FreshnessPolicy()
    readings = (
        dimension_freshness(
            "market_data",
            market_data_at,
            now=now,
            max_age_seconds=resolved.max_market_data_age_s,
        ),
        dimension_freshness("atr", atr_at, now=now, max_age_seconds=resolved.max_atr_age_s),
        dimension_freshness("quote", quote_at, now=now, max_age_seconds=resolved.max_quote_age_s),
        dimension_freshness(
            "volume", volume_at, now=now, max_age_seconds=resolved.max_volume_age_s
        ),
    )
    return FreshnessAssessment(dimensions=readings, as_of=float(now))


__all__ = [
    "FRESHNESS_FRESH",
    "FRESHNESS_STALE",
    "FRESHNESS_UNKNOWN",
    "FRESHNESS_DIMENSIONS",
    "DimensionFreshness",
    "FreshnessAssessment",
    "FreshnessPolicy",
    "FreshnessStatus",
    "assess_data_freshness",
    "dimension_freshness",
]
