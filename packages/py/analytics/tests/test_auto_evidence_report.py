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
    OUT_OF_SCOPE_AUTO21,
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
    assert OUT_OF_SCOPE_AUTO21 in text
    assert ALLOCATION_CHANGE_NONE in _row_for(text, "Allocation change")
    assert EXECUTION_REALITY_VIRTUAL_PAPER in text


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


def test_the_render_rows_use_the_canonical_calibration_keys() -> None:
    """El render no puede desalinearse del instrumento: sus filas son las preguntas canónicas."""
    from bolsa_analytics.cognitive.auto_adaptive_calibration import _CALIBRATION_QUESTIONS
    from bolsa_analytics.cognitive.auto_evidence_report import _CALIBRATION_ROWS

    assert {key for key, _ in _CALIBRATION_ROWS} == set(_CALIBRATION_QUESTIONS)
