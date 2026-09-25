"""AUTO-21 — CORRELACIÓN entre estrategias por cubo temporal (PURA y READ-ONLY).

Qué pregunta: cuando dos ``strategyVersion`` operan sobre el MISMO material, ¿se mueven juntas?
Hasta ahora el sistema recibía la correlación como un **escalar declarado por el llamante**
(``TradeContext.correlation``) y la usaba como restricción del optimizador; **nadie la medía** entre
las estrategias del propio AUTO. Esta pieza la mide, y solo la **publica**: no ordena el reparto.

Cómo la mide, sin inventar sincronía que el material no tiene:

* **Alineación por CUBO temporal declarado** (día por defecto, también semana y mes) derivado de
  ``closedAt``. Dos estrategias rara vez cierran ciclos en el mismo instante; exigir instantes
  idénticos declararía "sin solape" casi siempre. Cada cubo aporta la media de R de cada estrategia
  en ese tramo y la correlación es de **Pearson** sobre los cubos COMPARTIDOS.
* **Sin cubos compartidos no hay correlación.** Si las series no se cruzan, o se cruzan en menos
  cubos que el mínimo declarado, o una es constante (varianza nula: no hay relación que medir), la
  correlación es ``None`` y el hueco se **declara** (``no_shared_buckets`` / ``insufficient_buckets``
  / ``constant_series``). Nunca un ``0`` que diría "no correlacionadas" sin haberlo medido.
* **Filas sin instante legible se declaran** (``undated_cycles``): no se les supone un cubo.

Read-only por contrato: no toca el optimizador, la reserva de cartera, el plan ni el gobernador. La
correlación es EVIDENCIA publicada, nunca un permiso de sizing ni una restricción aplicada.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    closed_instant,
    cycle_field,
    measured_r,
    order_cycles_by_instant,
)

__all__ = [
    "CORRELATION_BUCKETS",
    "CORRELATION_BUCKET_DEFAULT",
    "CORRELATION_BUCKET_DAY",
    "CORRELATION_BUCKET_MONTH",
    "CORRELATION_BUCKET_WEEK",
    "CORRELATION_MIN_BUCKETS_DEFAULT",
    "CORRELATION_NOTE_CONSTANT_SERIES",
    "CORRELATION_NOTE_INSUFFICIENT_BUCKETS",
    "CORRELATION_NOTE_NO_CYCLES",
    "CORRELATION_NOTE_NO_SHARED_BUCKETS",
    "CORRELATION_NOTE_UNDATED_CYCLES",
    "STRATEGY_CORRELATION_METHOD",
    "StrategyCorrelationReport",
    "StrategyPairCorrelation",
    "bucket_key",
    "build_strategy_correlation_report",
    "pearson_correlation",
]

#: Método declarado de la lectura. Cambiarlo (otra alineación, otra métrica) obliga a subir el
#: sello: dos matrices con el mismo aspecto no pueden venir de instrumentos distintos.
STRATEGY_CORRELATION_METHOD = "bucket_correlation_v1"

CORRELATION_BUCKET_DAY = "day"
CORRELATION_BUCKET_WEEK = "week"
CORRELATION_BUCKET_MONTH = "month"
#: Cubos soportados. Un valor desconocido cae al defecto declarado en vez de inventar uno nuevo.
CORRELATION_BUCKETS: tuple[str, ...] = (
    CORRELATION_BUCKET_DAY,
    CORRELATION_BUCKET_WEEK,
    CORRELATION_BUCKET_MONTH,
)
CORRELATION_BUCKET_DEFAULT = CORRELATION_BUCKET_DAY

#: Cubos COMPARTIDOS mínimos para publicar una correlación. Con 2 cubos, Pearson es siempre ±1 y
#: afirmaría una relación perfecta que la muestra no sostiene; con menos de 4, el ruido manda.
CORRELATION_MIN_BUCKETS_DEFAULT = 4

#: Huecos DECLARADOS de la lectura de correlación.
CORRELATION_NOTE_NO_CYCLES = "no_cycles"
CORRELATION_NOTE_NO_SHARED_BUCKETS = "no_shared_buckets"
CORRELATION_NOTE_INSUFFICIENT_BUCKETS = "insufficient_buckets"
CORRELATION_NOTE_CONSTANT_SERIES = "constant_series"
CORRELATION_NOTE_UNDATED_CYCLES = "undated_cycles"


def _round4(value: float) -> float:
    rounded = round(float(value), 4)
    return 0.0 if rounded == 0 else rounded


def resolve_bucket(bucket: str | None) -> str:
    """(PURA) cubo declarado, acotado a los soportados; desconocido ⇒ el defecto declarado."""
    key = str(bucket or "").strip().lower()
    return key if key in CORRELATION_BUCKETS else CORRELATION_BUCKET_DEFAULT


def bucket_key(instant: Any, bucket: str) -> str:
    """(PURA) clave de cubo temporal de un instante: ``AAAA-MM-DD`` / ``AAAA-Www`` / ``AAAA-MM``.

    Es una clave **ordenable** y estable (ISO-8601 para el día, ISO-week para la semana): dos
    instantes del mismo cubo comparten clave sin importar la zona horaria con que se parsearon.
    """
    resolved = resolve_bucket(bucket)
    if resolved == CORRELATION_BUCKET_MONTH:
        return f"{instant.year:04d}-{instant.month:02d}"
    if resolved == CORRELATION_BUCKET_WEEK:
        iso = instant.isocalendar()
        return f"{iso.year:04d}-W{iso.week:02d}"
    return f"{instant.year:04d}-{instant.month:02d}-{instant.day:02d}"


def pearson_correlation(
    left: Sequence[float], right: Sequence[float]
) -> tuple[float | None, tuple[str, ...]]:
    """(PURA) correlación de Pearson sobre dos series YA alineadas, con su hueco declarado.

    Sin al menos 2 puntos no hay correlación; si alguna serie es constante (varianza cero) la
    correlación es indefinida y se declara ``constant_series`` en vez de publicar un ``0`` falso.
    La correlación es invariante a la escala, así que la convención de momentos (población o
    muestra) no cambia el número.
    """
    count = min(len(left), len(right))
    if count < 2:
        return None, (CORRELATION_NOTE_INSUFFICIENT_BUCKETS,)
    left_values = [float(value) for value in left[:count]]
    right_values = [float(value) for value in right[:count]]
    mean_left = sum(left_values) / count
    mean_right = sum(right_values) / count
    covariance = sum(
        (value - mean_left) * (other - mean_right)
        for value, other in zip(left_values, right_values, strict=True)
    )
    variance_left = sum((value - mean_left) ** 2 for value in left_values)
    variance_right = sum((other - mean_right) ** 2 for other in right_values)
    if variance_left <= 0.0 or variance_right <= 0.0:
        return None, (CORRELATION_NOTE_CONSTANT_SERIES,)
    coefficient = covariance / math.sqrt(variance_left * variance_right)
    # Se acota a [-1, 1] por el error de coma flotante (el cociente puede salir 1.0000000002).
    return _round4(max(-1.0, min(1.0, coefficient))), ()


def bucket_series(
    rows: Sequence[Any], *, bucket: str = CORRELATION_BUCKET_DEFAULT
) -> tuple[dict[str, dict[str, float]], int]:
    """(PURA) medias de R por ``(versión, cubo)`` y nº de filas sin instante legible.

    Solo entran ciclos con R medible y cubo resoluble: una fila sin instante no se le supone fecha
    (se cuenta y se declara). La media por cubo es la unidad que hace comparables dos estrategias que
    cierran a distinta frecuencia dentro del mismo tramo.
    """
    resolved = resolve_bucket(bucket)
    grouped: dict[str, dict[str, list[float]]] = {}
    undated = 0
    for row in rows:
        version = str(cycle_field(row, "strategyVersion", "strategy_version") or "")
        if not version:
            continue
        value = measured_r(row)
        if value is None:
            continue
        instant = closed_instant(row)
        if instant is None:
            undated += 1
            continue
        grouped.setdefault(version, {}).setdefault(bucket_key(instant, resolved), []).append(
            float(value)
        )
    means = {
        version: {key: sum(values) / len(values) for key, values in buckets.items()}
        for version, buckets in grouped.items()
    }
    return means, undated


@dataclass(frozen=True, slots=True)
class StrategyPairCorrelation:
    """Correlación de UN par ordenado de estrategias, con los cubos que la sostienen."""

    left: str
    right: str
    correlation: float | None
    shared_buckets: int
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "left": self.left,
            "right": self.right,
            "correlation": self.correlation,
            "sharedBuckets": self.shared_buckets,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class StrategyCorrelationReport:
    """La matriz declarada: los pares medidos (y los que no se pudieron medir) por cubo temporal."""

    strategies: tuple[str, ...]
    pairs: tuple[StrategyPairCorrelation, ...]
    bucket: str = CORRELATION_BUCKET_DEFAULT
    method: str = STRATEGY_CORRELATION_METHOD
    min_buckets: int = CORRELATION_MIN_BUCKETS_DEFAULT
    notes: tuple[str, ...] = ()

    def pair(self, left: str, right: str) -> StrategyPairCorrelation | None:
        for row in self.pairs:
            if {row.left, row.right} == {left, right}:
                return row
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "bucket": self.bucket,
            "minBuckets": self.min_buckets,
            "strategies": list(self.strategies),
            "pairs": [row.as_dict() for row in self.pairs],
            "notes": list(self.notes),
        }


def build_strategy_correlation_report(
    cycles: Iterable[Any] | None = None,
    *,
    bucket: str = CORRELATION_BUCKET_DEFAULT,
    min_buckets: int = CORRELATION_MIN_BUCKETS_DEFAULT,
) -> StrategyCorrelationReport:
    """(PURA) mide la correlación de cada par de estrategias sobre los cubos COMPARTIDOS.

    Sin ciclos devuelve una matriz VACÍA declarada (``no_cycles``), nunca ``[]`` mudo. Cada par
    publica su número **o** su hueco, y los pares se ordenan por nombre para que la matriz sea
    determinista (el orden de llegada del material no puede cambiar la lectura).
    """
    rows = list(cycles or ())
    resolved_bucket = resolve_bucket(bucket)
    resolved_min = max(2, int(min_buckets))
    if not rows:
        return StrategyCorrelationReport(
            strategies=(),
            pairs=(),
            bucket=resolved_bucket,
            min_buckets=resolved_min,
            notes=(CORRELATION_NOTE_NO_CYCLES,),
        )

    ordered, undated = order_cycles_by_instant(rows)
    series, unreadable = bucket_series(ordered, bucket=resolved_bucket)
    strategies = tuple(sorted(series))
    pairs: list[StrategyPairCorrelation] = []
    for index, left in enumerate(strategies):
        for right in strategies[index + 1 :]:
            shared = sorted(set(series[left]) & set(series[right]))
            if not shared:
                pairs.append(
                    StrategyPairCorrelation(
                        left=left,
                        right=right,
                        correlation=None,
                        shared_buckets=0,
                        notes=(CORRELATION_NOTE_NO_SHARED_BUCKETS,),
                    )
                )
                continue
            if len(shared) < resolved_min:
                pairs.append(
                    StrategyPairCorrelation(
                        left=left,
                        right=right,
                        correlation=None,
                        shared_buckets=len(shared),
                        notes=(CORRELATION_NOTE_INSUFFICIENT_BUCKETS,),
                    )
                )
                continue
            left_values = [series[left][key] for key in shared]
            right_values = [series[right][key] for key in shared]
            correlation, notes = pearson_correlation(left_values, right_values)
            pairs.append(
                StrategyPairCorrelation(
                    left=left,
                    right=right,
                    correlation=correlation,
                    shared_buckets=len(shared),
                    notes=notes,
                )
            )

    notes: list[str] = []
    if undated or unreadable:
        notes.append(CORRELATION_NOTE_UNDATED_CYCLES)
    return StrategyCorrelationReport(
        strategies=strategies,
        pairs=tuple(pairs),
        bucket=resolved_bucket,
        min_buckets=resolved_min,
        notes=tuple(notes),
    )
