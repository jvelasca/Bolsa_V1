"""DÍA-D AUTO — contratos del comparador declarado vs ejecutado (puro y determinista).

Invariantes que se fijan aquí:

* Un paso con ambos lados medibles e iguales es ``MATCH``; distinto es ``DIVERGENT``.
* Un lado sin medir (``None``/``""``/ausente) es ``NOT_MEASURED`` — jamás un ``0`` ni un
  "coincide con vacío".
* El veredicto global nunca esconde una divergencia real detrás de un hueco (``DIVERGENT``
  gana a ``PARTIAL``).
* El mismo estado produce el mismo payload byte a byte (sin reloj, sin aleatoriedad).
"""

from __future__ import annotations

import json

from bolsa_application.dia_d_auto import (
    CHAIN_STEPS,
    SCHEMA_VERSION,
    VERDICT_DIVERGENT,
    VERDICT_MATCH,
    VERDICT_NOT_MEASURED,
    VERDICT_PARTIAL,
    build_dia_d_auto_artifact,
    compare_declared_vs_executed,
    compare_step,
    cycle_closure_summary,
    normalize_day,
    summarize_comparison,
    values_equal,
)


def test_match_when_both_sides_are_equal() -> None:
    row = compare_step(2, 2)
    assert row["verdict"] == VERDICT_MATCH
    assert row["measurement"] == "COMPLETE"
    assert row["declared"] == 2.0
    assert row["executed"] == 2.0


def test_divergent_when_both_sides_differ() -> None:
    row = compare_step(2, 1)
    assert row["verdict"] == VERDICT_DIVERGENT
    assert row["measurement"] == "COMPLETE"


def test_not_measured_when_either_side_is_missing() -> None:
    for declared, executed in ((None, 3), (3, None), (None, None)):
        row = compare_step(declared, executed)
        assert row["verdict"] == VERDICT_NOT_MEASURED, (declared, executed)
        assert row["measurement"] == "UNKNOWN", (declared, executed)


def test_empty_string_is_a_gap_not_a_measurement() -> None:
    # "" no es una medición: no puede "coincidir" con otro vacío ni colarse como valor.
    assert compare_step("", "")["verdict"] == VERDICT_NOT_MEASURED
    assert compare_step("", 0)["verdict"] == VERDICT_NOT_MEASURED


def test_zero_is_measured_and_distinct_from_a_gap() -> None:
    # Un 0 es una MEDICIÓN ("no pasó nada"); un None es un HUECO. No son lo mismo.
    row = compare_step(0, 0)
    assert row["verdict"] == VERDICT_MATCH
    assert row["declared"] == 0.0
    gap = compare_step(0, None)
    assert gap["verdict"] == VERDICT_NOT_MEASURED
    assert gap["executed"] is None


def test_booleans_compare_identically_without_numeric_coercion() -> None:
    assert compare_step(True, True)["verdict"] == VERDICT_MATCH
    assert compare_step(True, False)["verdict"] == VERDICT_DIVERGENT


def test_float_tolerance_absorbs_rounding_but_not_real_drift() -> None:
    assert values_equal(1.0000000001, 1.0)
    assert not values_equal(1.01, 1.0)


def test_comparison_covers_the_chain_in_order() -> None:
    rows = compare_declared_vs_executed({"SIGNAL": 1}, {"SIGNAL": 1})
    assert [row["step"] for row in rows] == list(CHAIN_STEPS)
    # Los pasos ausentes en ambos lados son huecos declarados, no ceros.
    assert all(
        row["verdict"] == VERDICT_NOT_MEASURED
        for row in rows
        if row["step"] != "SIGNAL"
    )


def test_summary_prefers_divergence_over_gap() -> None:
    comparison = compare_declared_vs_executed(
        {"SIGNAL": 1, "FILL": 2},
        {"SIGNAL": 1, "FILL": 1},
    )
    summary = summarize_comparison(comparison)
    # Hay coincidencia (SIGNAL) y divergencia (FILL) y huecos: gana DIVERGENT.
    assert summary["verdict"] == VERDICT_DIVERGENT
    assert summary["match"] == 1
    assert summary["divergent"] == 1
    assert summary["notMeasured"] == len(CHAIN_STEPS) - 2


def test_summary_partial_when_measured_and_gaps_without_divergence() -> None:
    comparison = compare_declared_vs_executed({"SIGNAL": 1}, {"SIGNAL": 1})
    assert summarize_comparison(comparison)["verdict"] == VERDICT_PARTIAL


def test_summary_match_when_all_steps_agree() -> None:
    agree = {step: 1 for step in CHAIN_STEPS}
    comparison = compare_declared_vs_executed(agree, agree)
    summary = summarize_comparison(comparison)
    assert summary["verdict"] == VERDICT_MATCH
    assert summary["notMeasured"] == 0


def test_summary_not_measured_when_nothing_is_measured() -> None:
    summary = summarize_comparison(compare_declared_vs_executed(None, None))
    assert summary["verdict"] == VERDICT_NOT_MEASURED


def test_normalize_day_rejects_unreadable_values() -> None:
    assert normalize_day("2026-09-30T00:00:00Z") == "2026-09-30"
    assert normalize_day("2026-09-30") == "2026-09-30"
    assert normalize_day("") == ""
    assert normalize_day(None) == ""
    assert normalize_day("30/09/2026") == ""


def test_artifact_is_deterministic_and_json_stable() -> None:
    kwargs = {
        "day": "2026-09-30",
        "declared": {"SIGNAL": 1, "FILL": 2},
        "executed": {"SIGNAL": 1, "FILL": 1},
        "oos": {"realizedR": 1.5},
        "meta": {"account": "acc", "versionA": "v1"},
    }
    first = build_dia_d_auto_artifact(**kwargs)
    second = build_dia_d_auto_artifact(**kwargs)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_artifact_declares_read_only_and_carries_limits() -> None:
    artifact = build_dia_d_auto_artifact(
        day="2026-09-30",
        declared={"FILL": 1},
        executed={"FILL": 1},
    )
    assert artifact["schemaVersion"] == SCHEMA_VERSION
    assert artifact["kind"] == "DIA_D_AUTO"
    assert artifact["readOnly"] is True
    assert artifact["day"] == "2026-09-30"
    assert artifact["limits"], "el artefacto debe declarar sus límites"
    # Un paso confirmado y el resto sin hechos durables: ni MATCH ni NOT_MEASURED.
    assert artifact["summary"]["verdict"] == VERDICT_PARTIAL


def test_artifact_declared_without_executed_is_a_gap() -> None:
    # Sin hechos durables en D, TODO el lado ejecutado es un hueco declarado (no un cero).
    artifact = build_dia_d_auto_artifact(day="2026-09-30", declared={"FILL": 1})
    assert artifact["summary"]["verdict"] == VERDICT_NOT_MEASURED
    assert artifact["summary"]["notMeasured"] == len(CHAIN_STEPS)


# ── Identidad única del ciclo (D34-01) ──────────────────────────────────────────


def test_cycle_closure_one_when_a_d_cycle_closes_later() -> None:
    summary = cycle_closure_summary(["c1"], ["c1"])
    assert summary["step"] == 1
    assert summary["opened"] == ["c1"]
    assert summary["closed"] == ["c1"]
    assert summary["open"] == []
    assert summary["unmeasured"] is False


def test_cycle_closure_zero_when_d_cycle_still_open() -> None:
    summary = cycle_closure_summary(["c1"], [])
    assert summary["step"] == 0
    assert summary["open"] == ["c1"]
    assert summary["closed"] == []


def test_cycle_closure_ignores_cycles_not_born_in_d() -> None:
    # Un ciclo abierto en D-1 y cerrado en D NO es un D-cycle: no puede afirmar cierre.
    summary = cycle_closure_summary(["c_born_in_d"], ["c_born_in_d_minus_1"])
    assert summary["step"] == 0
    assert summary["opened"] == ["c_born_in_d"]
    assert summary["closed"] == []


def test_cycle_closure_none_when_no_opening_is_reconstructible() -> None:
    summary = cycle_closure_summary([], ["c1"])
    assert summary["step"] is None
    assert summary["unmeasured"] is True
    assert summary["opened"] == []
