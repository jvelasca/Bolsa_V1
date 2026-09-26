"""AUTO-23 — VALIDACIÓN de la evidencia: un consumidor de la ÚNICA aritmética, nunca una segunda.

Certifica el contrato del informe de validación:

* **Una sola aritmética.** El barrido ``P(R>0)`` vs N COMPONE ``build_evidence_run_bundle`` y copia
  sus cifras; si las recalculara, el número publicado podría divergir del instrumento auditado.
* **``NO MEDIDO`` de verdad.** Un tamaño muestral mayor que el material medido es un hueco
  declarado, jamás una fila fabricada ni un cero de relleno.
* **Lectura, no gate.** La estabilidad de régimen publica global vs por-régimen y sus divergencias;
  no convierte nada en permiso de sizing.
* **Procedencia declarada.** El defecto es el fixture sintético, nunca PAPER real.

Puro y hermético: sin PG, sin red, sin reloj.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    measured_r,
    order_cycles_by_instant,
)
from bolsa_analytics.cognitive.auto_evidence_report import (
    MATERIAL_ORIGIN_PAPER_REAL,
    MATERIAL_ORIGIN_SYNTHETIC_FIXTURE,
)
from bolsa_analytics.cognitive.auto_evidence_run import build_evidence_run_bundle
from bolsa_analytics.cognitive.auto_evidence_validation import (
    CORRELATION_VALIDATION_SCHEMA,
    EDGE_VERDICT_INCONCLUSIVE,
    EDGE_VERDICT_SUPPORTED,
    EDGE_VERDICTS,
    EVIDENCE_VALIDATION_SCHEMA,
    REGIME_STABILITY_SCHEMA,
    SAMPLE_SIZE_SWEEP_SCHEMA,
    EvidenceValidationBlockedError,
    build_correlation_validation,
    build_regime_stability,
    build_sample_size_sweep,
    build_validation_report,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "auto_calibration_cycles.json"

_SWEEP_KWARGS = {"folds": 3, "seed": 42, "level": 0.90, "resamples": 50}


def _fixture_cycles() -> list[dict[str, object]]:
    return list(json.loads(_FIXTURE.read_text(encoding="utf-8"))["cycles"])


def _measured(cycles: list[dict[str, object]]) -> list[dict[str, object]]:
    ordered, _undated = order_cycles_by_instant(cycles)
    return [row for row in ordered if measured_r(row) is not None]


def _report_of(bundle: dict[str, object]) -> dict[str, object]:
    artifact = bundle["artifact"]
    assert isinstance(artifact, dict)
    report = artifact["report"]
    assert isinstance(report, dict)
    return report


def _probability_of(report: dict[str, object]) -> object:
    for row in report["questions"]:  # type: ignore[index]
        assert isinstance(row, dict)
        if row.get("question") == "probability_positive_calibration":
            metrics = row.get("metrics")
            assert isinstance(metrics, dict)
            return metrics.get("meanDeclaredProbability")
    raise AssertionError("falta la pregunta de probabilidad")


# ── Barrido P(R>0) vs N: compone, no recalcula ─────────────────────────────────────


def test_the_sweep_copies_the_probability_from_the_only_arithmetic() -> None:
    """El ``P(R>0)`` del barrido ES el del bundle ``AUTO-22``: no hay una segunda aritmética."""
    cycles = _fixture_cycles()
    measured = _measured(cycles)
    size = len(measured)

    sweep = build_sample_size_sweep(cycles, sizes=(size,), **_SWEEP_KWARGS)  # type: ignore[arg-type]
    bundle = build_evidence_run_bundle(measured, **_SWEEP_KWARGS)  # type: ignore[arg-type]
    report = _report_of(bundle)
    aggregate = report["aggregate"]
    assert isinstance(aggregate, dict)

    row = sweep["rows"][0]
    assert row["measured"] is True
    assert row["probabilityPositive"] == _probability_of(report)
    assert row["probabilityPositiveOos"] == aggregate.get("probabilityPositiveOos")
    assert row["walkForwardEfficiency"] == aggregate.get("walkForwardEfficiency")


def test_a_size_beyond_the_measured_material_is_not_measured_never_fabricated() -> None:
    """``N`` mayor que el material medido ⇒ fila ``NO MEDIDO``: no se fabrica una medición."""
    sweep = build_sample_size_sweep(
        _fixture_cycles(), sizes=(16, 100_000), **_SWEEP_KWARGS  # type: ignore[arg-type]
    )
    assert sweep["requestedSizes"] == [16, 100_000]
    beyond = sweep["rows"][1]
    assert beyond["size"] == 100_000
    assert beyond["measured"] is False
    assert beyond["probabilityPositive"] is None
    assert beyond["probabilityPositiveOos"] is None
    assert beyond["walkForwardEfficiency"] is None
    assert "insufficient_measured_cycles" in beyond["notes"]


def test_the_sweep_declares_the_sample_and_never_selects_a_size() -> None:
    """El barrido publica la serie y la regla de muestreo; no elige el ``N`` que mejor suena."""
    sweep = build_sample_size_sweep(
        _fixture_cycles(), sizes=(16, 32, 16), **_SWEEP_KWARGS  # type: ignore[arg-type]
    )
    assert sweep["schema"] == SAMPLE_SIZE_SWEEP_SCHEMA
    assert sweep["method"] == "chronological_prefix_sweep_v1"
    # Duplicados colapsados y orden ascendente: la serie es determinista.
    assert sweep["requestedSizes"] == [16, 32]
    assert sweep["measuredCycles"] == len(_measured(_fixture_cycles()))
    assert sweep["undatedCycles"] == 0
    assert [row["size"] for row in sweep["rows"]] == [16, 32]


def test_the_sweep_is_blocked_without_measured_cycles() -> None:
    sweep = build_sample_size_sweep(
        [{"cycleId": "c1", "strategyVersion": "a", "pnl": "1"}],
        sizes=(16,),
        **_SWEEP_KWARGS,  # type: ignore[arg-type]
    )
    assert sweep["measuredCycles"] == 0
    assert sweep["rows"][0]["measured"] is False
    assert "no_measured_cycles" in sweep["notes"]


# ── Estabilidad de régimen: lectura global vs por régimen ───────────────────────────


def test_regime_stability_publishes_global_and_per_regime_verdicts() -> None:
    report = build_regime_stability(_fixture_cycles(), resamples=50, seed=42, level=0.90)
    assert report["schema"] == REGIME_STABILITY_SCHEMA
    assert "TREND_UP" in report["regimesPresent"]
    assert report["strategies"], "el fixture declara estrategias"
    for strategy in report["strategies"]:
        global_cell = strategy["global"]
        assert global_cell["verdict"] == EDGE_VERDICTS.get(
            global_cell["edgeConfidence"], EDGE_VERDICT_INCONCLUSIVE
        )
        for cell in strategy["byRegime"].values():
            assert cell["verdict"] == EDGE_VERDICTS.get(
                cell["edgeConfidence"], EDGE_VERDICT_INCONCLUSIVE
            )


def test_regime_divergences_are_declared_as_a_reading_not_a_gate() -> None:
    """Una divergencia (global vs régimen) se PUBLICA; no bloquea ni mueve el reparto."""
    report = build_regime_stability(_fixture_cycles(), resamples=50, seed=42, level=0.90)
    for strategy in report["strategies"]:
        for divergence in strategy["divergences"]:
            assert divergence["regimeVerdict"] != divergence["globalVerdict"]
            assert divergence["regime"] in strategy["byRegime"]


# ── Validación de la correlación: el número y su diagnóstico P3-2 ───────────────────


def test_correlation_validation_publishes_every_bucket_with_its_diagnostics() -> None:
    report = build_correlation_validation(_fixture_cycles(), buckets=("day", "week"))
    assert report["schema"] == CORRELATION_VALIDATION_SCHEMA
    assert set(report["buckets"]) == {"day", "week"}
    for bucket in ("day", "week"):
        entry = report["buckets"][bucket]
        assert entry["strategies"], "el fixture tiene varias estrategias"
        assert entry["pairs"], "hay pares que medir"
        per_strategy = entry["diagnostics"]["strategies"]
        assert per_strategy
        for stats in per_strategy.values():
            assert "activeBuckets" in stats
            assert "singleCycleBucketShare" in stats
        for pair in entry["pairs"]:
            diagnostics = pair["diagnostics"]
            assert diagnostics["sharedBuckets"] == pair["sharedBuckets"]
            if diagnostics["sharedBuckets"]:
                assert diagnostics["sharedSingleCycleShare"] is not None


def test_a_pair_without_shared_buckets_is_a_declared_gap_never_a_zero() -> None:
    cycles = [
        {
            "cycleId": f"a-{index}",
            "strategyVersion": "orb-a",
            "pnl": "3",
            "riskAmount": "5",
            "marketRegime": "TREND_UP",
            "closedAt": f"2026-01-{index + 1:02d}T10:00:00Z",
        }
        for index in range(6)
    ] + [
        {
            "cycleId": f"b-{index}",
            "strategyVersion": "orb-b",
            "pnl": "2",
            "riskAmount": "5",
            "marketRegime": "RANGE",
            "closedAt": f"2026-06-{index + 1:02d}T10:00:00Z",
        }
        for index in range(6)
    ]
    report = build_correlation_validation(cycles, buckets=("day",))
    pair = report["buckets"]["day"]["pairs"][0]
    assert pair["correlation"] is None
    assert pair["diagnostics"]["sharedBuckets"] == 0
    assert pair["diagnostics"]["sharedSingleCycleShare"] is None


# ── Informe compuesto: procedencia, muestra y fail-closed ───────────────────────────


def test_the_validation_report_declares_its_provenance_and_is_deterministic() -> None:
    cycles = _fixture_cycles()
    material = {
        "materialOrigin": MATERIAL_ORIGIN_PAPER_REAL,
        "fingerprint": "sha256:auto23-material",
    }
    report = build_validation_report(
        cycles,
        material=material,
        material_origin=MATERIAL_ORIGIN_PAPER_REAL,
        broker_venue="paper",
        **_SWEEP_KWARGS,  # type: ignore[arg-type]
    )
    assert report["schema"] == EVIDENCE_VALIDATION_SCHEMA
    assert report["materialOrigin"] == MATERIAL_ORIGIN_PAPER_REAL
    assert report["brokerVenue"] == "paper"
    assert report["fingerprint"] == "sha256:auto23-material"
    assert report["measuredCycles"] == len(_measured(cycles))
    assert report["regimeStability"]["strategies"]
    assert report["correlationValidation"]["buckets"]
    again = build_validation_report(
        cycles,
        material=material,
        material_origin=MATERIAL_ORIGIN_PAPER_REAL,
        broker_venue="paper",
        **_SWEEP_KWARGS,  # type: ignore[arg-type]
    )
    assert again == report


def test_the_default_origin_is_the_synthetic_fixture_never_paper_real() -> None:
    report = build_validation_report(_fixture_cycles(), **_SWEEP_KWARGS)  # type: ignore[arg-type]
    assert report["materialOrigin"] == MATERIAL_ORIGIN_SYNTHETIC_FIXTURE
    assert report["fingerprint"] is None


def test_the_validation_report_is_blocked_without_measured_cycles() -> None:
    with pytest.raises(EvidenceValidationBlockedError):
        build_validation_report([])
    with pytest.raises(EvidenceValidationBlockedError):
        build_validation_report(
            [{"cycleId": "c1", "strategyVersion": "a", "pnl": "1"}]
        )


def test_a_strong_global_verdict_stays_separate_from_the_regime_verdict() -> None:
    """El veredicto global no se hereda a un régimen sin celda ni al revés (lectura honesta)."""
    report = build_regime_stability(_fixture_cycles(), resamples=50, seed=42, level=0.90)
    for strategy in report["strategies"]:
        for regime, cell in strategy["byRegime"].items():
            if cell.get("measuredN") == 0:
                assert cell["verdict"] == EDGE_VERDICT_INCONCLUSIVE
            assert regime  # la celda declara SIEMPRE su régimen
    assert EDGE_VERDICT_SUPPORTED in EDGE_VERDICTS.values()
