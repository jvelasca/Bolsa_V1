"""AUTO-22 — RUN de evidencia PAPER end-to-end (composición PURA, un solo comando, un bundle).

Qué resuelve: ``AUTO-21`` dejó implementadas las tres lecturas —``P(R>0)``, correlación entre
estrategias por cubo temporal y evidencia del régimen actual— pero la corrida real seguía siendo una
**secuencia de pasos manuales**: exportar material, lanzar el walk-forward, recomponer el artefacto y
copiar números a mano. Este módulo compone, en UNA llamada pura, el paquete completo de evidencia
que ``scripts/auto_evidence_run.py`` guarda con su huella.

Regla dura, la razón de existir de la fase:

> **El run es reproducible o se DECLARA bloqueado.** Sin ciclos con R medible no se publica un
> bundle "vacío pero con aspecto de medición": se lanza ``EvidenceRunBlockedError``. Un artefacto sin
> muestra es ``NO MEDIDO``, nunca un cero ni sello de una corrida que no midió nada.

Qué NO hace:

* **No mide nada nuevo.** Llama a los productores ya auditados (``build_calibration_report`` de
  ``AUTO-19B``, ``build_strategy_correlation_report`` y ``build_current_regime_evidence`` de
  ``AUTO-21``, ``build_evidence_artifact``/``render_evidence_report`` de ``AUTO-20C``) y encadena sus
  salidas. No hay una segunda aritmética de ``P(R>0)`` ni una correlación paralela que pudiera
  divergir del informe.
* **No decide.** El reparto sigue congelado (``auto18-v1``): esta pieza publica evidencia, no sizing.
* **No miente sobre la procedencia.** ``material_origin`` lo declara quien llama (el lector real
  aplica ``MATERIAL_ORIGIN_PAPER_REAL``; el modo fixture, ``MATERIAL_ORIGIN_SYNTHETIC_FIXTURE``).

Puro y determinista: sin reloj, sin I/O, sin estado. El timestamp y los argumentos del run son cosa
del script que lo invoca, no de la composición.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_calibration import (
    CALIBRATION_FOLDS_DEFAULT,
    CALIBRATION_QUESTION_COVERAGE,
    CALIBRATION_QUESTION_EFFECTIVE_N,
    CALIBRATION_QUESTION_INTERVAL_COVERAGE,
    CALIBRATION_QUESTION_PROBABILITY,
    build_calibration_report,
)
from bolsa_analytics.cognitive.auto_adaptive_confidence import measured_r
from bolsa_analytics.cognitive.auto_adaptive_correlation import (
    CORRELATION_BUCKET_DEFAULT,
    build_strategy_correlation_report,
)
from bolsa_analytics.cognitive.auto_adaptive_regime_evidence import (
    build_current_regime_evidence,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (
    ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
    ADAPTIVE_INTERVAL_SEED_DEFAULT,
)
from bolsa_analytics.cognitive.auto_evidence_report import (
    MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
    NOT_MEASURED,
    build_evidence_artifact,
    render_evidence_report,
)

__all__ = [
    "EVIDENCE_LEVELS",
    "EVIDENCE_LEVEL_CONTEXT",
    "EVIDENCE_LEVEL_MATERIAL",
    "EVIDENCE_LEVEL_STATISTICS",
    "EVIDENCE_RUN_SCHEMA",
    "EvidenceRunBlockedError",
    "build_evidence_run_bundle",
    "summarize_evidence_levels",
]

#: Sello del paquete de una corrida de evidencia. Cambiar su forma obliga a subir este sello: dos
#: bundles con el mismo aspecto no pueden venir de instrumentos distintos.
EVIDENCE_RUN_SCHEMA = "auto22_evidence_run_bundle_v1"

#: Etiqueta de lo que no se midió: espejo de ``NOT_MEASURED``/``_INCONCLUSIVE_LABEL`` del render.
INCONCLUSIVE_LABEL = "INCONCLUSIVE"

#: Los tres niveles que el run publica, en orden de lectura (del material al contexto).
EVIDENCE_LEVEL_MATERIAL = "material"
EVIDENCE_LEVEL_STATISTICS = "statistics"
EVIDENCE_LEVEL_CONTEXT = "context"
EVIDENCE_LEVELS: tuple[str, ...] = (
    EVIDENCE_LEVEL_MATERIAL,
    EVIDENCE_LEVEL_STATISTICS,
    EVIDENCE_LEVEL_CONTEXT,
)


class EvidenceRunBlockedError(RuntimeError):
    """La corrida no tiene material medible: se DECLARA bloqueada en vez de publicar un bundle.

    Un bundle sin ningún ciclo con R medible tendría el aspecto de una medición (artefacto, render,
    veredictos ``INCONCLUSIVE``) sin haber medido nada del mercado. Guardarlo como evidencia sería
    exactamente el cero disfrazado que la fase entera existe para evitar: quien llama lo traduce a
    BLOQUEADO (``exit 2``) y no escribe ningún fichero.
    """


def _measured_cycles(rows: Sequence[Any]) -> list[Any]:
    """Ciclos con R medible (mismo cociente que el informe): la muestra real del run."""
    return [row for row in rows if measured_r(row) is not None]


def _number(value: Any) -> str:
    """Número → texto a 4 decimales; ausente/no numérico ⇒ ``NO MEDIDO`` (nunca un ``0`` de relleno)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NOT_MEASURED
    return f"{float(value):.4f}"


def _count(value: Any) -> str:
    """Conteo → texto; ausente ⇒ ``NO MEDIDO`` (distinto del ``0`` legítimo de "medido y vacío")."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NOT_MEASURED
    return str(int(value))


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else NOT_MEASURED


def _row(label: str, value: str, *, inconclusive: bool) -> dict[str, Any]:
    return {"label": label, "value": value, "inconclusive": inconclusive}


def _question_metrics(report: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Métricas de una pregunta del informe; sin pregunta o sin métricas ⇒ ``{}`` (no se inventa)."""
    for row in report.get("questions") or ():
        if isinstance(row, Mapping) and row.get("question") == key:
            metrics = row.get("metrics")
            return dict(metrics) if isinstance(metrics, Mapping) else {}
    return {}


def _material_rows(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Nivel 1 — MATERIAL: el universo medido, sus huecos declarados y su huella."""
    material = artifact.get("material")
    if not isinstance(material, Mapping):
        return [
            _row(
                "Material",
                "NO MEDIDO (corrida sin exportación PAPER)",
                inconclusive=True,
            )
        ]
    requested = material.get("requestedStrategyVersions")
    observed = material.get("observedStrategyVersions")
    requested_text = (
        ", ".join(str(item) for item in requested) if isinstance(requested, list) and requested else NOT_MEASURED
    )
    observed_text = (
        ", ".join(str(item) for item in observed) if isinstance(observed, list) and observed else NOT_MEASURED
    )
    return [
        _row("Origen del material", _text(material.get("materialOrigin")), inconclusive=not material.get("materialOrigin")),
        _row("Cuenta", _text(material.get("account")), inconclusive=not material.get("account")),
        _row("Ciclos cerrados", _count(material.get("closedCycles")), inconclusive=not isinstance(material.get("closedCycles"), (int, float))),
        _row("Medidos (con R)", _count(material.get("cyclesWithRisk")), inconclusive=not isinstance(material.get("cyclesWithRisk"), (int, float))),
        _row("Sin R", _count(material.get("cyclesWithoutRisk")), inconclusive=not isinstance(material.get("cyclesWithoutRisk"), (int, float))),
        _row("Fills seleccionados", _count(material.get("fillsSelected")), inconclusive=not isinstance(material.get("fillsSelected"), (int, float))),
        _row("Fills excluidos (sin versión)", _count(material.get("fillsExcludedNoVersion")), inconclusive=not isinstance(material.get("fillsExcludedNoVersion"), (int, float))),
        _row("Fills excluidos (otra versión)", _count(material.get("fillsExcludedOtherVersion")), inconclusive=not isinstance(material.get("fillsExcludedOtherVersion"), (int, float))),
        _row("Versiones pedidas", requested_text, inconclusive=requested_text == NOT_MEASURED),
        _row("Versiones observadas", observed_text, inconclusive=observed_text == NOT_MEASURED),
        _row("Huella", _text(material.get("fingerprint")), inconclusive=not material.get("fingerprint")),
    ]


def _statistics_rows(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Nivel 2 — ESTADÍSTICA: la lectura del instrumento, con sus sellos y su muestra."""
    report = artifact.get("report")
    report = report if isinstance(report, Mapping) else {}
    aggregate = report.get("aggregate")
    aggregate = aggregate if isinstance(aggregate, Mapping) else {}
    probability = _question_metrics(report, CALIBRATION_QUESTION_PROBABILITY)
    interval = _question_metrics(report, CALIBRATION_QUESTION_INTERVAL_COVERAGE)
    effective_n = _question_metrics(report, CALIBRATION_QUESTION_EFFECTIVE_N)
    coverage = _question_metrics(report, CALIBRATION_QUESTION_COVERAGE)
    declared = probability.get("meanDeclaredProbability")
    return [
        _row("Método de incertidumbre", _text(report.get("method")), inconclusive=not report.get("method")),
        _row("Media R (OOS)", _number(aggregate.get("meanOosExpectancyR")), inconclusive=aggregate.get("meanOosExpectancyR") is None),
        _row("Cobertura esperada (intervalo)", _number(interval.get("expectedCoverage")), inconclusive=interval.get("expectedCoverage") is None),
        _row("Ancho medio del intervalo", _number(interval.get("meanIntervalWidth")), inconclusive=interval.get("meanIntervalWidth") is None),
        _row("P(R>0)", _number(declared), inconclusive=declared is None),
        _row("P(R>0) OOS", _number(aggregate.get("probabilityPositiveOos")), inconclusive=aggregate.get("probabilityPositiveOos") is None),
        _row("WFE", _number(aggregate.get("walkForwardEfficiency")), inconclusive=aggregate.get("walkForwardEfficiency") is None),
        _row("Effective-N (mediana)", _count(effective_n.get("medianEffectiveN")), inconclusive=effective_n.get("medianEffectiveN") is None),
        _row("Cobertura (régimen, celdas cubiertas)", _count(coverage.get("cellsCovered")), inconclusive=coverage.get("cellsCovered") is None),
        _row("Pliegues emparejados", _count(aggregate.get("pairedFoldCount")), inconclusive=aggregate.get("pairedFoldCount") is None),
    ]


def _context_rows(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Nivel 3 — CONTEXTO: régimen actual, evidencia por estrategia y correlación entre estrategias."""
    rows: list[dict[str, Any]] = []
    regime = artifact.get("currentRegime")
    rows.append(_row("Régimen actual", _text(regime), inconclusive=not regime))

    evidence = artifact.get("currentEvidence")
    by_strategy = evidence.get("byStrategy") if isinstance(evidence, Mapping) else None
    if isinstance(by_strategy, Mapping) and by_strategy:
        for version in sorted(str(key) for key in by_strategy):
            cell = by_strategy.get(version)
            cell = cell if isinstance(cell, Mapping) else {}
            probability = cell.get("probabilityPositive")
            edge = _text(cell.get("edgeConfidence") or INCONCLUSIVE_LABEL)
            rows.append(
                _row(
                    f"Evidencia {version}",
                    f"P(R>0) {_number(probability)} ({edge})",
                    inconclusive=probability is None,
                )
            )
    else:
        rows.append(_row("Evidencia del régimen", NOT_MEASURED, inconclusive=True))

    correlation = artifact.get("correlation")
    pairs = correlation.get("pairs") if isinstance(correlation, Mapping) else None
    if isinstance(pairs, Sequence) and not isinstance(pairs, (str, bytes)) and pairs:
        for pair in pairs:
            if not isinstance(pair, Mapping):
                continue
            value = pair.get("correlation")
            notes = ", ".join(str(note) for note in (pair.get("notes") or ()))
            suffix = f" [{notes}]" if notes else ""
            rows.append(
                _row(
                    f"Correlación {pair.get('left')} vs {pair.get('right')}",
                    f"{_number(value)} (cubos={_count(pair.get('sharedBuckets'))}){suffix}",
                    inconclusive=value is None,
                )
            )
    else:
        rows.append(_row("Correlación entre estrategias", NOT_MEASURED, inconclusive=True))
    return rows


def summarize_evidence_levels(artifact: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """(PURA) los TRES niveles de evidencia del artefacto, en filas ``{label, value, inconclusive}``.

    Es la vista que el run imprime y guarda en ``run.json``: material, estadística y contexto. Se
    DERIVA del artefacto (no recalcula nada) y conserva la regla del repo: lo ausente es
    ``NO MEDIDO``/``INCONCLUSIVE``, nunca un cero.
    """
    return {
        EVIDENCE_LEVEL_MATERIAL: _material_rows(artifact),
        EVIDENCE_LEVEL_STATISTICS: _statistics_rows(artifact),
        EVIDENCE_LEVEL_CONTEXT: _context_rows(artifact),
    }


def build_evidence_run_bundle(
    cycles: Iterable[Any] | None = None,
    *,
    material: Mapping[str, Any] | None = None,
    material_origin: str = MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
    broker_venue: str | None = None,
    bucket: str = CORRELATION_BUCKET_DEFAULT,
    current_regime: str | None = None,
    folds: int = CALIBRATION_FOLDS_DEFAULT,
    seed: int = ADAPTIVE_INTERVAL_SEED_DEFAULT,
    level: float = ADAPTIVE_INTERVAL_LEVEL_DEFAULT,
    resamples: int = ADAPTIVE_INTERVAL_RESAMPLES_DEFAULT,
) -> dict[str, Any]:
    """(PURA) compone el bundle de UNA corrida de evidencia, o se declara BLOQUEADO.

    Encadena los productores ya auditados y devuelve ``{schema, materialOrigin, fingerprint,
    artifact, render, levels}``. ``artifact`` es el ``auto20c_evidence_artifact_v1`` que la UI
    importa (mismas claves aditivas de ``AUTO-21``) y ``render`` su ``AUTO EVIDENCE REPORT`` legible.

    ``material_origin`` es OBLIGATORIO en espíritu: el defecto es el **fixture sintético**, de modo
    que un llamante que olvide declarar el material real no herede el sello PAPER por accidente.
    Sin ciclos con R medible lanza ``EvidenceRunBlockedError`` (no hay bundle "vacío").
    """
    rows = list(cycles or ())
    if not _measured_cycles(rows):
        raise EvidenceRunBlockedError(
            "sin ciclos con R medible: no se publica un bundle vacío como si fuera una medición"
        )

    report = build_calibration_report(
        rows,
        folds=folds,
        seed=seed,
        level=level,
        resamples=resamples,
        material=material,
    )
    correlation = build_strategy_correlation_report(rows, bucket=bucket)
    regime = build_current_regime_evidence(
        rows,
        current_regime=current_regime,
        level=level,
        resamples=resamples,
        seed=seed,
    )
    artifact = build_evidence_artifact(
        report,
        material=material,
        broker_venue=broker_venue,
        material_origin=material_origin,
        correlation=correlation.as_dict(),
        current_regime=regime.regime,
        current_evidence=regime.as_dict(),
    )
    return {
        "schema": EVIDENCE_RUN_SCHEMA,
        "materialOrigin": material_origin,
        "fingerprint": (material or {}).get("fingerprint"),
        "artifact": artifact,
        "render": render_evidence_report(artifact),
        "levels": summarize_evidence_levels(artifact),
    }
