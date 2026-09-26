"""AUTO-23 — VALIDACIÓN de la evidencia sobre material real (P(R>0) vs N, régimen y correlación).

Qué resuelve: ``AUTO-22`` dejó un RUN reproducible que publica evidencia, pero **nadie la había
validado sobre datos reales**. Las deudas ``P3-2`` (¿la correlación por cubos introduce sincronía
artificial?) y ``P3-3`` (¿``P(R>0)`` se estabiliza con la muestra?) solo se pueden cerrar con el
primer dataset PAPER. Este módulo deja el andamiaje listo para ese momento: no decide, no elige el
``N`` que mejor suena y **no añade ninguna aritmética nueva**.

Qué NO hace:

* **No mide nada nuevo.** El barrido por tamaño muestral llama a ``build_evidence_run_bundle``
  (``AUTO-22``) y **copia** sus cifras; la estabilidad de régimen llama a
  ``build_adaptive_uncertainty`` (``AUTO-19A``) y la validación de correlación a
  ``build_strategy_correlation_report`` (``AUTO-21``). Si aquí naciera una segunda ``P(R>0)``,
  tendríamos exactamente la divergencia que toda la cadena existe para impedir.
* **No decide.** La banda de edge y la correlación se publican como lectura; no mueven sizing, plan,
  reserva ni rotación.
* **No inventa ceros.** Un tamaño muestral mayor que el material medido es ``NO MEDIDO``, nunca una
  fila fabricada; una correlación sin cubos es un hueco declarado, nunca ``0.0``.

Puro y determinista: sin I/O, sin reloj, sin estado.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_calibration import (
    CALIBRATION_FOLDS_DEFAULT,
    CALIBRATION_QUESTION_EFFECTIVE_N,
    CALIBRATION_QUESTION_PROBABILITY,
)
from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    closed_instant,
    cycle_field,
    measured_r,
    order_cycles_by_instant,
)
from bolsa_analytics.cognitive.auto_adaptive_correlation import (
    CORRELATION_BUCKET_DAY,
    CORRELATION_BUCKET_MONTH,
    CORRELATION_BUCKET_WEEK,
    bucket_key,
    build_strategy_correlation_report,
    resolve_bucket,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (
    ADAPTIVE_EDGE_HIGH,
    ADAPTIVE_EDGE_LOW,
    ADAPTIVE_EDGE_MEDIUM,
    ADAPTIVE_EDGE_UNKNOWN,
    ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
    ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    ADAPTIVE_INTERVAL_SEED_DEFAULT,
    build_adaptive_uncertainty,
)
from bolsa_analytics.cognitive.auto_evidence_report import (
    MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
)
from bolsa_analytics.cognitive.auto_evidence_run import build_evidence_run_bundle

__all__ = [
    "CORRELATION_VALIDATION_BUCKETS",
    "CORRELATION_VALIDATION_SCHEMA",
    "EDGE_VERDICTS",
    "EDGE_VERDICT_INCONCLUSIVE",
    "EDGE_VERDICT_NOT_SUPPORTED",
    "EDGE_VERDICT_SUPPORTED",
    "EVIDENCE_VALIDATION_SCHEMA",
    "EvidenceValidationBlockedError",
    "REGIME_STABILITY_SCHEMA",
    "SAMPLE_SIZE_SWEEP_DEFAULT",
    "SAMPLE_SIZE_SWEEP_SCHEMA",
    "build_correlation_validation",
    "build_regime_stability",
    "build_sample_size_sweep",
    "build_validation_report",
]

#: Sello del informe de validación. Cambiar su forma obliga a subir este sello.
#: ``v2`` (v2.71): ``probabilityPositive`` pasa a ser la ``P(R>0)`` por CICLOS y se añade
#: ``edgePositiveProbability`` (la ``P(edge>0)`` del bootstrap) en las celdas.
EVIDENCE_VALIDATION_SCHEMA = "auto23_evidence_validation_v2"
SAMPLE_SIZE_SWEEP_SCHEMA = "auto23_sample_size_sweep_v2"
REGIME_STABILITY_SCHEMA = "auto23_regime_stability_v2"
CORRELATION_VALIDATION_SCHEMA = "auto23_correlation_validation_v1"

#: Tamaños del barrido ``P(R>0)`` vs muestra. No son umbrales ni una rejilla de selección: son los
#: puntos donde se OBSERVA si la lectura se estabiliza (auditoría ``v2.69``, punto 20).
SAMPLE_SIZE_SWEEP_DEFAULT: tuple[int, ...] = (16, 32, 64, 128)
#: Cubos de la validación de correlación (los mismos que soporta ``AUTO-21``).
CORRELATION_VALIDATION_BUCKETS: tuple[str, ...] = (
    CORRELATION_BUCKET_DAY,
    CORRELATION_BUCKET_WEEK,
    CORRELATION_BUCKET_MONTH,
)

#: Veredictos publicados (espejo de ``EDGE_VERDICTS`` del frontend y del render Python). La banda
#: de edge la declara el backend; aquí solo se traduce a una etiqueta legible, no se recalcula.
EDGE_VERDICT_SUPPORTED = "SUPPORTED"
EDGE_VERDICT_NOT_SUPPORTED = "NOT_SUPPORTED"
EDGE_VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
EDGE_VERDICTS: dict[str, str] = {
    ADAPTIVE_EDGE_HIGH: EDGE_VERDICT_SUPPORTED,
    ADAPTIVE_EDGE_MEDIUM: EDGE_VERDICT_INCONCLUSIVE,
    ADAPTIVE_EDGE_LOW: EDGE_VERDICT_NOT_SUPPORTED,
    ADAPTIVE_EDGE_UNKNOWN: EDGE_VERDICT_INCONCLUSIVE,
}


class EvidenceValidationBlockedError(RuntimeError):
    """La validación no tiene material medible: se DECLARA bloqueada en vez de publicar un informe.

    Un informe de validación sin ningún ciclo con R medible tendría el aspecto de una validación
    (barrido, régimen, correlación) sin haber medido nada. Quien llama lo traduce a BLOQUEADO
    (``exit 2``) y no escribe ningún fichero.
    """


def _report_of(bundle: Mapping[str, Any]) -> Mapping[str, Any]:
    """El informe de calibración que viaja DENTRO del bundle, sin reinterpretarlo."""
    artifact = bundle.get("artifact")
    if not isinstance(artifact, Mapping):
        return {}
    report = artifact.get("report")
    return report if isinstance(report, Mapping) else {}


def _aggregate_of(report: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = report.get("aggregate")
    return aggregate if isinstance(aggregate, Mapping) else {}


def _question_metrics(report: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Métricas de una pregunta del informe; sin pregunta o sin métricas ⇒ ``{}`` (no se inventa)."""
    for row in report.get("questions") or ():
        if isinstance(row, Mapping) and row.get("question") == key:
            metrics = row.get("metrics")
            return metrics if isinstance(metrics, Mapping) else {}
    return {}


def _declared_probability(report: Mapping[str, Any]) -> Any:
    """``P(R>0)`` DECLARADA por el instrumento, leída del informe (no recalculada)."""
    return _question_metrics(report, CALIBRATION_QUESTION_PROBABILITY).get(
        "meanDeclaredProbability"
    )


def _median_effective_n(report: Mapping[str, Any]) -> Any:
    """``effective_n`` mediano declarado por el instrumento, leído del informe."""
    return _question_metrics(report, CALIBRATION_QUESTION_EFFECTIVE_N).get(
        "medianEffectiveN"
    )


def _unmeasured_sweep_row(size: int) -> dict[str, Any]:
    """Fila ``NO MEDIDO``: el tamaño pedido supera el material medido. Nunca un cero de relleno."""
    return {
        "size": size,
        "measured": False,
        "probabilityPositive": None,
        "probabilityPositiveOos": None,
        "walkForwardEfficiency": None,
        "medianEffectiveN": None,
        "notes": ["insufficient_measured_cycles"],
    }


def _sweep_row_from_bundle(
    prefix: Sequence[Any],
    size: int,
    *,
    folds: int,
    seed: int,
    level: float,
    resamples: int,
) -> dict[str, Any]:
    """Compone el bundle AUTO-22 del prefijo y COPIA sus cifras (una sola aritmética)."""
    bundle = build_evidence_run_bundle(
        list(prefix),
        folds=folds,
        seed=seed,
        level=level,
        resamples=resamples,
    )
    report = _report_of(bundle)
    aggregate = _aggregate_of(report)
    return {
        "size": size,
        "measured": True,
        "probabilityPositive": _declared_probability(report),
        "probabilityPositiveOos": aggregate.get("probabilityPositiveOos"),
        "walkForwardEfficiency": aggregate.get("walkForwardEfficiency"),
        "medianEffectiveN": _median_effective_n(report),
        "notes": [],
    }


def _sweep_row(
    prefix: Sequence[Any],
    size: int,
    *,
    folds: int,
    seed: int,
    level: float,
    resamples: int,
) -> dict[str, Any]:
    return _sweep_row_from_bundle(
        prefix,
        size,
        folds=folds,
        seed=seed,
        level=level,
        resamples=resamples,
    )


def build_sample_size_sweep(
    cycles: Iterable[Any] | None = None,
    *,
    sizes: Sequence[int] = SAMPLE_SIZE_SWEEP_DEFAULT,
    folds: int = CALIBRATION_FOLDS_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
) -> dict[str, Any]:
    """(PURA) ``P(R>0)`` vs N sobre el PREFIJO CRONOLÓGICO de los ciclos con R medible.

    Para cada tamaño ``N`` se compone el bundle de ``AUTO-22`` sobre los ``N`` ciclos más antiguos y
    se copian ``P(R>0)``, ``P(R>0)`` OOS, ``WFE`` y ``effective_n``. **No** se elige un ``N``: se
    publica la serie para observar estabilidad. ``N`` mayor que el material medido ⇒ ``NO MEDIDO``.
    """
    rows = list(cycles or ())
    ordered, undated = order_cycles_by_instant(rows)
    measured = [row for row in ordered if measured_r(row) is not None]
    requested = sorted({int(size) for size in sizes if int(size) > 0})
    sweep_rows: list[dict[str, Any]] = []
    for size in requested:
        if size > len(measured):
            sweep_rows.append(_unmeasured_sweep_row(size))
            continue
        sweep_rows.append(
            _sweep_row(
                measured[:size],
                size,
                folds=folds,
                seed=seed,
                level=level,
                resamples=resamples,
            )
        )
    notes: list[str] = []
    if not measured:
        notes.append("no_measured_cycles")
    if undated:
        notes.append("undated_cycles_ordered_last")
    return {
        "schema": SAMPLE_SIZE_SWEEP_SCHEMA,
        "method": "chronological_prefix_sweep_v2",
        "requestedSizes": requested,
        "measuredCycles": len(measured),
        "undatedCycles": undated,
        "rows": sweep_rows,
        "notes": notes,
    }


def _verdict(edge_confidence: Any) -> str:
    """Traduce la banda de edge declarada a un veredicto legible (no recalcula la banda)."""
    key = str(edge_confidence or "").strip().upper()
    return EDGE_VERDICTS.get(key, EDGE_VERDICT_INCONCLUSIVE)


def _interval_cell(interval: Any, edge_confidence: Any) -> dict[str, Any]:
    """Lectura de una celda de incertidumbre, con la banda de edge ya declarada por el backend.

    ``probabilityPositive`` es la ``P(R>0)`` por CICLOS (``cycle_positive_share``); la ``P(edge>0)``
    del bootstrap viaja aparte como ``edgePositiveProbability``. No son intercambiables.
    """
    return {
        "measuredN": interval.measured_n,
        "episodes": interval.episodes,
        "effectiveN": interval.effective_n,
        "expectancyR": interval.point,
        "probabilityPositive": interval.cycle_positive_share,
        "edgePositiveProbability": interval.edge_positive_probability,
        "edgeConfidence": edge_confidence,
        "verdict": _verdict(edge_confidence),
    }


def _divergences(
    global_cell: Mapping[str, Any], by_regime: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Lectura (NO gate) de dónde el veredicto global y el del régimen no coinciden."""
    rows: list[dict[str, Any]] = []
    for regime in sorted(by_regime):
        regime_verdict = by_regime[regime].get("verdict")
        if regime_verdict != global_cell.get("verdict"):
            rows.append(
                {
                    "regime": regime,
                    "globalVerdict": global_cell.get("verdict"),
                    "regimeVerdict": regime_verdict,
                }
            )
    return rows


def build_regime_stability(
    cycles: Iterable[Any] | None = None,
    *,
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
    min_episodes: int = ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
) -> dict[str, Any]:
    """(PURA) veredicto GLOBAL vs veredicto POR RÉGIMEN de cada estrategia, como lectura.

    Reutiliza ``build_adaptive_uncertainty`` (``AUTO-19A``): la banda de edge global y la de cada
    celda ``strategyVersion × regime`` salen de la MISMA aritmética. Publica las divergencias
    (p. ej. global ``SUPPORTED`` y régimen actual ``NOT_SUPPORTED``) sin convertirlas en gate.
    """
    rows = list(cycles or ())
    uncertainty = build_adaptive_uncertainty(
        rows,
        level=level,
        resamples=resamples,
        seed=seed,
        min_episodes=min_episodes,
    )
    strategies: list[dict[str, Any]] = []
    regimes_present: set[str] = set()
    for strategy in uncertainty.by_strategy:
        global_cell = _interval_cell(strategy.interval, strategy.edge_confidence)
        by_regime: dict[str, dict[str, Any]] = {}
        for cell in strategy.by_regime:
            by_regime[cell.regime] = _interval_cell(cell.interval, cell.edge_confidence)
            regimes_present.add(cell.regime)
        strategies.append(
            {
                "strategyVersion": strategy.strategy_version,
                "global": global_cell,
                "byRegime": by_regime,
                "divergences": _divergences(global_cell, by_regime),
                "notes": list(strategy.notes),
            }
        )
    return {
        "schema": REGIME_STABILITY_SCHEMA,
        "method": uncertainty.method,
        "regimesPresent": sorted(regimes_present),
        "strategies": strategies,
        "notes": list(uncertainty.notes),
    }


def _bucket_counts(
    rows: Sequence[Any], bucket: str
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, Any]], int]:
    """Cuenta ciclos medidos por ``(versión, cubo)`` y resume la actividad de cada estrategia.

    Es un DIAGNÓSTICO de ``P3-2`` (frecuencia y exposición), no una segunda correlación: aquí no se
    calcula ningún coeficiente, solo cuántos ciclos caen en cada cubo.
    """
    resolved = resolve_bucket(bucket)
    counts: dict[str, dict[str, int]] = {}
    activity: dict[str, dict[str, Any]] = {}
    undated = 0
    for row in rows:
        version = str(cycle_field(row, "strategyVersion", "strategy_version") or "")
        if not version or measured_r(row) is None:
            continue
        instant = closed_instant(row)
        if instant is None:
            undated += 1
            continue
        key = bucket_key(instant, resolved)
        counts.setdefault(version, {})
        counts[version][key] = counts[version].get(key, 0) + 1
        entry = activity.setdefault(
            version, {"cycles": 0, "firstBucket": key, "lastBucket": key}
        )
        entry["cycles"] = int(entry["cycles"]) + 1
        if key < str(entry["firstBucket"]):
            entry["firstBucket"] = key
        if key > str(entry["lastBucket"]):
            entry["lastBucket"] = key
    return counts, activity, undated


def _single_cycle_share(counts: Mapping[str, int]) -> float | None:
    if not counts:
        return None
    singles = sum(1 for value in counts.values() if value == 1)
    return round(singles / len(counts), 4)


def _pair_diagnostics(
    pair: Any,
    counts: Mapping[str, Mapping[str, int]],
) -> dict[str, Any]:
    """Diagnóstico `P3-2` de un par: cuántos cubos compartidos se sostienen sobre 1 solo ciclo."""
    left_counts = counts.get(pair.left, {})
    right_counts = counts.get(pair.right, {})
    shared = sorted(set(left_counts) & set(right_counts))
    single = sum(
        1 for key in shared if left_counts.get(key) == 1 or right_counts.get(key) == 1
    )
    return {
        "left": pair.left,
        "right": pair.right,
        "sharedBuckets": len(shared),
        "sharedBucketsWithSingleCycle": single,
        "sharedSingleCycleShare": (
            round(single / len(shared), 4) if shared else None
        ),
    }


def _bucket_diagnostics(rows: Sequence[Any], bucket: str) -> dict[str, Any]:
    counts, activity, undated = _bucket_counts(rows, bucket)
    per_strategy = {
        version: {
            **activity[version],
            "activeBuckets": len(counts[version]),
            "singleCycleBucketShare": _single_cycle_share(counts[version]),
        }
        for version in sorted(counts)
    }
    return {
        "bucket": resolve_bucket(bucket),
        "strategies": per_strategy,
        "undatedCycles": undated,
    }


def build_correlation_validation(
    cycles: Iterable[Any] | None = None,
    *,
    buckets: Sequence[str] = CORRELATION_VALIDATION_BUCKETS,
) -> dict[str, Any]:
    """(PURA) la correlación por cubo, con los diagnósticos de ``P3-2`` declarados y SIN tocarla.

    Para cada cubo publica la matriz de ``AUTO-21`` (número o hueco) y, junto a ella, los
    diagnósticos que permiten juzgar si la frecuencia/exposición sesgan el número: ciclos y cubos
    activos por estrategia y fracción de cubos compartidos sostenidos por un solo ciclo.
    """
    rows = list(cycles or ())
    resolved_buckets = tuple(dict.fromkeys(resolve_bucket(entry) for entry in buckets))
    by_bucket: dict[str, Any] = {}
    for bucket in resolved_buckets:
        report = build_strategy_correlation_report(rows, bucket=bucket)
        counts, _activity, _undated = _bucket_counts(rows, bucket)
        by_bucket[bucket] = {
            "method": report.method,
            "bucket": report.bucket,
            "minBuckets": report.min_buckets,
            "strategies": list(report.strategies),
            "pairs": [
                {
                    "left": pair.left,
                    "right": pair.right,
                    "correlation": pair.correlation,
                    "sharedBuckets": pair.shared_buckets,
                    "notes": list(pair.notes),
                    "diagnostics": _pair_diagnostics(pair, counts),
                }
                for pair in report.pairs
            ],
            "notes": list(report.notes),
            "diagnostics": _bucket_diagnostics(rows, bucket),
        }
    return {
        "schema": CORRELATION_VALIDATION_SCHEMA,
        "buckets": by_bucket,
        "notes": [],
    }


def build_validation_report(
    cycles: Iterable[Any] | None = None,
    *,
    material: Mapping[str, Any] | None = None,
    material_origin: str = MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
    broker_venue: str | None = None,
    sizes: Sequence[int] = SAMPLE_SIZE_SWEEP_DEFAULT,
    buckets: Sequence[str] = CORRELATION_VALIDATION_BUCKETS,
    folds: int = CALIBRATION_FOLDS_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    min_episodes: int = ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
) -> dict[str, Any]:
    """(PURA) compone el informe de validación de ``AUTO-23``, o se declara BLOQUEADO.

    El defecto de procedencia es el **fixture sintético** (nunca PAPER real): un llamante que olvide
    declarar el material no hereda el sello de una corrida de mercado. Sin ciclos con R medible
    lanza ``EvidenceValidationBlockedError``.
    """
    rows = list(cycles or ())
    if not any(measured_r(row) is not None for row in rows):
        raise EvidenceValidationBlockedError(
            "sin ciclos con R medible: no se publica una validación vacía como si fuera una medición"
        )
    return {
        "schema": EVIDENCE_VALIDATION_SCHEMA,
        "materialOrigin": material_origin,
        "brokerVenue": broker_venue,
        "fingerprint": (material or {}).get("fingerprint"),
        "measuredCycles": sum(1 for row in rows if measured_r(row) is not None),
        "sweep": build_sample_size_sweep(
            rows,
            sizes=sizes,
            folds=folds,
            seed=seed,
            level=level,
            resamples=resamples,
        ),
        "regimeStability": build_regime_stability(
            rows,
            level=level,
            resamples=resamples,
            seed=seed,
            min_episodes=min_episodes,
        ),
        "correlationValidation": build_correlation_validation(rows, buckets=buckets),
    }
