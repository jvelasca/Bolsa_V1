"""DÍA-D AUTO — contratos del bucle de realimentación por valor (puro y determinista).

Invariantes que se fijan aquí:

* Veredicto por valor con precedencia declarada: un error de SOFTWARE gana sobre el suelo de
  muestra; un ``expectancyR <= 0`` mata; sin muestra suficiente no se afirma nada.
* Un hueco es ``None``/``NOT_MEASURED``: la media/R total/hit-rate de una muestra vacía NUNCA
  se rellena con ``0``.
* El catálogo de errores reutiliza el vocabulario existente y no inventa familias: un código
  sin dueño se declara ausente, nunca se cataloga a la fuerza.
* El mismo estado produce el mismo payload byte a byte (sin reloj ni aleatoriedad).
"""

from __future__ import annotations

import json

from bolsa_application.dia_d_auto_feedback import (
    DATA,
    DEFAULT_LIMITS,
    ERROR_KINDS,
    EVIDENCE_NOT_MEASURED,
    EVIDENCE_PRELIMINARY,
    EVIDENCE_STRONG,
    EVIDENCE_STRONG_MIN_CYCLES,
    EVIDENCE_SUPPORTED,
    EVIDENCE_SUPPORTED_MIN_CYCLES,
    MIN_VALUE_CYCLES,
    MIN_VALUE_HIT_RATE,
    OPERATIONAL,
    OPERATIONAL_REASON_CODES,
    SCHEMA_VERSION,
    SOFTWARE,
    VALUE_CONFIRMED,
    VALUE_MIXED,
    VALUE_NOT_MEASURED,
    VALUE_OOS_SUPPORTED,
    VALUE_REFUTED,
    VALUE_VERDICTS,
    build_day_matrix,
    build_dia_d_feedback_artifact,
    build_value_scorecard,
    classify_error,
    error_kind_for_exit_state,
    error_kind_for_reason,
    evidence_quality_for,
    normalize_error,
    software_error_for_step,
    summarize_feedback,
)


def _trips(*values: float, day: str = "2026-09-30") -> list[dict]:
    return [
        {"symbol": "AAA", "exitDay": day, "entryDay": day, "realizedR": value}
        for value in values
    ]


# ── Veredicto por valor ──────────────────────────────────────────────────────────


def test_oos_supported_needs_positive_edge_hit_rate_and_supported_sample() -> None:
    # 20 ciclos con edge positivo y hit-rate suficiente ⇒ evidencia OOS SOPORTADA.
    card = build_value_scorecard(
        "AAA",
        round_trips=_trips(*([1.0, 0.5] * 10)),  # 20 ciclos, hit 100%
        days=["2026-09-30"],
    )
    assert card["measuredCycles"] == 20
    assert card["verdict"] == VALUE_OOS_SUPPORTED
    assert card["evidenceQuality"] == EVIDENCE_SUPPORTED
    assert card["expectancyR"] is not None and card["expectancyR"] > 0
    assert card["hitRate"] is not None and card["hitRate"] >= MIN_VALUE_HIT_RATE
    assert card["verdictReason"] == "positive_expectancy"
    # ``CONFIRMED`` queda reservado a evidencia PAPER: no es un veredicto del replay.
    assert VALUE_CONFIRMED not in VALUE_VERDICTS


def test_positive_edge_with_preliminary_sample_is_mixed_not_supported() -> None:
    # 5..19 ciclos: se MIDE, pero no se declara SOPORTADO (D34-04).
    card = build_value_scorecard(
        "AAA",
        round_trips=_trips(1.0, 2.0, 0.5, 1.5, -0.5, 2.0),
        days=["2026-09-30"],
    )
    assert card["measuredCycles"] == 6
    assert card["evidenceQuality"] == EVIDENCE_PRELIMINARY
    assert card["verdict"] == VALUE_MIXED
    assert card["verdictReason"] == "preliminary_sample"
    assert card["expectancyR"] is not None and card["expectancyR"] > 0


def test_evidence_quality_tiers_and_strong_boundary() -> None:
    assert evidence_quality_for(0) == EVIDENCE_NOT_MEASURED
    assert evidence_quality_for(MIN_VALUE_CYCLES - 1) == EVIDENCE_NOT_MEASURED
    assert evidence_quality_for(MIN_VALUE_CYCLES) == EVIDENCE_PRELIMINARY
    assert evidence_quality_for(EVIDENCE_SUPPORTED_MIN_CYCLES - 1) == EVIDENCE_PRELIMINARY
    assert evidence_quality_for(EVIDENCE_SUPPORTED_MIN_CYCLES) == EVIDENCE_SUPPORTED
    assert evidence_quality_for(EVIDENCE_STRONG_MIN_CYCLES - 1) == EVIDENCE_SUPPORTED
    assert evidence_quality_for(EVIDENCE_STRONG_MIN_CYCLES) == EVIDENCE_STRONG
    assert evidence_quality_for("n/d") == EVIDENCE_NOT_MEASURED


def test_refuted_when_expectancy_is_not_positive() -> None:
    card = build_value_scorecard(
        "AAA",
        round_trips=_trips(-1.0, -0.5, -2.0, 0.1, -1.0, -0.8),
        days=["2026-09-30"],
    )
    assert card["verdict"] == VALUE_REFUTED
    assert card["verdictReason"] == "negative_expectancy"


def test_mixed_when_positive_but_hit_rate_below_floor() -> None:
    # Positiva de media pero pocos aciertos: mide, no concluye.
    card = build_value_scorecard(
        "AAA",
        round_trips=_trips(6.0, -1.0, -1.0, -1.0, -1.0, -1.0),
        days=["2026-09-30"],
    )
    assert card["expectancyR"] is not None and card["expectancyR"] > 0
    assert card["hitRate"] == 1 / 6
    assert card["verdict"] == VALUE_MIXED
    assert card["verdictReason"] == "no_conclusive_edge"


def test_not_measured_below_sample_floor() -> None:
    card = build_value_scorecard("AAA", round_trips=_trips(1.0, 1.0), days=["2026-09-30"])
    assert card["measuredCycles"] == 2 < MIN_VALUE_CYCLES
    assert card["verdict"] == VALUE_NOT_MEASURED
    assert card["verdictReason"] == "insufficient_sample"


def test_software_error_wins_over_sample_floor_and_mixed() -> None:
    # Un fallo lógico es evidencia POSITIVA: no se esconde tras el suelo de muestra.
    software = [{"day": "2026-09-30", "symbol": "AAA", "kind": SOFTWARE, "code": "FILL"}]
    card = build_value_scorecard(
        "AAA",
        round_trips=_trips(5.0, -1.0, -1.0),  # muestra por debajo del suelo
        errors=software,
        days=["2026-09-30"],
    )
    assert card["measuredCycles"] < MIN_VALUE_CYCLES
    assert card["verdict"] == VALUE_REFUTED
    assert card["verdictReason"] == "software_divergence"


def test_empty_sample_is_a_gap_never_zero() -> None:
    card = build_value_scorecard("AAA", round_trips=[], days=["2026-09-30"])
    assert card["expectancyR"] is None
    assert card["hitRate"] is None
    assert card["realizedRTotal"] is None
    assert card["measuredCycles"] == 0
    assert card["verdict"] == VALUE_NOT_MEASURED


def test_unreadable_realized_r_is_not_a_cycle() -> None:
    card = build_value_scorecard(
        "AAA",
        round_trips=[
            {"exitDay": "2026-09-30", "realizedR": None},
            {"exitDay": "2026-09-30", "realizedR": "n/d"},
            {"exitDay": "2026-09-30", "realizedR": 1.0},
        ],
        days=["2026-09-30"],
    )
    assert card["measuredCycles"] == 1
    assert card["realizedRTotal"] == 1.0


def test_infinite_realized_r_is_not_a_cycle() -> None:
    # D35-03: un ±inf no es una medición; no debe contar como ciclo ni contaminar el total.
    card = build_value_scorecard(
        "AAA",
        round_trips=[
            {"entryDay": "2026-09-30", "exitDay": "2026-09-30", "realizedR": float("inf")},
            {"entryDay": "2026-09-30", "exitDay": "2026-09-30", "realizedR": float("-inf")},
            {"entryDay": "2026-09-30", "exitDay": "2026-09-30", "realizedR": 1.0},
        ],
        days=["2026-09-30"],
    )
    assert card["measuredCycles"] == 1
    assert card["realizedRTotal"] == 1.0
    assert card["byDay"]["2026-09-30"]["cycles"] == 1
    assert "Infinity" not in json.dumps(card)


# ── Catálogo de errores (aislado y reutilizando el vocabulario) ───────────────────


def test_software_only_on_deterministic_divergence() -> None:
    assert software_error_for_step("FILL", "DIVERGENT") == "FILL"
    assert software_error_for_step("ORDER", "DIVERGENT") == "ORDER"
    assert software_error_for_step("SIGNAL", "DIVERGENT") == "SIGNAL"
    # Un paso NO determinista que diverge no es un fallo lógico catalogado.
    assert software_error_for_step("PROTECTION", "DIVERGENT") is None
    assert software_error_for_step("FILL", "MATCH") is None


def test_reason_codes_map_to_the_existing_taxonomy() -> None:
    assert error_kind_for_reason("reservation_unmeasurable") == OPERATIONAL
    assert error_kind_for_reason("protection_missing") == OPERATIONAL
    assert error_kind_for_reason("stale_data") == DATA
    assert error_kind_for_reason("atr_unknown") == DATA
    assert error_kind_for_reason("sector_unknown") == DATA
    assert error_kind_for_reason("no_mark_data") == DATA
    assert error_kind_for_reason("approved") is None
    assert error_kind_for_reason("") is None


def test_operational_reason_catalog_is_explicit() -> None:
    assert "reservation_unmeasurable" in OPERATIONAL_REASON_CODES
    assert "protection_missing" in OPERATIONAL_REASON_CODES


def test_exit_and_execution_states_map_to_operational() -> None:
    assert error_kind_for_exit_state("ABANDONED") == OPERATIONAL
    assert error_kind_for_exit_state("EMERGENCY") == OPERATIONAL
    assert error_kind_for_exit_state("FILLED") is None


def test_classify_error_prefers_software_then_operational_then_data() -> None:
    assert classify_error(step="FILL", verdict="DIVERGENT", reason_code="stale_data") == {
        "kind": SOFTWARE,
        "code": "FILL",
    }
    assert classify_error(reconcile_state="drift") == {"kind": SOFTWARE, "code": "drift"}
    assert classify_error(exit_state="ABANDONED") == {"kind": OPERATIONAL, "code": "ABANDONED"}
    assert classify_error(execution_status="RETRY") == {
        "kind": OPERATIONAL,
        "code": "RETRY",
    }
    assert classify_error(reason_code="stale_data") == {"kind": DATA, "code": "stale_data"}
    assert classify_error(reason_code="approved") is None


def test_normalize_error_rejects_unknown_kind_or_empty_code() -> None:
    assert normalize_error(kind="GHOST", code="X") is None
    assert normalize_error(kind=SOFTWARE, code="") is None
    row = normalize_error(day="2026-09-30T00:00:00Z", symbol="AAA", kind="data", code="stale_data")
    assert row == {"day": "2026-09-30", "symbol": "AAA", "kind": DATA, "code": "stale_data"}


# ── Matriz valor × día y resumen ─────────────────────────────────────────────────


def test_day_matrix_cell_outcomes() -> None:
    card = build_value_scorecard(
        "AAA",
        round_trips=[
            {"entryDay": "2026-09-30", "exitDay": "2026-09-30", "realizedR": 1.0},
            {"entryDay": "2026-10-01", "exitDay": "2026-10-01", "realizedR": -1.0},
        ],
        errors=[{"day": "2026-10-02", "symbol": "AAA", "kind": SOFTWARE, "code": "FILL"}],
        days=["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"],
    )
    matrix = build_day_matrix([card], days=["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"])
    assert len(matrix) == 1
    outcomes = [cell["outcome"] for cell in matrix[0]["cells"]]
    assert outcomes == ["GAIN", "LOSS", "ERROR", "NOT_MEASURED"]


def test_by_day_attributes_by_entry_day_not_exit_day() -> None:
    # D34-02: un ciclo abierto en D y cerrado FUERA de la ventana pertenece a D.
    card = build_value_scorecard(
        "AAA",
        round_trips=[
            {"entryDay": "2026-09-30", "exitDay": "2026-10-07", "realizedR": 2.4},
        ],
        days=["2026-09-29", "2026-09-30", "2026-10-01"],
    )
    assert card["measuredCycles"] == 1
    assert card["byDay"]["2026-09-30"]["cycles"] == 1
    assert card["byDay"]["2026-09-30"]["realizedR"] == 2.4
    assert card["daysCovered"] == 1


def test_cycle_without_entry_day_is_not_attributed_to_any_day() -> None:
    card = build_value_scorecard(
        "AAA",
        round_trips=[{"exitDay": "2026-09-30", "realizedR": 1.0}],
        days=["2026-09-30"],
    )
    assert card["measuredCycles"] == 1
    assert card["daysCovered"] == 0
    assert card["byDay"]["2026-09-30"]["cycles"] == 0


def test_summary_counts_verdicts_evidence_and_error_families() -> None:
    values = [
        {"verdict": VALUE_OOS_SUPPORTED, "evidenceQuality": EVIDENCE_SUPPORTED},
        {"verdict": VALUE_MIXED, "evidenceQuality": EVIDENCE_PRELIMINARY},
        {"verdict": VALUE_REFUTED, "evidenceQuality": EVIDENCE_PRELIMINARY},
        {"verdict": VALUE_NOT_MEASURED, "evidenceQuality": EVIDENCE_NOT_MEASURED},
    ]
    errors = [
        {"kind": SOFTWARE, "code": "FILL"},
        {"kind": OPERATIONAL, "code": "protection_missing"},
        {"kind": DATA, "code": "stale_data"},
    ]
    summary = summarize_feedback(values, errors)
    assert summary["values"] == 4
    assert summary["oosSupported"] == 1
    assert summary["mixed"] == 1
    assert summary["refuted"] == 1
    assert summary["notMeasured"] == 1
    assert summary["measuredValues"] == 3
    assert summary["byEvidenceQuality"][EVIDENCE_SUPPORTED] == 1
    assert summary["byEvidenceQuality"][EVIDENCE_PRELIMINARY] == 2
    assert summary["byEvidenceQuality"][EVIDENCE_NOT_MEASURED] == 1
    assert summary["errors"] == {SOFTWARE: 1, OPERATIONAL: 1, DATA: 1, "total": 3}


# ── Artefacto ────────────────────────────────────────────────────────────────────


def _artifact() -> dict:
    card = build_value_scorecard(
        "AAA",
        round_trips=_trips(1.0, 2.0, 0.5, 1.5, -0.5, 2.0),
        days=["2026-09-30"],
    )
    return build_dia_d_feedback_artifact(
        window_from="2026-09-30",
        window_to="2026-09-30",
        days=["2026-09-30"],
        values=[card],
        errors=[{"kind": SOFTWARE, "code": "FILL", "day": "2026-09-30", "symbol": "AAA"}],
        gate={"ready": False, "verdict": "INCONCLUSIVE"},
        meta={"account": "acc", "bump": "2.11.34-beta"},
    )


def test_artifact_shape_and_determinism() -> None:
    first = _artifact()
    second = _artifact()
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["schemaVersion"] == SCHEMA_VERSION
    assert first["kind"] == "DIA_D_AUTO_FEEDBACK"
    assert first["readOnly"] is True
    assert first["matrixBasis"] == "entryDay"
    assert first["window"] == {"from": "2026-09-30", "to": "2026-09-30", "days": ["2026-09-30"]}
    assert first["values"][0]["symbol"] == "AAA"
    assert first["summary"]["errors"]["total"] == 1
    assert first["limits"] == list(DEFAULT_LIMITS)


def test_artifact_dedupes_and_sorts_days_and_values() -> None:
    card_a = build_value_scorecard("BBB", days=["2026-10-01"])
    card_b = build_value_scorecard("AAA", days=["2026-10-01"])
    artifact = build_dia_d_feedback_artifact(
        window_from="2026-10-01",
        window_to="2026-10-01",
        days=["2026-10-01", "2026-10-01"],
        values=[card_a, card_b],
    )
    assert artifact["window"]["days"] == ["2026-10-01"]
    assert [value["symbol"] for value in artifact["values"]] == ["AAA", "BBB"]
    assert set(artifact) >= {"summary", "matrix", "errors", "gate", "meta", "limits"}
    assert ERROR_KINDS == (SOFTWARE, OPERATIONAL, DATA)
