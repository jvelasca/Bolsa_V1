"""AUTO-22 — RUN de evidencia: compone lo auditado, o se declara BLOQUEADO. Nunca miente.

Certifica el contrato del bundle de la corrida de evidencia:

* **Una sola aritmética.** ``build_evidence_run_bundle`` no recalcula nada: encadena los productores
  ya auditados (``AUTO-19B``/``AUTO-20C``/``AUTO-21``) y el artefacto sale con las mismas claves.
* **Fail-closed.** Sin ciclos con R medible NO hay bundle "vacío": ``EvidenceRunBlockedError``.
* **Procedencia declarada.** El defecto NUNCA es PAPER real: un llamante que olvide declarar el
  material obtiene el sello del fixture sintético, no el de una corrida de mercado.
* **``NO MEDIDO`` de verdad.** Una correlación que no se pudo medir aparece como hueco declarado;
  un ``0.0`` de relleno sería una independencia lineal inventada.

Puro y hermético: sin PG, sin red, sin reloj.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bolsa_analytics.cognitive.auto_evidence_report import (
    MATERIAL_ORIGIN_PAPER_REAL,
    MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
    NOT_MEASURED,
)
from bolsa_analytics.cognitive.auto_evidence_run import (
    EVIDENCE_LEVEL_CONTEXT,
    EVIDENCE_LEVEL_MATERIAL,
    EVIDENCE_LEVEL_STATISTICS,
    EVIDENCE_LEVELS,
    EVIDENCE_RUN_SCHEMA,
    EvidenceRunBlockedError,
    build_evidence_run_bundle,
    summarize_evidence_levels,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "auto_calibration_cycles.json"

_MATERIAL = {
    "materialOrigin": MATERIAL_ORIGIN_PAPER_REAL,
    "account": "acc-auto22",
    "closedCycles": 126,
    "cyclesWithRisk": 126,
    "cyclesWithoutRisk": 0,
    "fingerprint": "sha256:auto22-material",
    "requestedStrategyVersions": ["wf-trend"],
    "observedStrategyVersions": ["wf-trend"],
}


def _fixture_cycles() -> list[dict[str, object]]:
    return list(json.loads(_FIXTURE.read_text(encoding="utf-8"))["cycles"])


def _row(rows: list[dict[str, object]], label: str) -> dict[str, object]:
    return next(row for row in rows if row["label"] == label)


# ── Fail-closed: sin material medible no hay bundle ────────────────────────────────


def test_the_run_is_blocked_without_any_cycle() -> None:
    """Sin ciclos no se publica un artefacto 'vacío pero con aspecto de medición'."""
    with pytest.raises(EvidenceRunBlockedError):
        build_evidence_run_bundle([])


def test_the_run_is_blocked_when_no_cycle_has_a_measurable_r() -> None:
    """Ciclos sin denominador de R no son evidencia: el run se DECLARA bloqueado."""
    cycles = [
        {
            "cycleId": f"cyc-{index}",
            "strategyVersion": "orb-a",
            "pnl": "3",
            "closedAt": f"2026-01-{index + 1:02d}T10:00:00Z",
        }
        for index in range(6)
    ]
    with pytest.raises(EvidenceRunBlockedError):
        build_evidence_run_bundle(cycles)


# ── El bundle compuesto ────────────────────────────────────────────────────────────


def test_the_bundle_composes_the_audited_pieces_and_declares_its_provenance() -> None:
    """Un bundle determinista con las tres lecturas publicadas y la huella del material."""
    bundle = build_evidence_run_bundle(
        _fixture_cycles(),
        material=dict(_MATERIAL),
        material_origin=MATERIAL_ORIGIN_PAPER_REAL,
        broker_venue="paper",
    )

    assert bundle["schema"] == EVIDENCE_RUN_SCHEMA
    assert bundle["materialOrigin"] == MATERIAL_ORIGIN_PAPER_REAL
    assert bundle["fingerprint"] == _MATERIAL["fingerprint"]
    artifact = bundle["artifact"]
    assert artifact["material"] == _MATERIAL
    assert artifact["brokerVenue"] == "paper"
    # Las lecturas de AUTO-21 viajan en el artefacto (claves aditivas, esquema intacto).
    assert "correlation" in artifact
    assert "currentRegime" in artifact
    assert "currentEvidence" in artifact
    assert bundle["render"].startswith("AUTO EVIDENCE REPORT")
    # El bundle es PURO: dos composiciones del mismo material son idénticas (sin reloj).
    again = build_evidence_run_bundle(
        _fixture_cycles(),
        material=dict(_MATERIAL),
        material_origin=MATERIAL_ORIGIN_PAPER_REAL,
        broker_venue="paper",
    )
    assert again == bundle


def test_the_default_origin_is_the_synthetic_fixture_never_paper_real() -> None:
    """Un llamante que olvide declarar el material NO hereda el sello PAPER real."""
    bundle = build_evidence_run_bundle(_fixture_cycles())

    assert bundle["materialOrigin"] == MATERIAL_ORIGIN_SYNTHETIC_FIXTURE
    assert bundle["artifact"]["materialOrigin"] == MATERIAL_ORIGIN_SYNTHETIC_FIXTURE
    assert bundle["artifact"]["material"] is None


def test_the_three_levels_publish_the_measured_numbers_and_the_declared_gaps() -> None:
    """NIVEL 2 lleva P(R>0)/P(R>0) OOS/WFE; NIVEL 3 lleva régimen, evidencia y correlación."""
    bundle = build_evidence_run_bundle(
        _fixture_cycles(), material=dict(_MATERIAL), resamples=50
    )
    levels = bundle["levels"]

    assert tuple(levels) == EVIDENCE_LEVELS
    statistics = levels[EVIDENCE_LEVEL_STATISTICS]
    assert _row(statistics, "P(R>0)")["inconclusive"] is False
    assert _row(statistics, "P(R>0) OOS")["inconclusive"] is False
    assert _row(statistics, "WFE")["inconclusive"] is False

    context = levels[EVIDENCE_LEVEL_CONTEXT]
    assert _row(context, "Régimen actual")["value"] != NOT_MEASURED
    # La matriz de correlación se publica par a par (nada se colapsa en un agregado).
    assert any(str(row["label"]).startswith("Correlación ") for row in context)


def test_the_material_level_reports_the_universe_and_its_fingerprint() -> None:
    """NIVEL 1 declara el universo medido, sus huecos y su huella (sin ella, NO MEDIDO)."""
    with_material = summarize_evidence_levels(
        {"material": dict(_MATERIAL)}
    )[EVIDENCE_LEVEL_MATERIAL]
    assert _row(with_material, "Huella")["value"] == "sha256:auto22-material"
    assert _row(with_material, "Ciclos cerrados")["value"] == "126"
    assert _row(with_material, "Sin R")["value"] == "0"
    assert _row(with_material, "Sin R")["inconclusive"] is False

    without_material = summarize_evidence_levels({})[EVIDENCE_LEVEL_MATERIAL]
    assert NOT_MEASURED in str(without_material[0]["value"])
    assert without_material[0]["inconclusive"] is True


def test_an_unmeasured_correlation_is_a_declared_gap_never_a_zero() -> None:
    """Un par sin cubos compartidos ⇒ hueco declarado; jamás un ``0.0000`` de relleno."""
    cycles = [
        {
            "cycleId": f"cyc-a-{index}",
            "strategyVersion": "orb-a",
            "pnl": "3",
            "riskAmount": "5",
            "closedAt": f"2026-01-{index + 1:02d}T10:00:00Z",
        }
        for index in range(6)
    ] + [
        {
            "cycleId": f"cyc-b-{index}",
            "strategyVersion": "orb-b",
            "pnl": "2",
            "riskAmount": "5",
            # Instantes fuera de los cubos de ``orb-a``: sin cubos compartidos.
            "closedAt": f"2026-06-{index + 1:02d}T10:00:00Z",
        }
        for index in range(6)
    ]
    bundle = build_evidence_run_bundle(cycles, resamples=50)
    context = bundle["levels"][EVIDENCE_LEVEL_CONTEXT]

    pair = _row(context, "Correlación orb-a vs orb-b")
    assert pair["inconclusive"] is True
    assert NOT_MEASURED in str(pair["value"])
    assert "0.0000" not in str(pair["value"])


def test_the_levels_derive_from_the_artifact_without_recalculating() -> None:
    """``summarize_evidence_levels`` es una LECTURA: el mismo artefacto da las mismas filas."""
    bundle = build_evidence_run_bundle(
        _fixture_cycles(), material=dict(_MATERIAL), resamples=50
    )

    assert summarize_evidence_levels(bundle["artifact"]) == bundle["levels"]
