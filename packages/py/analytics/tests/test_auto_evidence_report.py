"""AUTO-20C — artefacto + render del AUTO EVIDENCE REPORT: declaran, no inventan.

Certifican las dos propiedades que hacen honesto el instrumento:

* **El informe viaja verbatim.** El artefacto envuelve el informe de calibración sin tocar ninguna
  medición; solo añade el sello de esquema y la procedencia (PAPER **virtual**).
* **Lo no medido se imprime INCONCLUSIVE.** El render no fabrica un veredicto que el informe no
  emitió: una pregunta ausente o un ``walkForwardEfficiency`` sin cociente honesto se declaran.
"""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_calibration import build_calibration_report
from bolsa_analytics.cognitive.auto_evidence_report import (
    ALLOCATION_CHANGE_NONE,
    EVIDENCE_ARTIFACT_SCHEMA,
    EXECUTION_REALITY_NOTE,
    EXECUTION_REALITY_VIRTUAL_PAPER,
    MATERIAL_ORIGIN_PAPER_REAL,
    NOT_MEASURED,
    REAL_MONEY_AT_RISK,
    build_evidence_artifact,
    render_evidence_report,
)

_MATERIAL: dict[str, Any] = {
    "materialOrigin": MATERIAL_ORIGIN_PAPER_REAL,
    "closedCycles": 26,
    "cyclesWithRisk": 17,
    "cyclesWithoutRisk": 9,
    "regimesPresent": ["RANGE", "TREND_UP"],
    "fingerprint": "sha256:material",
    "requestedStrategyVersions": ["orb-a"],
    "observedStrategyVersions": ["orb-a"],
    "versionsRequestedWithoutMaterial": [],
    "versionsObservedNotRequested": [],
    "fillsTotalForAccount": 500,
    "fillsSelected": 420,
    "fillsExcludedNoVersion": 80,
    "fillsExcludedOtherVersion": 0,
    "reservationsRead": 17,
    "riskReadSaturated": False,
}


def _row_for(text: str, label: str) -> str:
    return next(line for line in text.splitlines() if line.strip().startswith(label))


def test_the_artifact_declares_the_virtual_paper_reality() -> None:
    """El invariante de la fase: PAPER es VIRTUAL; ningún dinero real está en riesgo."""
    artifact = build_evidence_artifact(build_calibration_report([]), material=None)

    assert artifact["schema"] == EVIDENCE_ARTIFACT_SCHEMA
    assert artifact["executionReality"] == EXECUTION_REALITY_VIRTUAL_PAPER
    assert artifact["realMoneyAtRisk"] is REAL_MONEY_AT_RISK is False
    assert artifact["note"] == EXECUTION_REALITY_NOTE
    assert "VIRTUAL" in artifact["note"]
    assert artifact["material"] is None


def test_the_artifact_publishes_the_report_verbatim() -> None:
    """El artefacto no reinterpreta la medición: el informe va tal cual lo emitió el instrumento."""
    report = build_calibration_report([])
    artifact = build_evidence_artifact(report, material=dict(_MATERIAL), broker_venue="paper")

    assert artifact["report"] == report.as_dict()
    assert artifact["material"] == _MATERIAL
    assert artifact["brokerVenue"] == "paper"
    assert artifact["materialOrigin"] == MATERIAL_ORIGIN_PAPER_REAL


def test_the_render_labels_every_calibration_question() -> None:
    """Cada pregunta del informe se imprime con su veredicto, sin invertir su sentido."""
    report = {
        "questions": [
            {"question": "shrinkage_calibration", "verdict": "supported"},
            {"question": "effective_n_calibration", "verdict": "supported"},
            {"question": "interval_coverage", "verdict": "inconclusive"},
            {"question": "edge_sign_calibration", "verdict": "not_supported"},
            {"question": "probability_positive_calibration", "verdict": "supported"},
            {"question": "confidence_calibration", "verdict": "not_supported"},
            {"question": "coverage_calibration", "verdict": "supported"},
        ],
        "aggregate": {"walkForwardEfficiency": None},
    }
    text = render_evidence_report(
        build_evidence_artifact(report, material=dict(_MATERIAL), broker_venue="paper")
    )

    assert _row_for(text, "Shrinkage").rstrip().endswith("SUPPORTED")
    assert _row_for(text, "Effective-N").rstrip().endswith("SUPPORTED")
    assert _row_for(text, "Interval coverage").rstrip().endswith("INCONCLUSIVE")
    assert _row_for(text, "Edge sign").rstrip().endswith("NOT_SUPPORTED")
    assert _row_for(text, "P(R>0)").rstrip().endswith("SUPPORTED")
    assert _row_for(text, "Confidence calibration").rstrip().endswith("NOT_SUPPORTED")
    assert _row_for(text, "Coverage (regime)").rstrip().endswith("SUPPORTED")
    # Sin cociente honesto, el WFE no se inventa.
    assert _row_for(text, "Walk-forward efficiency").rstrip().endswith("INCONCLUSIVE")


def test_the_render_shows_the_walk_forward_efficiency_when_it_exists() -> None:
    """Con un cociente real, el render muestra el número en vez de etiquetarlo."""
    artifact = build_evidence_artifact(
        {"questions": [], "aggregate": {"walkForwardEfficiency": 0.4213}}, material=None
    )

    assert _row_for(render_evidence_report(artifact), "Walk-forward efficiency").rstrip().endswith(
        "0.4213"
    )


def test_the_render_marks_missing_evidence_inconclusive() -> None:
    """Sin ciclos, las siete filas quedan INCONCLUSIVE: no se fabrica ningún veredicto."""
    text = render_evidence_report(build_evidence_artifact(build_calibration_report([])))

    for label in (
        "Shrinkage",
        "Effective-N",
        "Interval coverage",
        "Edge sign",
        "P(R>0)",
        "Confidence calibration",
        "Coverage (regime)",
        "Walk-forward efficiency",
    ):
        assert _row_for(text, label).rstrip().endswith("INCONCLUSIVE")
    assert "(sin material declarado" in text


def test_the_render_declares_the_perimeter_and_the_frozen_allocation() -> None:
    """El render declara el contorno del volcado y que la evidencia NO mueve el reparto."""
    artifact = build_evidence_artifact(
        {"questions": [], "aggregate": {}}, material=dict(_MATERIAL), broker_venue="paper"
    )
    text = render_evidence_report(artifact)

    assert "excluded (no version):80" in text
    assert "excluded (other):     0" in text
    assert "regimes:              RANGE, TREND_UP (2)" in text
    assert _row_for(text, "Current regime").rstrip().endswith(NOT_MEASURED)
    assert _row_for(text, "Current evidence").rstrip().endswith(NOT_MEASURED)
    assert ALLOCATION_CHANGE_NONE in _row_for(text, "Allocation change")
    assert EXECUTION_REALITY_VIRTUAL_PAPER in text


def test_the_render_fills_the_current_regime_and_evidence_when_the_artifact_brings_them() -> None:
    """AUTO-21: con lectura, el render imprime el régimen y la P(R>0) por estrategia, no un stub."""
    artifact = build_evidence_artifact(
        {"questions": [], "aggregate": {}},
        material=dict(_MATERIAL),
        current_regime="TREND_UP",
        current_evidence={
            "regime": "TREND_UP",
            "byStrategy": {
                "orb-a": {
                    "probabilityPositive": 0.7012,
                    "edgeConfidence": "HIGH",
                },
                "orb-b": {"probabilityPositive": None, "edgeConfidence": "UNKNOWN"},
            },
        },
        correlation={
            "bucket": "day",
            "pairs": [
                {
                    "left": "orb-a",
                    "right": "orb-b",
                    "correlation": 0.42,
                    "sharedBuckets": 6,
                    "notes": [],
                },
                {
                    "left": "orb-a",
                    "right": "orb-c",
                    "correlation": None,
                    "sharedBuckets": 0,
                    "notes": ["no_shared_buckets"],
                },
            ],
        },
    )
    text = render_evidence_report(artifact)

    assert _row_for(text, "Current regime").rstrip().endswith("TREND_UP")
    evidence_line = _row_for(text, "Current evidence")
    assert "orb-a: P(R>0) 0.7012 (HIGH)" in evidence_line
    assert "orb-b: P(R>0) NO MEDIDO (UNKNOWN)" in evidence_line
    assert "correlation (bucket=day)" in text
    assert "orb-a vs orb-b: 0.4200 (cubos=6)" in text
    assert "orb-a vs orb-c: NO MEDIDO (cubos=0) [no_shared_buckets]" in text


def test_the_artifact_omits_the_auto21_keys_when_there_is_no_reading() -> None:
    """Sin lectura, las claves aditivas NO se inventan: el artefacto sigue siendo el auditado."""
    artifact = build_evidence_artifact({"questions": [], "aggregate": {}}, material=None)

    assert "correlation" not in artifact
    assert "currentRegime" not in artifact
    assert "currentEvidence" not in artifact


def test_the_render_distinguishes_an_absent_perimeter_list_from_an_empty_one() -> None:
    """Ausente y vacío NO son lo mismo: ausente ⇒ ``NO MEDIDO``; lista vacía ⇒ ``(ninguna)``."""
    material: dict[str, Any] = {
        "materialOrigin": MATERIAL_ORIGIN_PAPER_REAL,
        "requestedStrategyVersions": [],
        # `observedStrategyVersions` ausente a propósito.
    }
    text = render_evidence_report(
        build_evidence_artifact({"questions": [], "aggregate": {}}, material=material)
    )

    assert "requested versions:   (ninguna)" in text
    assert "observed versions:    NO MEDIDO" in text


def test_the_render_treats_a_non_list_perimeter_value_as_not_measured() -> None:
    """Un escalar donde se espera una lista NO se itera: se declara ``NO MEDIDO`` (espejo de TS)."""
    material: dict[str, Any] = {
        "materialOrigin": MATERIAL_ORIGIN_PAPER_REAL,
        "requestedStrategyVersions": "orb-a",
        "observedStrategyVersions": {"a": 1},
    }
    text = render_evidence_report(
        build_evidence_artifact({"questions": [], "aggregate": {}}, material=material)
    )

    assert "requested versions:   NO MEDIDO" in text
    assert "observed versions:    NO MEDIDO" in text
    # No se itera la cadena carácter a carácter.
    assert "o, r, b" not in text


def test_the_render_rows_use_the_canonical_calibration_keys() -> None:
    """El render no puede desalinearse del instrumento: sus filas son las preguntas canónicas."""
    from bolsa_analytics.cognitive.auto_adaptive_calibration import _CALIBRATION_QUESTIONS
    from bolsa_analytics.cognitive.auto_evidence_report import _CALIBRATION_ROWS

    assert {key for key, _ in _CALIBRATION_ROWS} == set(_CALIBRATION_QUESTIONS)
