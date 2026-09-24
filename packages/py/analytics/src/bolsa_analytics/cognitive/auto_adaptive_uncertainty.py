"""AUTO-19A — Incertidumbre del edge y confianza de EDGE del Adaptive AUTO (PURA y READ-ONLY).

Cierra el hueco que ``AUTO-18`` dejó declarado: la confianza publicaba **cuánto** se había medido
(``confidence``/``coverage``/``effective_n``) y una expectancy **encogida**, pero no publicaba el
**intervalo de incertidumbre** del número ni separaba la calidad de la MEDICIÓN de la del EDGE.

Qué publica, por ``strategyVersion`` (y por celda ``strategy × regime``):

* **``expectancy_interval``** — el intervalo de confianza (por defecto 90 %) de la expectancy, por
  **bootstrap de episodios** (``bootstrap_episodes_v1``): se remuestrean **rachas de régimen** con
  reemplazo, no ciclos sueltos, de modo que la incertidumbre respeta la MISMA noción de
  independencia que ``AUTO-18`` fijó (100 ciclos de una sola fase no son 100 observaciones). El
  intervalo contiene siempre al punto publicado por construcción.
* **``edge_confidence``** — ``HIGH``/``MEDIUM``/``LOW``/``UNKNOWN``: la confianza de que **haya
  edge**, derivada del signo del intervalo frente a cero y modulada por la cobertura, el deterioro
  y la base del neto. Es un eje **distinto** de la banda de medición: ``measurement = HIGH`` con
  ``edge = LOW`` significa "sabemos bien que ahora mismo no muestra edge", y ``measurement = LOW``
  con ``edge = UNKNOWN`` significa "no sabemos lo suficiente". Ausencia de medición ⇒ ``UNKNOWN``,
  nunca un ``LOW`` por defecto.
* **``dispersion_r``** — la desviación de las medias bootstrap: una lectura mínima de estabilidad
  del edge (dos edges con la misma media y distinta dispersión no son igual de fiables).

Disciplina de medición (la del repo, y aquí es el punto entero del módulo):

* **Lo que no se midió se declara.** Sin ciclos medidos no hay número que encuadrar (``None`` +
  ``no_cycles``); con menos de ``min_episodes`` rachas no hay percentil honesto: se publica solo el
  punto, se declara ``insufficient_episodes`` y el edge queda ``UNKNOWN``. Nunca se fabrica un
  intervalo que la muestra no sostiene.
* **La independencia se mide una sola vez.** El material de la racha sale de ``regime_episodes``
  (``AUTO-19A``): la incertidumbre NO reimplementa la semántica de episodios de ``AUTO-18``.
* **La ausencia no es un defecto.** Una versión sin lectura de confianza sigue publicando su
  intervalo y su punto; lo que falta (cobertura, deterioro) se declara ``UNKNOWN`` y no modula.

**Read-only por contrato**: no modifica pesos, ni sizing, ni estado, ni el reparto (el sello sigue
en ``auto18-v1``). La incertidumbre es EVIDENCIA publicada, nunca un permiso.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import pstdev
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_BASIS_DATA_DEGRADED,
    ADAPTIVE_BASIS_UNKNOWN,
    ADAPTIVE_COVERAGE_LOW,
    ADAPTIVE_COVERAGE_UNCOVERED,
    ADAPTIVE_DECAY_SEVERE,
    ADAPTIVE_DECAY_UNKNOWN,
    AdaptiveConfidence,
    RegimeConfidence,
    StrategyConfidence,
    coverage_band,
    order_cycles_by_instant,
    regime_episodes,
)

__all__ = [
    "ADAPTIVE_EDGE_HIGH",
    "ADAPTIVE_EDGE_LOW",
    "ADAPTIVE_EDGE_MEDIUM",
    "ADAPTIVE_EDGE_UNKNOWN",
    "ADAPTIVE_EDGE_NOTE_BASIS_DEGRADED",
    "ADAPTIVE_EDGE_NOTE_CROSSES_ZERO",
    "ADAPTIVE_EDGE_NOTE_LOW_COVERAGE",
    "ADAPTIVE_EDGE_NOTE_NEGATIVE",
    "ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT",
    "ADAPTIVE_EDGE_NOTE_SEVERE_DECAY",
    "ADAPTIVE_INTERVAL_LEVEL_DEFAULT",
    "ADAPTIVE_INTERVAL_LEVEL_MAX",
    "ADAPTIVE_INTERVAL_LEVEL_MIN",
    "ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT",
    "ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT",
    "ADAPTIVE_INTERVAL_SEED_DEFAULT",
    "ADAPTIVE_UNCERTAINTY_INSUFFICIENT_EPISODES",
    "ADAPTIVE_UNCERTAINTY_METHOD",
    "ADAPTIVE_UNCERTAINTY_NO_CYCLES",
    "ADAPTIVE_UNCERTAINTY_UNDATED",
    "AdaptiveUncertainty",
    "ExpectancyInterval",
    "RegimeUncertainty",
    "StrategyUncertainty",
    "build_adaptive_uncertainty",
    "percentile",
]

#: Método declarado del intervalo: bootstrap de percentil sobre RACHAS de régimen (episodios),
#: no sobre ciclos sueltos. Cambiar el método obliga a declararlo aquí (y a subir el sello de la
#: lectura), porque dos intervalos con el mismo aspecto podrían venir de supuestos distintos.
ADAPTIVE_UNCERTAINTY_METHOD = "bootstrap_episodes_v1"

#: Nivel de confianza del intervalo (90 % por defecto). Se acota a ``[0.5, 0.99]``: por debajo de
#: 0.5 el "intervalo" no afirma nada y por encima de 0.99 el percentil depende de colas que pocas
#: muestras no tienen.
ADAPTIVE_INTERVAL_LEVEL_DEFAULT = 0.90
ADAPTIVE_INTERVAL_LEVEL_MIN = 0.5
ADAPTIVE_INTERVAL_LEVEL_MAX = 0.99
#: Remuestreos del bootstrap. Declarado para que la lectura sea reproducible: mismo material +
#: misma semilla + mismos remuestreos ⇒ mismo intervalo.
ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT = 2000
#: Semilla declarada: la reproducibilidad del intervalo no puede depender del reloj ni del azar
#: global del proceso.
ADAPTIVE_INTERVAL_SEED_DEFAULT = 42
#: Rachas mínimas para afirmar un intervalo. Con una sola racha el bootstrap devolvería el mismo
#: número siempre: no hay incertidumbre que medir, y ese hueco se DECLARA en vez de disfrazarse de
#: intervalo estrecho.
ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT = 2

# ── Bandas de CONFIANZA DE EDGE (eje PROPIO, distinto de la banda de medición) ───────
#
# La banda de medición de ``AUTO-12``/``AUTO-18`` dice "qué bien se midió". Esta dice "qué
# probable es que haya edge". No comparten vocabulario con la banda de medición en el caso
# ausente (``UNKNOWN`` no existe allí), y por eso se publican en campos separados.
#: El intervalo es positivo y estrecho de sobra: hay edge demostrado (dentro de la cobertura).
ADAPTIVE_EDGE_HIGH = "HIGH"
#: El punto es positivo pero el intervalo cruza el cero: indicio, no prueba.
ADAPTIVE_EDGE_MEDIUM = "MEDIUM"
#: El punto no es positivo (o el intervalo es negativo): sabemos que no hay edge.
ADAPTIVE_EDGE_LOW = "LOW"
#: No hay medición suficiente para afirmar nada del edge. NO es "edge bajo".
ADAPTIVE_EDGE_UNKNOWN = "UNKNOWN"

#: Notas DECLARADAS de la confianza de edge (viajan con la lectura, no solo al log).
ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT = "no_measurement"
ADAPTIVE_EDGE_NOTE_CROSSES_ZERO = "interval_crosses_zero"
ADAPTIVE_EDGE_NOTE_NEGATIVE = "interval_negative"
ADAPTIVE_EDGE_NOTE_LOW_COVERAGE = "low_coverage"
ADAPTIVE_EDGE_NOTE_SEVERE_DECAY = "severe_decay"
ADAPTIVE_EDGE_NOTE_BASIS_DEGRADED = "basis_degraded"

#: Huecos DECLARADOS de la lectura de incertidumbre.
ADAPTIVE_UNCERTAINTY_NO_CYCLES = "no_cycles"
ADAPTIVE_UNCERTAINTY_INSUFFICIENT_EPISODES = "insufficient_episodes"
#: El material traía filas sin instante legible: se ordenan al final y se declara el hueco.
ADAPTIVE_UNCERTAINTY_UNDATED = "undated_cycles"

#: Orden creciente de las bandas de EDGE (``UNKNOWN`` queda fuera: no es un nivel, es una ausencia).
_EDGE_ORDER: tuple[str, ...] = (ADAPTIVE_EDGE_LOW, ADAPTIVE_EDGE_MEDIUM, ADAPTIVE_EDGE_HIGH)


def _round4(value: float) -> float:
    """Redondeo de la casa (4 decimales), el mismo de ``AUTO-7``/``AUTO-9``/``AUTO-18``.

    Un cero se normaliza a ``0.0`` positivo: ``-0.0`` y ``0.0`` son el mismo número y publicar el
    signo del redondeo sería ruido en la evidencia.
    """
    rounded = round(value, 4)
    return 0.0 if rounded == 0 else rounded


def percentile(sorted_values: Sequence[float], q: float) -> float | None:
    """(PURA) percentil por interpolación lineal sobre una lista YA ordenada.

    Determinista y sin dependencias: la incertidumbre no puede cambiar de resultado por la versión
    de una librería. ``None`` sobre una lista vacía (la ausencia se declara, no se rellena).
    """
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * min(max(float(q), 0.0), 1.0)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(sorted_values[int(position)])
    weight = position - low
    return float(sorted_values[low]) * (1.0 - weight) + float(sorted_values[high]) * weight


@dataclass(frozen=True, slots=True)
class ExpectancyInterval:
    """Intervalo de confianza de una expectancy de R, con su método y su muestra declarados.

    ``lower``/``upper`` son ``None`` cuando no hay rachas suficientes para un percentil honesto:
    en ese caso el ``point`` sigue siendo el punto medido y la ausencia se declara en ``notes``.
    El intervalo contiene siempre al ``point`` (se ensancha si hiciera falta): un intervalo que no
    contuviera su propio punto sería una contradicción publicada.
    """

    point: float | None
    lower: float | None
    upper: float | None
    level: float
    method: str
    effective_n: int
    episodes: int
    measured_n: int
    resamples: int
    dispersion_r: float | None = None
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "point": self.point,
            "lower": self.lower,
            "upper": self.upper,
            "level": self.level,
            "method": self.method,
            "effectiveN": self.effective_n,
            "episodes": self.episodes,
            "measuredN": self.measured_n,
            "resamples": self.resamples,
            "dispersionR": self.dispersion_r,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class RegimeUncertainty:
    """Incertidumbre y confianza de EDGE de UNA celda ``strategyVersion × regime``."""

    regime: str
    interval: ExpectancyInterval
    edge_confidence: str
    coverage: str | None = None
    notes: tuple[str, ...] = ()

    @property
    def dispersion_r(self) -> float | None:
        return self.interval.dispersion_r

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "expectancyInterval": self.interval.as_dict(),
            "edgeConfidence": self.edge_confidence,
            "coverage": self.coverage,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class StrategyUncertainty:
    """Incertidumbre y confianza de EDGE de UNA ``strategyVersion`` (con su desglose por régimen)."""

    strategy_version: str
    interval: ExpectancyInterval
    edge_confidence: str
    by_regime: tuple[RegimeUncertainty, ...] = ()
    coverage: str | None = None
    notes: tuple[str, ...] = ()

    @property
    def dispersion_r(self) -> float | None:
        return self.interval.dispersion_r

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "expectancyInterval": self.interval.as_dict(),
            "edgeConfidence": self.edge_confidence,
            "coverage": self.coverage,
            "byRegime": [cell.as_dict() for cell in self.by_regime],
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveUncertainty:
    """Lectura de incertidumbre del período: por estrategia (y sus celdas), con huecos declarados."""

    by_strategy: tuple[StrategyUncertainty, ...]
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT
    method: str = ADAPTIVE_UNCERTAINTY_METHOD
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT
    available: bool = False
    notes: tuple[str, ...] = ()

    def uncertainty_for(self, strategy_version: str) -> StrategyUncertainty | None:
        key = str(strategy_version or "")
        for row in self.by_strategy:
            if row.strategy_version == key:
                return row
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "level": self.level,
            "resamples": self.resamples,
            "seed": self.seed,
            "available": self.available,
            "byStrategy": {
                row.strategy_version: row.as_dict() for row in self.by_strategy
            },
            "notes": list(self.notes),
        }


def _interval_from_episodes(
    episodes: Sequence[Sequence[float]],
    *,
    level: float,
    resamples: int,
    seed: int,
    min_episodes: int,
) -> ExpectancyInterval:
    """(PURA) intervalo de percentil por bootstrap de EPISODIOS (rachas) con reemplazo.

    Cada episodio es una racha de régimen: se remuestrean rachas enteras, de modo que la
    dependencia dentro de una misma fase de mercado no se destruye (el error que el bootstrap
    ingenuo por ciclos cometería). Sin valores no hay punto ni intervalo (``no_cycles``); con
    menos de ``min_episodes`` rachas no hay percentil honesto: se publica el punto y se declara
    (``insufficient_episodes``) — nunca un intervalo estrecho fabricado con una sola racha.
    """
    values = [float(value) for episode in episodes for value in episode]
    point = _round4(sum(values) / len(values)) if values else None
    bursts = [tuple(float(v) for v in episode) for episode in episodes if episode]
    effective_n = len(bursts)
    if point is None:
        return ExpectancyInterval(
            point=None,
            lower=None,
            upper=None,
            level=level,
            method=ADAPTIVE_UNCERTAINTY_METHOD,
            effective_n=0,
            episodes=0,
            measured_n=0,
            resamples=0,
            notes=(ADAPTIVE_UNCERTAINTY_NO_CYCLES,),
        )
    if effective_n < max(1, int(min_episodes)):
        return ExpectancyInterval(
            point=point,
            lower=None,
            upper=None,
            level=level,
            method=ADAPTIVE_UNCERTAINTY_METHOD,
            effective_n=effective_n,
            episodes=effective_n,
            measured_n=len(values),
            resamples=0,
            notes=(ADAPTIVE_UNCERTAINTY_INSUFFICIENT_EPISODES,),
        )

    generator = random.Random(seed)
    means: list[float] = []
    for _ in range(max(1, int(resamples))):
        total = 0.0
        count = 0
        for _ in range(effective_n):
            episode = bursts[generator.randrange(effective_n)]
            total += sum(episode)
            count += len(episode)
        means.append(total / count if count else 0.0)
    means.sort()
    tail = (1.0 - level) / 2.0
    lower = percentile(means, tail)
    upper = percentile(means, 1.0 - tail)
    # El intervalo CONTIENE al punto publicado: ensanchar es honesto, contradecirse no.
    assert lower is not None and upper is not None  # la lista nunca está vacía aquí
    lower_value = _round4(min(lower, point))
    upper_value = _round4(max(upper, point))
    dispersion = _round4(pstdev(means)) if len(means) > 1 else 0.0
    return ExpectancyInterval(
        point=point,
        lower=lower_value,
        upper=upper_value,
        level=level,
        method=ADAPTIVE_UNCERTAINTY_METHOD,
        effective_n=effective_n,
        episodes=effective_n,
        measured_n=len(values),
        resamples=max(1, int(resamples)),
        dispersion_r=dispersion,
    )


def _edge_confidence(
    interval: ExpectancyInterval,
    *,
    coverage: str | None,
    decay: str,
    basis_transition: str,
    min_episodes: int,
) -> tuple[str, tuple[str, ...]]:
    """(PURA) banda de EDGE a partir del intervalo y de lo que se sabe de la población.

    Reglas declaradas, en orden:

    1. Sin medición suficiente (``point`` nulo o menos de ``min_episodes`` rachas) ⇒
       ``UNKNOWN``: no saber no es tener un edge bajo.
    2. ``lower > 0`` ⇒ base ``HIGH`` (el intervalo entero es positivo).
    3. el punto positivo que cruza el cero ⇒ base ``MEDIUM`` (indicio, no prueba).
    4. el resto ⇒ base ``LOW`` (el punto no es positivo: sabemos que no hay edge).

    Y después se **degradan** un escalón (con suelo ``LOW``, nunca a ``UNKNOWN``) los hechos que
    debilitan la generalidad: cobertura ``LOW``/``UNCOVERED``, deterioro ``SEVERE`` y base del neto
    ``DATA_DEGRADED``. Cada degradación añade su nota: un ``MEDIUM`` no dice por sí solo si le
    faltó cobertura o le pesó el deterioro.
    """
    notes: list[str] = []
    if interval.point is None or interval.lower is None or interval.upper is None:
        return ADAPTIVE_EDGE_UNKNOWN, (ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT,)
    if interval.effective_n < max(1, int(min_episodes)):
        return ADAPTIVE_EDGE_UNKNOWN, (ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT,)
    if interval.lower > 0.0:
        level = ADAPTIVE_EDGE_HIGH
    elif interval.point > 0.0:
        level = ADAPTIVE_EDGE_MEDIUM
        notes.append(ADAPTIVE_EDGE_NOTE_CROSSES_ZERO)
    else:
        level = ADAPTIVE_EDGE_LOW
        notes.append(ADAPTIVE_EDGE_NOTE_NEGATIVE)
    steps = 0
    if coverage in (ADAPTIVE_COVERAGE_LOW, ADAPTIVE_COVERAGE_UNCOVERED):
        steps += 1
        notes.append(ADAPTIVE_EDGE_NOTE_LOW_COVERAGE)
    if decay == ADAPTIVE_DECAY_SEVERE:
        steps += 1
        notes.append(ADAPTIVE_EDGE_NOTE_SEVERE_DECAY)
    if basis_transition == ADAPTIVE_BASIS_DATA_DEGRADED:
        steps += 1
        notes.append(ADAPTIVE_EDGE_NOTE_BASIS_DEGRADED)
    index = _EDGE_ORDER.index(level)
    return _EDGE_ORDER[max(0, index - steps)], tuple(notes)


def _cell_confidence(
    strategy: StrategyConfidence | None, regime: str
) -> RegimeConfidence | None:
    """La banda de confianza de una celda ``(estrategia, régimen)``, o ``None`` si no la hay."""
    if strategy is None:
        return None
    key = str(regime or "").strip().upper()
    for cell in strategy.by_regime:
        if str(cell.regime or "").strip().upper() == key:
            return cell
    return None


def _cell_uncertainty(
    *,
    regime: str,
    episodes: Sequence[Sequence[float]],
    cell: RegimeConfidence | None,
    level: float,
    resamples: int,
    seed: int,
    min_episodes: int,
) -> RegimeUncertainty:
    """(PURA) la incertidumbre de UNA celda de régimen, con la banda de ESA celda como modulador."""
    interval = _interval_from_episodes(
        episodes, level=level, resamples=resamples, seed=seed, min_episodes=min_episodes
    )
    coverage = cell.coverage if cell is not None else None
    if coverage is None:
        coverage = (
            coverage_band(interval.measured_n, interval.effective_n)
            if interval.measured_n > 0
            else None
        )
    decay = cell.decay if cell is not None else ADAPTIVE_DECAY_UNKNOWN
    basis_transition = cell.basis_transition if cell is not None else ADAPTIVE_BASIS_UNKNOWN
    edge, notes = _edge_confidence(
        interval,
        coverage=coverage,
        decay=decay,
        basis_transition=basis_transition,
        min_episodes=min_episodes,
    )
    return RegimeUncertainty(
        regime=regime,
        interval=interval,
        edge_confidence=edge,
        coverage=coverage,
        notes=notes,
    )


def _strategy_uncertainty(
    *,
    version: str,
    episodes: Sequence[tuple[str, tuple[float, ...]]],
    strategy: StrategyConfidence | None,
    level: float,
    resamples: int,
    seed: int,
    min_episodes: int,
) -> StrategyUncertainty:
    """(PURA) la incertidumbre de UNA estrategia, con su celda por régimen heredada del cruce.

    El material de las celdas son las MISMAS rachas agrupadas por su régimen: no se remuestrea un
    segundo material para la celda. Las celdas que declara el cruce (``by_regime``) mandan en la
    composición —una celda sin racha propia queda con punto ``None`` y lo declara—, de modo que la
    incertidumbre habla de las celdas que la confianza ya publica.
    """
    pooled = [values for _regime, values in episodes]
    interval = _interval_from_episodes(
        pooled, level=level, resamples=resamples, seed=seed, min_episodes=min_episodes
    )
    coverage = strategy.coverage if strategy is not None else None
    if coverage is None:
        coverage = (
            coverage_band(interval.measured_n, interval.effective_n)
            if interval.measured_n > 0
            else None
        )
    decay = strategy.decay if strategy is not None else ADAPTIVE_DECAY_UNKNOWN
    basis_transition = (
        strategy.basis_transition if strategy is not None else ADAPTIVE_BASIS_UNKNOWN
    )
    edge, notes = _edge_confidence(
        interval,
        coverage=coverage,
        decay=decay,
        basis_transition=basis_transition,
        min_episodes=min_episodes,
    )

    grouped: dict[str, list[tuple[float, ...]]] = {}
    for regime, values in episodes:
        grouped.setdefault(str(regime or "").strip().upper(), []).append(tuple(values))
    declared = [cell.regime for cell in strategy.by_regime] if strategy is not None else []
    regimes: list[str] = []
    seen_keys: set[str] = set()
    for regime in declared:
        key = str(regime or "").strip().upper()
        if key and key not in seen_keys:
            seen_keys.add(key)
            regimes.append(str(regime))
    for key in grouped:
        if key and key not in seen_keys:
            seen_keys.add(key)
            regimes.append(key)
    cells = tuple(
        _cell_uncertainty(
            regime=regime,
            episodes=grouped.get(str(regime or "").strip().upper(), ()),
            cell=_cell_confidence(strategy, regime),
            level=level,
            resamples=resamples,
            seed=seed,
            min_episodes=min_episodes,
        )
        for regime in regimes
    )
    return StrategyUncertainty(
        strategy_version=version,
        interval=interval,
        edge_confidence=edge,
        by_regime=cells,
        coverage=coverage,
        notes=notes,
    )


def build_adaptive_uncertainty(
    cycles: Iterable[Any] | None = None,
    *,
    confidence: AdaptiveConfidence | None = None,
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
    min_episodes: int = ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
) -> AdaptiveUncertainty:
    """(PURA) incertidumbre del edge desde los ciclos del MISMO productor que el informe.

    ``cycles`` son las filas de ciclo de ``AUTO-7``/``AUTO-9`` (con ``closedAt`` cuando se pudo
    medir): las rachas se cuentan sobre el orden por instante, igual que en ``AUTO-18``, así que la
    independencia que acota el peso es la misma que la que encuadra el intervalo. ``confidence`` es
    OPCIONAL: cuando el llamante la aporta, la cobertura, el deterioro y la base del neto salen de
    ESA lectura (una sola medición, dos publicaciones); sin ella, la cobertura se clasifica con la
    misma convención y el resto queda ``UNKNOWN`` —el hueco no se inventa—.

    Sin ciclos se devuelve una lectura VACÍA declarada (``no_cycles``), nunca ``[]`` mudo.
    """
    rows = list(cycles or ())
    resolved_level = min(
        max(float(level), ADAPTIVE_INTERVAL_LEVEL_MIN), ADAPTIVE_INTERVAL_LEVEL_MAX
    )
    resolved_resamples = max(1, int(resamples))
    resolved_min = max(1, int(min_episodes))
    if not rows:
        return AdaptiveUncertainty(
            by_strategy=(),
            level=resolved_level,
            resamples=resolved_resamples,
            seed=int(seed),
            available=False,
            notes=(ADAPTIVE_UNCERTAINTY_NO_CYCLES,),
        )

    ordered, undated = order_cycles_by_instant(rows)
    runs = regime_episodes(ordered)
    notes: list[str] = []
    if undated:
        # Filas sin instante legible: se ordenan al final y el hueco se declara (no se supone fecha).
        notes.append(ADAPTIVE_UNCERTAINTY_UNDATED)

    if confidence is not None:
        versions = [row.strategy_version for row in confidence.by_strategy]
    else:
        versions = sorted(runs)
    unique: list[str] = []
    seen: set[str] = set()
    for raw in versions:
        version = str(raw or "")
        if version and version not in seen:
            seen.add(version)
            unique.append(version)

    by_strategy = tuple(
        _strategy_uncertainty(
            version=version,
            episodes=runs.get(version, ()),
            strategy=confidence.confidence_for(version) if confidence is not None else None,
            level=resolved_level,
            resamples=resolved_resamples,
            seed=int(seed),
            min_episodes=resolved_min,
        )
        for version in unique
    )
    return AdaptiveUncertainty(
        by_strategy=by_strategy,
        level=resolved_level,
        resamples=resolved_resamples,
        seed=int(seed),
        available=bool(by_strategy),
        notes=tuple(notes),
    )
