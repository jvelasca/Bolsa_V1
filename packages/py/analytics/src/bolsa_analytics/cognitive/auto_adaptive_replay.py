"""AUTO-19A — Batería de REPLAY estadístico out-of-sample del AUTO (PURA y READ-ONLY).

Qué pregunta, exactamente: ¿las estadísticas de decisión de ``AUTO-18`` (el **shrinkage**, el
``effective_N``, la **banda de medición** y la **cobertura**) predicen mejor lo que de verdad pasó
**fuera de muestra**? El replay parte cada estrategia en un tramo **in-sample** (IS) y un tramo
**out-of-sample** (OOS) por orden **cronológico**, mide con el motor real (``auto_adaptive_confidence``
+ ``auto_adaptive_uncertainty``) sobre el IS, y compara la predicción con la expectancy REALIZADA
del OOS.

Cuatro preguntas, cada una con veredicto ``supported``/``not_supported``/``inconclusive``:

1. ``shrinkage_improves_oos`` — ¿el shrinkage reduce el error ``|pred_IS − real_OOS|`` frente al
   crudo, sin empeorar el acierto de signo?
2. ``effective_n_improves_calibration`` — ¿las celdas con ``effective_N`` alto tienen menos error
   OOS que las de ``effective_N`` bajo?
3. ``high_confidence_is_more_stable`` — ¿la banda de medición ``HIGH`` produce resultados OOS más
   estables (menos dispersión) que ``LOW``?
4. ``coverage_improves_selection`` — ¿las celdas con cobertura ``HIGH`` del régimen que dominó el
   OOS tienen menos error que las no cubiertas?

Disciplina (lo que hace honesto al instrumento):

* **Replay ESTADÍSTICO, no ejecución.** No re-simula órdenes ni toca la base de datos: re-aplica las
  estadísticas de decisión sobre ciclos ya cerrados. Read-only, sin I/O.
* **Sin muestra no hay veredicto.** Cada pregunta declara su ``sample`` (nº de celdas comparadas) y
  sin material suficiente (o sin los DOS grupos que exige la comparación) el veredicto es
  ``inconclusive``. Nunca se inventa un ``supported`` por mayoría de uno.
* **Umbrales declarados.** La fracción OOS y los mínimos por tramo son constantes publicadas
  (``REPLAY_*``), no números mágicos escondidos: el veredicto se puede recalcular a mano.
* **Lo que no se pudo leer se declara.** Filas sin instante legible se cuentan y se avisa; una
  estrategia sin material suficiente para partir no entra en las comparaciones (y el hueco aparece
  en ``notes`` de la celda).

El replay NO es una decisión: es un **instrumento de medición**. Su salida no mueve pesos, ni
sizing, ni el reparto (el sello sigue en ``auto18-v1``).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_COVERAGE_HIGH,
    ADAPTIVE_SHRINKAGE_PRIOR_DEFAULT,
    AdaptiveConfidence,
    build_adaptive_confidence,
    cycle_field,
    measured_r,
    order_cycles_by_instant,
    regime_of,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (
    ADAPTIVE_EDGE_HIGH,
    ADAPTIVE_EDGE_LOW,
    ADAPTIVE_EDGE_UNKNOWN,
    ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
    ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    ADAPTIVE_INTERVAL_SEED_DEFAULT,
    AdaptiveUncertainty,
    build_adaptive_uncertainty,
)

__all__ = [
    "REPLAY_METHOD",
    "REPLAY_MIN_CELLS_DEFAULT",
    "REPLAY_MIN_EPISODES_DEFAULT",
    "REPLAY_MIN_IS_MEASURED_DEFAULT",
    "REPLAY_MIN_OOS_MEASURED_DEFAULT",
    "REPLAY_OOS_PCT_DEFAULT",
    "REPLAY_OOS_PCT_MAX",
    "REPLAY_OOS_PCT_MIN",
    "REPLAY_QUESTION_CONFIDENCE",
    "REPLAY_QUESTION_COVERAGE",
    "REPLAY_QUESTION_EFFECTIVE_N",
    "REPLAY_QUESTION_SHRINKAGE",
    "REPLAY_VERDICT_INCONCLUSIVE",
    "REPLAY_VERDICT_NOT_SUPPORTED",
    "REPLAY_VERDICT_SUPPORTED",
    "ReplayCell",
    "ReplayQuestion",
    "ReplayReport",
    "build_replay_report",
]

#: Método declarado del replay. Ampliarlo (p.ej. validar la degradación del edge) obliga a subir
#: este sello: dos informes con el mismo aspecto no pueden venir de instrumentos distintos.
REPLAY_METHOD = "statistical_oos_v1"

#: Fracción del tramo final que se reserva para OOS, con el clamp declarado de ``optimize/holdout``.
#: Ni menos del 10 % (no habría OOS que juzgue) ni más del 40 % (el IS dejaría de medir el edge).
REPLAY_OOS_PCT_DEFAULT = 0.30
REPLAY_OOS_PCT_MIN = 0.10
REPLAY_OOS_PCT_MAX = 0.40

#: Mínimos DECLARADOS por tramo. Sin estos, un split con 2 ciclos "mediría" ruido y lo llamaría
#: predicción: por debajo, la celda no se forma y el hueco se declara.
REPLAY_MIN_IS_MEASURED_DEFAULT = 8
REPLAY_MIN_OOS_MEASURED_DEFAULT = 4
#: Rachas mínimas en el IS para que el bootstrap publique intervalo (mismo mínimo que ``AUTO-19A``).
REPLAY_MIN_EPISODES_DEFAULT = ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT
#: Celdas mínimas para comparar dos grupos. Con una sola celda por grupo no hay comparación: hay
#: anécdota, y la pregunta se declara ``inconclusive``.
REPLAY_MIN_CELLS_DEFAULT = 2

REPLAY_VERDICT_SUPPORTED = "supported"
REPLAY_VERDICT_NOT_SUPPORTED = "not_supported"
REPLAY_VERDICT_INCONCLUSIVE = "inconclusive"

REPLAY_QUESTION_SHRINKAGE = "shrinkage_improves_oos"
REPLAY_QUESTION_EFFECTIVE_N = "effective_n_improves_calibration"
REPLAY_QUESTION_CONFIDENCE = "high_confidence_is_more_stable"
REPLAY_QUESTION_COVERAGE = "coverage_improves_selection"

#: Tolerancia declarada para considerar dos medias "iguales": por debajo, la diferencia es redondeo
#: y la pregunta queda ``inconclusive`` (no se elige un ganador por un epsilon).
_EPSILON = 1e-9


def _round4(value: float | None) -> float | None:
    if value is None:
        return None
    rounded = round(float(value), 4)
    return 0.0 if rounded == 0 else rounded


def _signed_positive(value: float | None) -> bool | None:
    """¿El signo es positivo? ``None`` cuando no hay número (no se inventa un signo)."""
    if value is None:
        return None
    return value > 0.0


def _compare(candidate: float, baseline: float, *, epsilon: float = _EPSILON) -> str:
    """(PURA) veredicto de "candidate predice mejor que baseline" (menor = mejor)."""
    if candidate < baseline - epsilon:
        return REPLAY_VERDICT_SUPPORTED
    if candidate > baseline + epsilon:
        return REPLAY_VERDICT_NOT_SUPPORTED
    return REPLAY_VERDICT_INCONCLUSIVE


@dataclass(frozen=True, slots=True)
class ReplayCell:
    """Una estrategia partida IS/OOS: predicción del IS y expectancy REALIZADA del OOS.

    Todos los números son ``float | None``: ``None`` significa "no se pudo medir" y viaja como tal
    (nunca un cero de relleno). Los errores solo existen si existen sus dos términos.
    """

    strategy_version: str
    is_measured_n: int
    is_episodes: int
    is_effective_n: int
    is_expectancy_r: float | None
    is_shrunk_expectancy_r: float | None
    is_interval_lower: float | None
    is_interval_upper: float | None
    is_confidence: str
    is_coverage: str
    is_edge_confidence: str
    oos_measured_n: int
    oos_expectancy_r: float | None
    oos_dispersion_r: float | None
    oos_regime: str | None
    regime_coverage: str | None
    raw_error: float | None
    shrunk_error: float | None
    raw_sign_ok: bool | None
    shrunk_sign_ok: bool | None
    edge_sign_ok: bool | None
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "isMeasuredN": self.is_measured_n,
            "isEpisodes": self.is_episodes,
            "isEffectiveN": self.is_effective_n,
            "isExpectancyR": _round4(self.is_expectancy_r),
            "isShrunkExpectancyR": _round4(self.is_shrunk_expectancy_r),
            "isIntervalLower": _round4(self.is_interval_lower),
            "isIntervalUpper": _round4(self.is_interval_upper),
            "isConfidence": self.is_confidence,
            "isCoverage": self.is_coverage,
            "isEdgeConfidence": self.is_edge_confidence,
            "oosMeasuredN": self.oos_measured_n,
            "oosExpectancyR": _round4(self.oos_expectancy_r),
            "oosDispersionR": _round4(self.oos_dispersion_r),
            "oosRegime": self.oos_regime,
            "regimeCoverage": self.regime_coverage,
            "rawError": _round4(self.raw_error),
            "shrunkError": _round4(self.shrunk_error),
            "rawSignOk": self.raw_sign_ok,
            "shrunkSignOk": self.shrunk_sign_ok,
            "edgeSignOk": self.edge_sign_ok,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ReplayQuestion:
    """Una de las cuatro preguntas del auditor, con su veredicto y los números que lo sostienen."""

    question: str
    verdict: str
    sample: int
    metrics: dict[str, Any]
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "verdict": self.verdict,
            "sample": self.sample,
            "metrics": dict(self.metrics),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ReplayReport:
    """El informe del replay: celdas medidas + las cuatro respuestas + huecos declarados."""

    cells: tuple[ReplayCell, ...]
    questions: tuple[ReplayQuestion, ...]
    oos_pct: float = REPLAY_OOS_PCT_DEFAULT
    interval_level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT
    method: str = REPLAY_METHOD
    notes: tuple[str, ...] = ()

    def question(self, key: str) -> ReplayQuestion | None:
        for row in self.questions:
            if row.question == key:
                return row
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "oosPct": self.oos_pct,
            "intervalLevel": self.interval_level,
            "seed": self.seed,
            "shrinkPrior": ADAPTIVE_SHRINKAGE_PRIOR_DEFAULT,
            "cells": [cell.as_dict() for cell in self.cells],
            "questions": [row.as_dict() for row in self.questions],
            "notes": list(self.notes),
        }


def _inconclusive(
    question: str, *, metrics: dict[str, Any] | None = None, sample: int = 0
) -> ReplayQuestion:
    return ReplayQuestion(
        question=question, verdict=REPLAY_VERDICT_INCONCLUSIVE, sample=sample, metrics=metrics or {}
    )


def _group_mean(values: Sequence[float]) -> float:
    return float(mean(values))


def _majority_regime(rows: Sequence[Any]) -> str | None:
    """Régimen que DOMINÓ el tramo, o ``None`` si ninguno se declaró (no se supone ``UNKNOWN``)."""
    counts: dict[str, int] = {}
    for row in rows:
        regime = regime_of(row)
        if regime and regime != "UNKNOWN":
            counts[regime] = counts.get(regime, 0) + 1
    if not counts:
        return None
    return max(sorted(counts), key=lambda key: counts[key])


def _regime_coverage(strategy: Any, regime: str | None) -> str | None:
    """Cobertura del IS para el régimen que dominó el OOS, o ``None`` si no hay celda."""
    if strategy is None or regime is None:
        return None
    key = str(regime).strip().upper()
    for cell in strategy.by_regime:
        if str(cell.regime or "").strip().upper() == key:
            return cell.coverage
    return None


def _build_cell(
    version: str,
    measured_rows: Sequence[Any],
    *,
    oos_pct: float,
    min_is: int,
    min_oos: int,
    min_episodes: int,
    interval_level: float,
    resamples: int,
    seed: int,
) -> ReplayCell | None:
    """(PURA) parte una estrategia IS/OOS y mide predicción vs realidad. ``None`` si no se puede."""
    total = len(measured_rows)
    if total < min_is + min_oos:
        return None
    oos_n = max(min_oos, int(round(total * oos_pct)))
    if total - oos_n < min_is:
        oos_n = total - min_is
    if oos_n < min_oos or total - oos_n < min_is:
        return None
    is_rows = tuple(measured_rows[: total - oos_n])
    oos_rows = tuple(measured_rows[total - oos_n :])
    return measure_is_oos_row(
        version,
        is_rows,
        oos_rows,
        min_episodes=min_episodes,
        interval_level=interval_level,
        resamples=resamples,
        seed=seed,
    )


def measure_is_oos_row(
    version: str,
    is_rows: Sequence[Any],
    oos_rows: Sequence[Any],
    *,
    min_episodes: int,
    interval_level: float,
    resamples: int,
    seed: int,
) -> ReplayCell:
    """(PURA, ``AUTO-19B``) mide un par IS/OOS **ya partido** y devuelve la celda del replay.

    ``AUTO-19A`` partía y medía en el MISMO sitio (``_build_cell``); ``AUTO-19B`` necesita medir
    MUCHOS pares IS/OOS de la misma estrategia (walk-forward), así que el núcleo de medición se
    separa del split y se reutiliza tal cual: **una sola aritmética de la celda**, dos particiones
    (el split único del replay y los pliegues crecientes de la calibración). La partición del
    replay NO cambia: ``_build_cell`` conserva su split y delega aquí la medición.
    """
    confidence: AdaptiveConfidence = build_adaptive_confidence(is_rows)
    strategy = confidence.confidence_for(version)
    uncertainty: AdaptiveUncertainty = build_adaptive_uncertainty(
        is_rows,
        confidence=confidence,
        level=interval_level,
        resamples=resamples,
        min_episodes=min_episodes,
        seed=seed,
    )
    reading = uncertainty.uncertainty_for(version)

    is_expectancy = strategy.long_expectancy_r if strategy is not None else None
    is_shrunk = strategy.shrunk_expectancy_r if strategy is not None else None
    is_effective = strategy.effective_n if strategy is not None else 0
    is_band = strategy.confidence if strategy is not None else "UNKNOWN"
    is_coverage = strategy.coverage if strategy is not None else "UNKNOWN"
    interval = reading.interval if reading is not None else None
    edge = reading.edge_confidence if reading is not None else ADAPTIVE_EDGE_UNKNOWN

    oos_values = [
        float(value) for value in (measured_r(row) for row in oos_rows) if value is not None
    ]
    oos_expectancy = _round4(mean(oos_values)) if oos_values else None
    if len(oos_values) > 1:
        oos_dispersion: float | None = _round4(pstdev(oos_values))
    elif oos_values:
        oos_dispersion = 0.0
    else:
        oos_dispersion = None
    oos_regime = _majority_regime(oos_rows)

    raw_error = (
        _round4(abs(is_expectancy - oos_expectancy))
        if is_expectancy is not None and oos_expectancy is not None
        else None
    )
    shrunk_error = (
        _round4(abs(is_shrunk - oos_expectancy))
        if is_shrunk is not None and oos_expectancy is not None
        else None
    )
    actual_positive = _signed_positive(oos_expectancy)
    raw_sign_ok = (
        None
        if actual_positive is None or is_expectancy is None
        else _signed_positive(is_expectancy) == actual_positive
    )
    shrunk_sign_ok = (
        None
        if actual_positive is None or is_shrunk is None
        else _signed_positive(is_shrunk) == actual_positive
    )
    if actual_positive is None or edge not in (ADAPTIVE_EDGE_HIGH, ADAPTIVE_EDGE_LOW):
        edge_sign_ok: bool | None = None
    else:
        edge_sign_ok = (edge == ADAPTIVE_EDGE_HIGH) == actual_positive

    notes: list[str] = []
    if interval is not None and interval.lower is None:
        notes.append("is_interval_insufficient")
    return ReplayCell(
        strategy_version=version,
        is_measured_n=strategy.measured_n if strategy is not None else 0,
        is_episodes=strategy.episodes if strategy is not None else 0,
        is_effective_n=is_effective,
        is_expectancy_r=is_expectancy,
        is_shrunk_expectancy_r=is_shrunk,
        is_interval_lower=interval.lower if interval is not None else None,
        is_interval_upper=interval.upper if interval is not None else None,
        is_confidence=is_band,
        is_coverage=is_coverage,
        is_edge_confidence=edge,
        oos_measured_n=len(oos_values),
        oos_expectancy_r=oos_expectancy,
        oos_dispersion_r=oos_dispersion,
        oos_regime=oos_regime,
        regime_coverage=_regime_coverage(strategy, oos_regime),
        raw_error=raw_error,
        shrunk_error=shrunk_error,
        raw_sign_ok=raw_sign_ok,
        shrunk_sign_ok=shrunk_sign_ok,
        edge_sign_ok=edge_sign_ok,
        notes=tuple(notes),
    )


def _question_shrinkage(cells: Sequence[ReplayCell], min_cells: int) -> ReplayQuestion:
    """Q1 — ¿el shrinkage predice mejor el OOS que el crudo?"""
    pairs = [(c.raw_error, c.shrunk_error) for c in cells if c.raw_error is not None and c.shrunk_error is not None]
    metrics = {
        "meanRawError": None,
        "meanShrunkError": None,
        "rawSignAccuracy": None,
        "shrunkSignAccuracy": None,
    }
    if len(pairs) < max(1, min_cells):
        return _inconclusive(
            REPLAY_QUESTION_SHRINKAGE, metrics=metrics, sample=len(pairs)
        )
    raw_mean = _group_mean([raw for raw, _ in pairs])
    shrunk_mean = _group_mean([shrunk for _, shrunk in pairs])
    raw_signs = [c.raw_sign_ok for c in cells if c.raw_sign_ok is not None]
    shrunk_signs = [c.shrunk_sign_ok for c in cells if c.shrunk_sign_ok is not None]
    metrics = {
        "meanRawError": _round4(raw_mean),
        "meanShrunkError": _round4(shrunk_mean),
        "rawSignAccuracy": _round4(sum(1 for ok in raw_signs if ok) / len(raw_signs))
        if raw_signs
        else None,
        "shrunkSignAccuracy": _round4(sum(1 for ok in shrunk_signs if ok) / len(shrunk_signs))
        if shrunk_signs
        else None,
    }
    return ReplayQuestion(
        question=REPLAY_QUESTION_SHRINKAGE,
        verdict=_compare(shrunk_mean, raw_mean),
        sample=len(pairs),
        metrics=metrics,
    )


def _question_effective_n(cells: Sequence[ReplayCell], min_cells: int) -> ReplayQuestion:
    """Q2 — ¿las celdas con ``effective_N`` alto tienen menos error OOS?"""
    usable = [(c.is_effective_n, c.raw_error) for c in cells if c.raw_error is not None]
    metrics: dict[str, Any] = {
        "meanErrorHighEffectiveN": None,
        "meanErrorLowEffectiveN": None,
        "medianEffectiveN": None,
    }
    if len(usable) < max(2, min_cells * 2 - 1):
        return _inconclusive(REPLAY_QUESTION_EFFECTIVE_N, metrics=metrics, sample=len(usable))
    ordered = sorted(value for value, _ in usable)
    median = ordered[len(ordered) // 2]
    high = [error for value, error in usable if value > median]
    low = [error for value, error in usable if value <= median]
    metrics["medianEffectiveN"] = median
    if len(high) < min_cells or len(low) < min_cells:
        return _inconclusive(
            REPLAY_QUESTION_EFFECTIVE_N, metrics=metrics, sample=len(usable)
        )
    high_mean = _group_mean(high)
    low_mean = _group_mean(low)
    metrics["meanErrorHighEffectiveN"] = _round4(high_mean)
    metrics["meanErrorLowEffectiveN"] = _round4(low_mean)
    return ReplayQuestion(
        question=REPLAY_QUESTION_EFFECTIVE_N,
        # Más evidencia efectiva ⇒ menos error esperado: el error ALTO debe ser <= el BAJO.
        verdict=_compare(high_mean, low_mean),
        sample=len(high) + len(low),
        metrics=metrics,
    )


def _question_confidence(cells: Sequence[ReplayCell], min_cells: int) -> ReplayQuestion:
    """Q3 — ¿la banda ``HIGH`` produce OOS más estables (menos dispersión) que ``LOW``?"""
    usable = [
        (c.is_confidence, c.oos_dispersion_r)
        for c in cells
        if c.oos_dispersion_r is not None and c.oos_measured_n >= 2
    ]
    metrics: dict[str, Any] = {
        "meanDispersionHigh": None,
        "meanDispersionLow": None,
        "cellsHigh": 0,
        "cellsLow": 0,
    }
    high = [disp for band, disp in usable if band == "HIGH"]
    low = [disp for band, disp in usable if band == "LOW"]
    metrics["cellsHigh"] = len(high)
    metrics["cellsLow"] = len(low)
    if len(high) < min_cells or len(low) < min_cells:
        return _inconclusive(
            REPLAY_QUESTION_CONFIDENCE, metrics=metrics, sample=len(high) + len(low)
        )
    high_mean = _group_mean(high)
    low_mean = _group_mean(low)
    metrics["meanDispersionHigh"] = _round4(high_mean)
    metrics["meanDispersionLow"] = _round4(low_mean)
    return ReplayQuestion(
        question=REPLAY_QUESTION_CONFIDENCE,
        verdict=_compare(high_mean, low_mean),
        sample=len(high) + len(low),
        metrics=metrics,
    )


def _question_coverage(cells: Sequence[ReplayCell], min_cells: int) -> ReplayQuestion:
    """Q4 — ¿la cobertura ``HIGH`` del régimen que dominó el OOS reduce el error?"""
    usable = [(c.regime_coverage, c.raw_error) for c in cells if c.raw_error is not None]
    metrics: dict[str, Any] = {
        "meanErrorCovered": None,
        "meanErrorUncovered": None,
        "cellsCovered": 0,
        "cellsUncovered": 0,
    }
    covered = [error for coverage, error in usable if coverage == ADAPTIVE_COVERAGE_HIGH]
    uncovered = [error for coverage, error in usable if coverage != ADAPTIVE_COVERAGE_HIGH]
    metrics["cellsCovered"] = len(covered)
    metrics["cellsUncovered"] = len(uncovered)
    if len(covered) < min_cells or len(uncovered) < min_cells:
        return _inconclusive(
            REPLAY_QUESTION_COVERAGE, metrics=metrics, sample=len(covered) + len(uncovered)
        )
    covered_mean = _group_mean(covered)
    uncovered_mean = _group_mean(uncovered)
    metrics["meanErrorCovered"] = _round4(covered_mean)
    metrics["meanErrorUncovered"] = _round4(uncovered_mean)
    return ReplayQuestion(
        question=REPLAY_QUESTION_COVERAGE,
        verdict=_compare(covered_mean, uncovered_mean),
        sample=len(covered) + len(uncovered),
        metrics=metrics,
    )


def _questions(cells: Sequence[ReplayCell], min_cells: int) -> tuple[ReplayQuestion, ...]:
    return (
        _question_shrinkage(cells, min_cells),
        _question_effective_n(cells, min_cells),
        _question_confidence(cells, min_cells),
        _question_coverage(cells, min_cells),
    )


def build_replay_report(
    cycles: Iterable[Any] | None = None,
    *,
    oos_pct: float = REPLAY_OOS_PCT_DEFAULT,
    interval_level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
    min_is: int = REPLAY_MIN_IS_MEASURED_DEFAULT,
    min_oos: int = REPLAY_MIN_OOS_MEASURED_DEFAULT,
    min_episodes: int = REPLAY_MIN_EPISODES_DEFAULT,
    min_cells: int = REPLAY_MIN_CELLS_DEFAULT,
) -> ReplayReport:
    """(PURA) la batería OOS completa sobre los ciclos dados (mismo material que el informe).

    Sin ciclos devuelve un informe vacío DECLARADO: las cuatro preguntas quedan ``inconclusive`` con
    ``sample = 0``, que es la respuesta honesta a "¿predice mejor?" cuando no hay nada que medir.
    """
    rows = list(cycles or ())
    resolved_pct = min(max(float(oos_pct), REPLAY_OOS_PCT_MIN), REPLAY_OOS_PCT_MAX)
    resolved_min_is = max(1, int(min_is))
    resolved_min_oos = max(1, int(min_oos))
    resolved_min_cells = max(1, int(min_cells))

    if not rows:
        return ReplayReport(
            cells=(),
            questions=_questions((), resolved_min_cells),
            oos_pct=resolved_pct,
            interval_level=interval_level,
            seed=int(seed),
            notes=("no_cycles",),
        )

    ordered, undated = order_cycles_by_instant(rows)
    by_version: dict[str, list[Any]] = {}
    for row in ordered:
        version = str(cycle_field(row, "strategyVersion", "strategy_version") or "")
        if not version:
            continue
        if measured_r(row) is None:
            continue
        by_version.setdefault(version, []).append(row)

    notes: list[str] = []
    if undated:
        notes.append("undated_cycles")
    cells: list[ReplayCell] = []
    skipped: list[str] = []
    for version in sorted(by_version):
        cell = _build_cell(
            version,
            by_version[version],
            oos_pct=resolved_pct,
            min_is=resolved_min_is,
            min_oos=resolved_min_oos,
            min_episodes=max(1, int(min_episodes)),
            interval_level=interval_level,
            resamples=max(1, int(resamples)),
            seed=int(seed),
        )
        if cell is None:
            skipped.append(version)
            continue
        cells.append(cell)
    if skipped:
        notes.extend(f"skipped_strategy:{version}" for version in skipped)
    return ReplayReport(
        cells=tuple(cells),
        questions=_questions(cells, resolved_min_cells),
        oos_pct=resolved_pct,
        interval_level=interval_level,
        seed=int(seed),
        notes=tuple(notes),
    )
