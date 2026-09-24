"""AUTO-19B — CALIBRACIÓN del intervalo y WALK-FORWARD del AUTO (PURA y READ-ONLY).

``AUTO-19A`` construyó el instrumento que faltaba (el **intervalo de incertidumbre** por episodios y
la **confianza de EDGE**) y una batería que compara **una** partición IS/OOS. Lo que dejó declarado
como deuda es la pregunta que ahora importa: **¿está BIEN CALIBRADA esa incertidumbre?**

Este módulo la responde con dos piezas:

* **Walk-forward** (ventanas CRECIENTES): en vez de un solo split ``IS → OOS``, parte cada estrategia
  en ``n_folds+1`` segmentos cronológicos y mide ``n_folds`` pares: el pliegue ``i`` entrena con todo
  lo anterior y testea con el segmento inmediatamente posterior (``fold 1`` viejo → ``fold N``
  reciente). Una regla que solo funciona una vez no es una regla; repetir la partición lo delata.
* **Calibración**: sobre los pliegues se mide, con muestra declarada, si el intervalo del 90 % cubre
  de verdad los resultados OOS con la frecuencia prometida (``interval_coverage``), si el signo del
  EDGE acierta el signo realizado (``edge_sign_calibration``) y si la banda de MEDICIÓN ordena la
  estabilidad OOS (``confidence_calibration``). Las tres preguntas de ``AUTO-19A`` (shrinkage,
  ``effective_N`` y cobertura) se **reutilizan tal cual** sobre los pliegues: un solo productor de la
  comparación.

Disciplina de medición (la del repo, y aquí es el punto entero del módulo):

* **Lo que no se midió se declara.** Sin ciclos no hay informe (``no_cycles``); sin pliegues
  suficientes la estrategia no entra (``skipped_strategy``); con menos pliegues que los pedidos el
  hueco se nombra (``insufficient_folds``). Nunca se fabrica un veredicto.
* **La cobertura se MIDE, no se afirma.** ``interval_coverage`` compara la fracción observada contra
  el nivel declarado con una tolerancia declarada; sin intervalos en la muestra la pregunta queda
  ``inconclusive`` (una celda sin intervalo no cuenta como cubierta NI como descubierta).
* **Ninguna lectura mueve el reparto.** Ni el intervalo ni la calibración son un permiso: el sello
  del reparto sigue en ``auto18-v1`` y el walk-forward es **evidencia publicada**, nunca un sizing.

**Read-only por contrato**: no toca el plan, el journal durable, el gobernador, ni la base de datos.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_CONFIDENCE_HIGH,
    ADAPTIVE_CONFIDENCE_LOW,
    ADAPTIVE_CONFIDENCE_MEDIUM,
    cycle_field,
    measured_r,
    order_cycles_by_instant,
)
from bolsa_analytics.cognitive.auto_adaptive_replay import (
    REPLAY_MIN_CELLS_DEFAULT,
    REPLAY_MIN_IS_MEASURED_DEFAULT,
    REPLAY_MIN_OOS_MEASURED_DEFAULT,
    REPLAY_VERDICT_INCONCLUSIVE,
    REPLAY_VERDICT_NOT_SUPPORTED,
    REPLAY_VERDICT_SUPPORTED,
    ReplayCell,
    ReplayQuestion,
    _compare,
    _question_coverage,
    _question_effective_n,
    _question_shrinkage,
    measure_is_oos_row,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (
    ADAPTIVE_EDGE_HIGH,
    ADAPTIVE_EDGE_LOW,
    ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    ADAPTIVE_INTERVAL_LEVEL_MAX,
    ADAPTIVE_INTERVAL_LEVEL_MIN,
    ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
    ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    ADAPTIVE_INTERVAL_SEED_DEFAULT,
)

__all__ = [
    "CALIBRATION_COVERAGE_TOLERANCE_DEFAULT",
    "CALIBRATION_EDGE_SIGN_FLOOR_DEFAULT",
    "CALIBRATION_FOLDS_DEFAULT",
    "CALIBRATION_FOLDS_MAX",
    "CALIBRATION_FOLDS_MIN",
    "CALIBRATION_METHOD",
    "CALIBRATION_QUESTION_CONFIDENCE",
    "CALIBRATION_QUESTION_COVERAGE",
    "CALIBRATION_QUESTION_EDGE_SIGN",
    "CALIBRATION_QUESTION_EFFECTIVE_N",
    "CALIBRATION_QUESTION_INTERVAL_COVERAGE",
    "CALIBRATION_QUESTION_SHRINKAGE",
    "CalibrationFold",
    "CalibrationQuestion",
    "CalibrationReport",
    "build_calibration_report",
    "resolve_calibration_folds",
    "split_walk_forward_folds",
]

#: Método declarado de la lectura. Ampliarla (p. ej. validar ``P(R > 0)``) obliga a subir este
#: sello: dos informes con el mismo aspecto no pueden venir de instrumentos distintos.
CALIBRATION_METHOD = "walk_forward_calibration_v1"

#: Pliegues del walk-forward: por defecto 3, acotado a ``[2, 5]`` (el mismo rango que el walk-forward
#: de barras de ``optimize``). Con menos de 2 no hay walk-forward —hay un split—, y por encima de 5
#: cada tramo sería tan corto que mediría ruido.
CALIBRATION_FOLDS_DEFAULT = 3
CALIBRATION_FOLDS_MIN = 2
CALIBRATION_FOLDS_MAX = 5

#: Tolerancia declarada de la cobertura: la fracción observada no puede quedar más de esto por
#: debajo del nivel prometido. Con ``level = 0.90`` y ``0.10`` el listón es ``0.80``: un intervalo
#: del 90 % que solo cubre 2 de cada 3 resultados OOS se declara ``not_supported``.
CALIBRATION_COVERAGE_TOLERANCE_DEFAULT = 0.10

#: Acierto mínimo del signo del EDGE para declararlo calibrado. ``0.5`` es el azar: por debajo, el
#: instrumento afirmaría lo contrario de lo que midió.
CALIBRATION_EDGE_SIGN_FLOOR_DEFAULT = 0.5

CALIBRATION_QUESTION_INTERVAL_COVERAGE = "interval_coverage"
CALIBRATION_QUESTION_EDGE_SIGN = "edge_sign_calibration"
CALIBRATION_QUESTION_CONFIDENCE = "confidence_calibration"
CALIBRATION_QUESTION_SHRINKAGE = "shrinkage_calibration"
CALIBRATION_QUESTION_EFFECTIVE_N = "effective_n_calibration"
CALIBRATION_QUESTION_COVERAGE = "coverage_calibration"

_CALIBRATION_QUESTIONS: tuple[str, ...] = (
    CALIBRATION_QUESTION_INTERVAL_COVERAGE,
    CALIBRATION_QUESTION_EDGE_SIGN,
    CALIBRATION_QUESTION_CONFIDENCE,
    CALIBRATION_QUESTION_SHRINKAGE,
    CALIBRATION_QUESTION_EFFECTIVE_N,
    CALIBRATION_QUESTION_COVERAGE,
)

#: Tolerancia declarada para considerar dos medias "iguales": por debajo, la diferencia es redondeo
#: y la pregunta queda ``inconclusive`` (no se elige un ganador por un epsilon).
_EPSILON = 1e-9


def _round4(value: float | None) -> float | None:
    if value is None:
        return None
    rounded = round(float(value), 4)
    return 0.0 if rounded == 0 else rounded


def _positive(value: float | None) -> bool | None:
    """¿El número es positivo? ``None`` cuando no hay número (no se inventa un signo)."""
    if value is None:
        return None
    return value > 0.0


def resolve_calibration_folds(n_folds: int | None) -> int:
    """(PURA) pliegues declarados del walk-forward, acotados a ``[2, 5]``.

    ``None`` toma el defecto. **Nunca** se devuelve 1: con un solo pliegue no hay walk-forward, hay
    un split, y llamarlo walk-forward sería afirmar una repetición que no se midió.
    """
    value = CALIBRATION_FOLDS_DEFAULT if n_folds is None else int(n_folds)
    return max(CALIBRATION_FOLDS_MIN, min(CALIBRATION_FOLDS_MAX, value))


def split_walk_forward_folds(
    rows: Sequence[Any],
    *,
    n_folds: int = CALIBRATION_FOLDS_DEFAULT,
    min_is: int = REPLAY_MIN_IS_MEASURED_DEFAULT,
    min_oos: int = REPLAY_MIN_OOS_MEASURED_DEFAULT,
) -> tuple[tuple[tuple[Any, ...], tuple[Any, ...]], ...]:
    """(PURA) parte filas YA ORDENADAS por instante en pliegues IS/OOS CRECIENTES.

    Divide la serie en ``n_folds + 1`` segmentos de igual tamaño; el pliegue ``i`` (1-based) entrena
    con los ``i`` primeros segmentos (**expanding**) y testea con el segmento ``i + 1`` (el último
    absorbe el resto). Es la misma forma que el walk-forward de barras de ``optimize``, aplicada a
    ciclos cerrados.

    Los pliegues que no alcanzan los mínimos declarados por tramo **no se forman** (el walk-forward
    no fuerza una partición que mediría ruido): se devuelven solo los medibles. Sin material no hay
    pliegues. El IS de un pliegue **jamás** contiene su tramo OOS.
    """
    ordered = tuple(rows)
    total = len(ordered)
    resolved = resolve_calibration_folds(n_folds)
    resolved_min_is = max(1, int(min_is))
    resolved_min_oos = max(1, int(min_oos))
    if total <= 0:
        return ()
    segments = resolved + 1
    segment_size = total // segments
    if segment_size <= 0:
        return ()

    folds: list[tuple[tuple[Any, ...], tuple[Any, ...]]] = []
    for index in range(resolved):
        train_end = segment_size * (index + 1)
        test_end = total if index == resolved - 1 else segment_size * (index + 2)
        train = ordered[:train_end]
        test = ordered[train_end:test_end]
        if len(train) < resolved_min_is or len(test) < resolved_min_oos:
            continue
        folds.append((train, test))
    return tuple(folds)


@dataclass(frozen=True, slots=True)
class CalibrationFold:
    """Un pliegue del walk-forward: su índice (1-based) y la celda IS/OOS que lo mide."""

    index: int
    cell: ReplayCell

    def as_dict(self) -> dict[str, Any]:
        return {"index": self.index, "cell": self.cell.as_dict()}


@dataclass(frozen=True, slots=True)
class CalibrationQuestion:
    """Una pregunta de calibración, con su veredicto declarado y los números que lo sostienen."""

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
class CalibrationReport:
    """El informe de calibración: pliegues medidos + las preguntas + los agregados del walk-forward."""

    folds: tuple[CalibrationFold, ...]
    questions: tuple[CalibrationQuestion, ...]
    aggregate: dict[str, Any]
    method: str = CALIBRATION_METHOD
    folds_requested: int = CALIBRATION_FOLDS_DEFAULT
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT
    notes: tuple[str, ...] = ()

    @property
    def cells(self) -> tuple[ReplayCell, ...]:
        """Las celdas de todos los pliegues, en orden. Se DERIVAN de ``folds`` (un solo productor)."""
        return tuple(fold.cell for fold in self.folds)

    def question(self, key: str) -> CalibrationQuestion | None:
        for row in self.questions:
            if row.question == key:
                return row
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "foldsRequested": self.folds_requested,
            "level": self.level,
            "seed": self.seed,
            "folds": [fold.as_dict() for fold in self.folds],
            "cells": [cell.as_dict() for cell in self.cells],
            "questions": [row.as_dict() for row in self.questions],
            "aggregate": dict(self.aggregate),
            "notes": list(self.notes),
        }


def _inconclusive(
    question: str, *, metrics: dict[str, Any] | None = None, sample: int = 0
) -> CalibrationQuestion:
    return CalibrationQuestion(
        question=question,
        verdict=REPLAY_VERDICT_INCONCLUSIVE,
        sample=sample,
        metrics=metrics or {},
    )


def _as_calibration(question: ReplayQuestion, key: str) -> CalibrationQuestion:
    """Reetiqueta una pregunta de ``AUTO-19A`` como pregunta de calibración (mismo veredicto)."""
    return CalibrationQuestion(
        question=key,
        verdict=question.verdict,
        sample=question.sample,
        metrics=dict(question.metrics),
        notes=question.notes,
    )


def _question_interval_coverage(
    cells: Sequence[ReplayCell],
    *,
    min_cells: int,
    level: float,
    tolerance: float,
) -> CalibrationQuestion:
    """(PURA) ¿el intervalo del ``level`` cubre el OOS con la frecuencia prometida?

    Solo entran celdas que declaran intervalo **y** resultado OOS: sin intervalo no hay nada que
    cubrir (no cuenta como cubierta ni como descubierta) y sin OOS no hay resultado que encuadrar.
    """
    usable = [
        cell
        for cell in cells
        if cell.is_interval_lower is not None
        and cell.is_interval_upper is not None
        and cell.oos_expectancy_r is not None
    ]
    widths = [
        float(cell.is_interval_upper) - float(cell.is_interval_lower) for cell in usable
    ]
    covered = [
        cell
        for cell in usable
        if float(cell.is_interval_lower)
        <= float(cell.oos_expectancy_r)
        <= float(cell.is_interval_upper)
    ]
    total = len(usable)
    metrics: dict[str, Any] = {
        "coverageRate": _round4(len(covered) / total) if total else None,
        "expectedCoverage": _round4(min(max(level, 0.0), 1.0)),
        "foldCountWithInterval": total,
        "meanIntervalWidth": _round4(mean(widths)) if widths else None,
        "covered": len(covered),
        "total": total,
    }
    if total < max(1, int(min_cells)):
        return _inconclusive(CALIBRATION_QUESTION_INTERVAL_COVERAGE, metrics=metrics, sample=total)
    rate = len(covered) / total
    verdict = (
        REPLAY_VERDICT_SUPPORTED
        if rate >= level - tolerance
        else REPLAY_VERDICT_NOT_SUPPORTED
    )
    return CalibrationQuestion(
        question=CALIBRATION_QUESTION_INTERVAL_COVERAGE,
        verdict=verdict,
        sample=total,
        metrics=metrics,
    )


def _share_positive(values: Sequence[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return _round4(sum(1 for value in present if value > 0.0) / len(present))


def _question_edge_sign(
    cells: Sequence[ReplayCell],
    *,
    min_cells: int,
    floor: float,
) -> CalibrationQuestion:
    """(PURA) ¿el signo del EDGE (``HIGH``/``LOW``) acierta el signo realizado del OOS?

    ``MEDIUM`` y ``UNKNOWN`` quedan FUERA: no afirman un signo (``MEDIUM`` cruza cero, ``UNKNOWN``
    es no-medición), así que no se les puede pedir que acierten ninguno.
    """
    high = [cell for cell in cells if cell.is_edge_confidence == ADAPTIVE_EDGE_HIGH]
    low = [cell for cell in cells if cell.is_edge_confidence == ADAPTIVE_EDGE_LOW]
    usable = [cell for cell in cells if cell.edge_sign_ok is not None]
    sample = len(usable)
    accuracy = (
        _round4(sum(1 for cell in usable if cell.edge_sign_ok) / sample) if sample else None
    )
    metrics: dict[str, Any] = {
        "edgeSignAccuracy": accuracy,
        "cellsHigh": len(high),
        "cellsLow": len(low),
        "positiveOosShareHigh": _share_positive([cell.oos_expectancy_r for cell in high]),
        "positiveOosShareLow": _share_positive([cell.oos_expectancy_r for cell in low]),
    }
    if sample < max(1, int(min_cells)):
        return _inconclusive(CALIBRATION_QUESTION_EDGE_SIGN, metrics=metrics, sample=sample)
    verdict = (
        REPLAY_VERDICT_SUPPORTED if accuracy is not None and accuracy >= floor
        else REPLAY_VERDICT_NOT_SUPPORTED
    )
    return CalibrationQuestion(
        question=CALIBRATION_QUESTION_EDGE_SIGN,
        verdict=verdict,
        sample=sample,
        metrics=metrics,
    )


def _band_summary(cells: Sequence[ReplayCell], band: str) -> dict[str, Any]:
    rows = [cell for cell in cells if cell.is_confidence == band]
    oos = [cell.oos_expectancy_r for cell in rows if cell.oos_expectancy_r is not None]
    dispersions = [
        float(cell.oos_dispersion_r)
        for cell in rows
        if cell.oos_dispersion_r is not None and cell.oos_measured_n >= 2
    ]
    return {
        "n": len(rows),
        "meanOosExpectancyR": _round4(mean(oos)) if oos else None,
        "meanOosDispersionR": _round4(mean(dispersions)) if dispersions else None,
        "positiveShare": _share_positive(oos),
    }


def _question_confidence_band(
    cells: Sequence[ReplayCell], *, min_cells: int
) -> CalibrationQuestion:
    """(PURA) ¿la banda de MEDICIÓN ordena la estabilidad OOS? (``HIGH`` menos disperso que ``LOW``)

    Misma comparación que la tercera pregunta del replay, pero agregada sobre TODOS los pliegues y
    con el resumen por banda publicado: no basta decir "HIGH <= LOW"; se enseñan los números de cada
    banda para que un ``HIGH`` apenas mejor que un ``LOW`` no se lea como una separación fuerte.
    """
    bands = {
        band: _band_summary(cells, band)
        for band in (ADAPTIVE_CONFIDENCE_HIGH, ADAPTIVE_CONFIDENCE_MEDIUM, ADAPTIVE_CONFIDENCE_LOW)
    }
    high = [
        float(cell.oos_dispersion_r)
        for cell in cells
        if cell.is_confidence == ADAPTIVE_CONFIDENCE_HIGH
        and cell.oos_dispersion_r is not None
        and cell.oos_measured_n >= 2
    ]
    low = [
        float(cell.oos_dispersion_r)
        for cell in cells
        if cell.is_confidence == ADAPTIVE_CONFIDENCE_LOW
        and cell.oos_dispersion_r is not None
        and cell.oos_measured_n >= 2
    ]
    metrics: dict[str, Any] = {
        "bands": bands,
        "cellsHigh": len(high),
        "cellsLow": len(low),
        "meanDispersionHigh": _round4(mean(high)) if high else None,
        "meanDispersionLow": _round4(mean(low)) if low else None,
    }
    if len(high) < max(1, int(min_cells)) or len(low) < max(1, int(min_cells)):
        return _inconclusive(
            CALIBRATION_QUESTION_CONFIDENCE, metrics=metrics, sample=len(high) + len(low)
        )
    return CalibrationQuestion(
        question=CALIBRATION_QUESTION_CONFIDENCE,
        verdict=_compare(mean(high), mean(low)),
        sample=len(high) + len(low),
        metrics=metrics,
    )


def _calibration_questions(
    cells: Sequence[ReplayCell],
    *,
    min_cells: int,
    level: float,
    tolerance: float,
    edge_sign_floor: float,
) -> tuple[CalibrationQuestion, ...]:
    return (
        _question_interval_coverage(
            cells, min_cells=min_cells, level=level, tolerance=tolerance
        ),
        _question_edge_sign(cells, min_cells=min_cells, floor=edge_sign_floor),
        _question_confidence_band(cells, min_cells=min_cells),
        _as_calibration(
            _question_shrinkage(cells, min_cells), CALIBRATION_QUESTION_SHRINKAGE
        ),
        _as_calibration(
            _question_effective_n(cells, min_cells), CALIBRATION_QUESTION_EFFECTIVE_N
        ),
        _as_calibration(_question_coverage(cells, min_cells), CALIBRATION_QUESTION_COVERAGE),
    )


def _aggregate(folds: Sequence[CalibrationFold]) -> dict[str, Any]:
    """(PURA) agregados del walk-forward en R, espejo de ``aggregate_walk_forward_metrics``.

    ``walkForwardEfficiency`` es la media OOS sobre la media IS cuando la IS es positiva; sin IS
    positiva no hay cociente honesto (``None``, no un ``0`` que diría "no rindió").
    """
    oos = [
        float(fold.cell.oos_expectancy_r)
        for fold in folds
        if fold.cell.oos_expectancy_r is not None
    ]
    is_values = [
        float(fold.cell.is_expectancy_r)
        for fold in folds
        if fold.cell.is_expectancy_r is not None
    ]
    if not oos:
        return {
            "foldCount": len(folds),
            "meanIsExpectancyR": _round4(mean(is_values)) if is_values else None,
            "meanOosExpectancyR": None,
            "stdOosExpectancyR": None,
            "positiveOosFoldShare": None,
            "oosCv": None,
            "walkForwardEfficiency": None,
        }
    mean_oos = float(mean(oos))
    std_oos = float(pstdev(oos)) if len(oos) > 1 else 0.0
    mean_is = float(mean(is_values)) if is_values else None
    return {
        "foldCount": len(folds),
        "meanIsExpectancyR": _round4(mean_is),
        "meanOosExpectancyR": _round4(mean_oos),
        "stdOosExpectancyR": _round4(std_oos),
        "positiveOosFoldShare": _round4(
            sum(1 for value in oos if value >= 0.0) / len(oos)
        ),
        "oosCv": (
            _round4(std_oos / abs(mean_oos)) if abs(mean_oos) > _EPSILON else None
        ),
        "walkForwardEfficiency": (
            _round4(mean_oos / mean_is)
            if mean_is is not None and mean_is > _EPSILON
            else None
        ),
    }


def build_calibration_report(
    cycles: Iterable[Any] | None = None,
    *,
    folds: int = CALIBRATION_FOLDS_DEFAULT,
    min_is: int = REPLAY_MIN_IS_MEASURED_DEFAULT,
    min_oos: int = REPLAY_MIN_OOS_MEASURED_DEFAULT,
    min_episodes: int = ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
    min_cells: int = REPLAY_MIN_CELLS_DEFAULT,
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    tolerance: float = CALIBRATION_COVERAGE_TOLERANCE_DEFAULT,
    edge_sign_floor: float = CALIBRATION_EDGE_SIGN_FLOOR_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
) -> CalibrationReport:
    """(PURA) walk-forward + calibración sobre los ciclos dados (mismo material que el informe).

    Sin ciclos devuelve un informe vacío DECLARADO: las seis preguntas quedan ``inconclusive`` con
    ``sample = 0``, que es la respuesta honesta a "¿está calibrada mi incertidumbre?" cuando no hay
    nada que medir. Con material, cada estrategia se parte en pliegues crecientes y se mide con la
    MISMA aritmética de celda que ``AUTO-19A`` (``measure_is_oos_row``).
    """
    rows = list(cycles or ())
    resolved_folds = resolve_calibration_folds(folds)
    resolved_min_is = max(1, int(min_is))
    resolved_min_oos = max(1, int(min_oos))
    resolved_min_episodes = max(1, int(min_episodes))
    resolved_min_cells = max(1, int(min_cells))
    resolved_level = min(
        max(float(level), ADAPTIVE_INTERVAL_LEVEL_MIN), ADAPTIVE_INTERVAL_LEVEL_MAX
    )

    if not rows:
        return CalibrationReport(
            folds=(),
            questions=_calibration_questions(
                (),
                min_cells=resolved_min_cells,
                level=resolved_level,
                tolerance=tolerance,
                edge_sign_floor=edge_sign_floor,
            ),
            aggregate=_aggregate(()),
            folds_requested=resolved_folds,
            level=resolved_level,
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
    measured_folds: list[CalibrationFold] = []
    skipped: list[str] = []
    for version in sorted(by_version):
        split = split_walk_forward_folds(
            by_version[version],
            n_folds=resolved_folds,
            min_is=resolved_min_is,
            min_oos=resolved_min_oos,
        )
        if not split:
            skipped.append(version)
            continue
        for index, (train, test) in enumerate(split, start=1):
            cell = measure_is_oos_row(
                version,
                train,
                test,
                min_episodes=resolved_min_episodes,
                interval_level=resolved_level,
                resamples=max(1, int(resamples)),
                seed=int(seed),
            )
            measured_folds.append(CalibrationFold(index=index, cell=cell))
        if len(split) < resolved_folds:
            notes.append(f"insufficient_folds:{version}")
    if skipped:
        notes.extend(f"skipped_strategy:{version}" for version in skipped)

    folds_tuple = tuple(measured_folds)
    return CalibrationReport(
        folds=folds_tuple,
        questions=_calibration_questions(
            tuple(fold.cell for fold in folds_tuple),
            min_cells=resolved_min_cells,
            level=resolved_level,
            tolerance=tolerance,
            edge_sign_floor=edge_sign_floor,
        ),
        aggregate=_aggregate(folds_tuple),
        folds_requested=resolved_folds,
        level=resolved_level,
        seed=int(seed),
        notes=tuple(notes),
    )
