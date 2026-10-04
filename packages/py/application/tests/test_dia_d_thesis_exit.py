"""V2.88.45 · DÍA-D AUTO — contratos del QUIRÓFANO del ``THESIS_EXIT`` (puro).

Invariantes que se fijan aquí:

* Sólo entran los ciclos con ``exitMechanism == THESIS_EXIT``; el resto no vota.
* La dirección se conserva tal cual (inferida en el ledger); un hueco es ``None``, nunca ``"long"``.
* La captura se mide con ``mfeR > 0`` sobre el resultado NO negativo (misma semántica sellada en
  ``capture_study``): un MFE no positivo es un hueco y ``leftOnTableR`` nunca supera el MFE.
* Con fricción ``PARTIAL`` el R neto es ``None`` (jamás el bruto disfrazado de neto).
* Los cubos de edad son duros y ordenados; una fecha ilegible cae en ``unknown``.
* El plegado publica dispersión entre sorteos, fragilidad, motivos crudos y concentración.
* El artefacto es determinista y declara su contrato (read-only, advisory).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from bolsa_application.dia_d_attribution import capture_study, cycle_key
from bolsa_application.dia_d_multi_sampling import DECISION_ROUTES
from bolsa_application.dia_d_thesis_exit import (
    AGE_BUCKETS,
    KIND,
    MECHANISM,
    SCHEMA_VERSION,
    STOP_PATHS,
    build_thesis_exit_artifact,
)

# ── Utilidades de muestra (ciclos sintéticos, sin I/O) ───────────────────────────


def _row(
    *,
    mechanism: str = MECHANISM,
    realized: float | None = -1.0,
    net: float | None = -1.5,
    measurement: str = "COMPLETE",
    friction: float | None = 0.5,
    mae: float | None = -0.8,
    mfe: float | None = 0.4,
    adverse: float | None = -0.6,
    slip: float | None = 50.0,
    year: str | None = "2022",
    strategy: str | None = "v2.7",
    direction: str | None = "long",
    regime: str | None = "high_vol",
    op: str | None = "HIGH_VOLATILITY",
    entry: str = "2022-01-05",
    exit_day: str = "2022-01-07",
    symbol: str = "AAA",
    reason: str = "thesis_exit",
    invalidation_level_r: float | None = None,
    current_stop_at_exit_r: float | None = None,
    stop_above_level_r: float | None = None,
    level_equals_initial_stop: bool | None = None,
    stop_basis_mismatch_r: float | None = None,
    mae_vs_level_r: float | None = None,
    mae_reached_level: bool | None = None,
    thesis_condition: str | None = "sin_geometria",
    thesis_exit_route: str | None = None,
    stop_changed: bool | None = None,
    breakeven_reached: bool | None = None,
    structural_stop_candidate: bool | None = None,
    touch_before_exit: bool | None = None,
    days_to_first_touch: int | None = None,
    first_touch_day: str | None = None,
    min_mark_r: float | None = None,
    persisted_mae_r: float | None = None,
    persisted_mae_at_exit_r: float | None = None,
    decision_route: str | None = None,
    stop_touch_days: int | None = None,
    stop_evaluated_on_touch: bool | None = None,
    decider_ran_on_touch: bool | None = None,
    stop_fired_not_filled: bool | None = None,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "entryDay": entry,
        "exitDay": exit_day,
        "realizedR": realized,
        "maeR": mae,
        "mfeR": mfe,
        "year": year,
        "regime": regime,
        "operationalRegime": op,
        "strategyVersion": strategy,
        "direction": direction,
        "exitMechanism": mechanism,
        "exitReason": reason,
        "frictionCost": friction,
        "frictionR": friction,
        "frictionMeasurement": measurement,
        "netRealizedR": net,
        "entryAdverseR": adverse,
        "entryAdverseWindowDays": 3,
        "entrySlippageBps": slip,
        # ── Capa v4: geometría de la invalidación (hueco por defecto, nunca 0) ────
        "invalidationLevelR": invalidation_level_r,
        "currentStopAtExitR": current_stop_at_exit_r,
        "stopAboveLevelR": stop_above_level_r,
        "levelEqualsInitialStop": level_equals_initial_stop,
        "stopBasisMismatchR": stop_basis_mismatch_r,
        "maeVsLevelR": mae_vs_level_r,
        "maeReachedLevel": mae_reached_level,
        "thesisExitCondition": thesis_condition,
        # ── Capa v5: desambiguación THESIS_EXIT vs STOP (hueco por defecto, nunca 0) ──
        "thesisExitRoute": thesis_exit_route,
        "stopChanged": stop_changed,
        "breakevenReached": breakeven_reached,
        "structuralStopCandidate": structural_stop_candidate,
        "touchBeforeExit": touch_before_exit,
        "daysToFirstTouch": days_to_first_touch,
        "firstTouchDay": first_touch_day,
        "minMarkR": min_mark_r,
        "persistedMaeR": persisted_mae_r,
        "persistedMaeAtExitR": persisted_mae_at_exit_r,
        # ── Capa v6: correlación decisión↔ciclo (hueco por defecto, nunca 0) ──────
        "decisionRoute": decision_route,
        "stopTouchDays": stop_touch_days,
        "stopEvaluatedOnTouch": stop_evaluated_on_touch,
        "deciderRanOnTouch": decider_ran_on_touch,
        "stopFiredNotFilled": stop_fired_not_filled,
        "timelineStartsAt": "first_full_tick_after_entry",
    }


def _ledger(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"cycles": rows}


# ── Selección ────────────────────────────────────────────────────────────────────


def test_only_thesis_exit_cycles_are_selected():
    ledgers = [
        _ledger([_row(), _row(mechanism="STOP_EJECUTADO", realized=0.1)]),
        _ledger([_row(realized=-2.0)]),
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    assert artifact["global"]["cycles"] == 2
    assert artifact["coverage"]["cyclesTotal"] == 2
    assert artifact["mechanism"] == MECHANISM


def test_direction_is_kept_verbatim_and_a_gap_is_never_assumed_long():
    ledgers = [
        _ledger([_row(direction="short"), _row(direction=None, symbol="BBB")]),
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    labels = {row["direction"] for row in artifact["byDirection"]}
    assert labels == {"short", "unknown"}


# ── Geometría: captura acotada al MFE positivo ───────────────────────────────────


def test_capture_and_left_on_table_are_none_when_mfe_is_not_positive():
    ledgers = [_ledger([_row(mfe=0.0, realized=-1.0)])]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    excursion = artifact["global"]["excursion"]
    assert excursion["mfeR"]["mean"] == 0.0
    # Sin premio previo ni la captura ni el premio dejado en la mesa estan definidos
    # (misma semantica sellada en capture_study: un mfeR no positivo es un hueco).
    assert excursion["capture"]["measured"] == 0
    assert excursion["capture"]["mean"] is None
    assert excursion["leftOnTableR"]["measured"] == 0
    assert excursion["leftOnTableR"]["mean"] is None


def test_capture_and_left_on_table_are_measured_when_mfe_positive():
    ledgers = [_ledger([_row(realized=1.0, mfe=2.0)])]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    excursion = artifact["global"]["excursion"]
    assert excursion["capture"]["mean"] == pytest.approx(0.5)
    assert excursion["leftOnTableR"]["mean"] == pytest.approx(1.0)


def test_capture_is_never_negative_and_left_on_table_never_exceeds_mfe():
    # Cierre en perdida con premio previo: la captura es 0 (no negativa) y TODO el
    # MFE queda sobre la mesa (no mfeR + |perdida|, que inflaria el premio perdido).
    ledgers = [_ledger([_row(realized=-1.5, mfe=2.0)])]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    excursion = artifact["global"]["excursion"]
    assert excursion["capture"]["mean"] == pytest.approx(0.0)
    assert excursion["leftOnTableR"]["mean"] == pytest.approx(2.0)
    assert excursion["leftOnTableR"]["mean"] <= excursion["mfeR"]["mean"]


def test_capture_matches_the_sealed_capture_study_semantics():
    # Paridad con el canonico sellado (v2.88.40, A39-01): por ciclo, capturedR =
    # max(realizedR, 0), ratio = capturedR / mfeR y leftOnTableR = max(mfeR - capturedR, 0).
    rows = [
        _row(realized=1.0, mfe=2.0, symbol="AAA"),
        _row(realized=-1.0, mfe=0.5, symbol="BBB"),
        _row(realized=0.0, mfe=1.0, symbol="CCC"),
    ]
    ledgers = [_ledger(rows)]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    canonical = capture_study(
        rows,
        excursions_by_cycle={cycle_key(row): {"mfeR": row["mfeR"]} for row in rows},
    )
    excursion = artifact["global"]["excursion"]
    assert excursion["capture"]["mean"] == pytest.approx(canonical["captureRatio"]["mean"])
    assert excursion["leftOnTableR"]["mean"] == pytest.approx(canonical["leftOnTableR"]["mean"])
    assert excursion["capture"]["measured"] == canonical["measuredCycles"]


# ── Regla del suelo: PARTIAL nunca publica neto ──────────────────────────────────


def test_net_is_none_with_partial_friction_never_gross():
    ledgers = [
        _ledger([_row(net=None, measurement="PARTIAL")]),
        _ledger([_row(net=None, measurement="PARTIAL")]),
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    net = artifact["global"]["realizedRNet"]
    assert net["total"] is None
    assert net["cyclesUnmeasured"] == 2
    assert artifact["global"]["fragility"]["fragile"] is True
    assert "net_partial" in artifact["global"]["fragility"]["reasons"]
    # El bruto sigue afirmándose: no se confunde con el neto (total por sorteo = -1 en cada uno).
    assert artifact["global"]["realizedRGross"]["total"]["mean"] == pytest.approx(-1.0)


# ── Cubos de edad declarados y ordenados ─────────────────────────────────────────


def test_age_buckets_are_hard_declared_and_ordered():
    ledgers = [
        _ledger(
            [
                _row(entry="2022-01-05", exit_day="2022-01-07"),  # 2 días -> 1-3
                _row(entry="2022-01-05", exit_day="2022-01-12"),  # 7 días -> 4-10
                _row(entry="2022-01-05", exit_day="2022-01-25"),  # 20 días -> 11-30
                _row(entry="2022-01-05", exit_day="2022-02-20"),  # 46 días -> >30
                _row(entry="", exit_day=""),  # ilegible -> unknown
            ]
        )
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    labels = [row["ageBucket"] for row in artifact["byAgeBucket"]]
    assert labels == list(AGE_BUCKETS)
    by_bucket = {row["ageBucket"]: row["cycles"] for row in artifact["byAgeBucket"]}
    assert by_bucket["1-3"] == 1 and by_bucket["4-10"] == 1
    assert by_bucket["11-30"] == 1 and by_bucket[">30"] == 1 and by_bucket["unknown"] == 1


# ── Plegado por dimensión, fragilidad, motivos y concentración ───────────────────


def test_fold_by_strategy_reports_dispersion_and_fragility():
    ledgers = [
        _ledger([_row(strategy="v2.7", realized=-1.0)]),
        _ledger([_row(strategy="v2.7", realized=-0.5), _row(strategy="v2.8", realized=0.5)]),
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    by_strategy = {row["strategy"]: row for row in artifact["byStrategy"]}
    assert set(by_strategy) == {"v2.7", "v2.8"}
    assert by_strategy["v2.7"]["drawsWithCell"] == 2
    assert by_strategy["v2.7"]["cycles"] == 2
    assert by_strategy["v2.7"]["realizedRGross"]["expectancyR"]["mean"] == pytest.approx(-0.75)
    # El bucket presente en un solo sorteo es fragile y lo declara.
    assert by_strategy["v2.8"]["fragility"]["fragile"] is True
    assert "insufficient_draws" in by_strategy["v2.8"]["fragility"]["reasons"]


def test_raw_reason_tokens_and_concentration_are_declared():
    ledgers = [
        _ledger(
            [
                _row(symbol="AAA", reason="thesis_exit"),
                _row(symbol="AAA", reason="thesis_invalidation"),
                _row(symbol="BBB", reason="thesis_exit"),
            ]
        )
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    assert artifact["rawReasonTokens"] == {"thesis_exit": 2, "thesis_invalidation": 1}
    concentration = artifact["concentration"]
    assert concentration["distinctSymbols"] == 2
    assert concentration["topSymbol"] == "AAA"
    assert concentration["topSymbolShare"] == pytest.approx(2 / 3)
    assert concentration["topWeek"] == "2022-W01"
    assert concentration["topWeekShare"] == pytest.approx(1.0)


def test_entry_quality_shares_are_declared():
    ledgers = [_ledger([_row(adverse=-0.6), _row(adverse=-1.2), _row(adverse=-0.1)])]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    adverse = artifact["global"]["entryQuality"]["adverseR"]
    assert adverse["measured"] == 3
    assert adverse["shareBelowHalfR"] == pytest.approx(2 / 3)
    assert adverse["shareBelowOneR"] == pytest.approx(1 / 3)


# ── Condición de la invalidación (capa v4) ───────────────────────────────────────


def test_invalidation_block_measures_the_frozen_level_and_the_stop():
    ledgers = [
        _ledger(
            [
                _row(
                    invalidation_level_r=-1.0,
                    current_stop_at_exit_r=-0.6,
                    stop_above_level_r=0.4,
                    level_equals_initial_stop=True,
                    stop_basis_mismatch_r=0.0,
                    mae_vs_level_r=0.2,
                    mae_reached_level=True,
                    thesis_condition="nivel_igual_stop",
                )
            ]
        )
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=ledgers)
    invalidation = artifact["global"]["invalidation"]
    assert invalidation["cycles"] == 1
    assert invalidation["measured"] == 1
    assert invalidation["levelEqualsInitialStop"]["count"] == 1
    assert invalidation["levelEqualsInitialStop"]["share"] == pytest.approx(1.0)
    assert invalidation["maeReachedLevel"]["count"] == 1
    assert invalidation["invalidationLevelR"]["mean"] == pytest.approx(-1.0)
    assert invalidation["currentStopAtExitR"]["mean"] == pytest.approx(-0.6)
    assert invalidation["stopBasisMismatchR"]["measured"] == 1
    assert invalidation["stopBasisMismatchR"]["shareNonZero"] == pytest.approx(0.0)
    assert invalidation["condition"] == {"nivel_igual_stop": 1}


def test_invalidation_block_declares_a_distinct_level_and_counts_the_basis_mismatch():
    """Un nivel distinto del stop capturado y una base de R discrepante se declaran, no se ocultan."""
    row = _row(
        invalidation_level_r=-0.5,
        current_stop_at_exit_r=-1.0,
        stop_above_level_r=-0.5,
        level_equals_initial_stop=False,
        stop_basis_mismatch_r=0.75,
        mae_vs_level_r=-1.1,
        mae_reached_level=False,
        thesis_condition="nivel_distinto_stop",
    )
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger([row])])
    invalidation = artifact["global"]["invalidation"]
    assert invalidation["levelEqualsInitialStop"]["count"] == 0
    assert invalidation["stopBasisMismatchR"]["mean"] == pytest.approx(0.75)
    assert invalidation["stopBasisMismatchR"]["shareNonZero"] == pytest.approx(1.0)
    assert invalidation["condition"] == {"nivel_distinto_stop": 1}


def test_invalidation_block_without_geometry_declares_the_gap():
    """Sin la costura capturada, la condición es un hueco declarado (nunca 0)."""
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger([_row(), _row()])])
    invalidation = artifact["global"]["invalidation"]
    assert invalidation["cycles"] == 2
    assert invalidation["measured"] == 0
    assert invalidation["levelEqualsInitialStop"]["share"] is None
    assert invalidation["invalidationLevelR"]["mean"] is None
    assert invalidation["stopBasisMismatchR"]["measured"] == 0
    assert invalidation["stopBasisMismatchR"]["shareNonZero"] is None
    assert invalidation["condition"] == {"sin_geometria": 2}


def test_invalidation_block_distinguishes_a_measured_zero_from_a_gap():
    """El MAE que NO alcanzó el nivel es un dato medido (``False``), no un hueco ``None``."""
    row = _row(
        invalidation_level_r=-1.0,
        current_stop_at_exit_r=-1.0,
        stop_above_level_r=0.0,
        level_equals_initial_stop=True,
        mae_vs_level_r=-0.2,
        mae_reached_level=False,
        thesis_condition="nivel_igual_stop",
    )
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger([row])])
    invalidation = artifact["global"]["invalidation"]
    assert invalidation["maeReachedLevel"]["measured"] == 1
    assert invalidation["maeReachedLevel"]["count"] == 0
    assert invalidation["maeReachedLevel"]["share"] == pytest.approx(0.0)


# ── Desambiguación THESIS_EXIT vs STOP (capa v5) ─────────────────────────────────


def test_disambiguation_block_reports_the_mae_route_and_no_structural_candidate():
    row = _row(
        thesis_exit_route="ruta_mae",
        stop_changed=False,
        breakeven_reached=False,
        structural_stop_candidate=False,
        touch_before_exit=True,
        days_to_first_touch=2,
        first_touch_day="2022-01-06",
        min_mark_r=0.0,
        persisted_mae_r=-1.2,
        persisted_mae_at_exit_r=-1.1,
    )
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger([row])])
    disambiguation = artifact["global"]["disambiguation"]
    assert disambiguation["cycles"] == 1
    assert disambiguation["route"] == {"ruta_mae": 1}
    assert disambiguation["structuralStopCandidate"]["count"] == 0
    assert disambiguation["structuralStopCandidate"]["measured"] == 1
    assert disambiguation["structuralStopCandidate"]["share"] == pytest.approx(0.0)
    assert disambiguation["touchBeforeExit"]["count"] == 1
    assert disambiguation["daysToFirstTouch"]["mean"] == pytest.approx(2.0)
    assert disambiguation["firstTouchMeasured"] == 1
    assert disambiguation["persistedMaeR"]["mean"] == pytest.approx(-1.2)


def test_disambiguation_flags_a_structural_stop_candidate_as_measured():
    row = _row(thesis_exit_route="ruta_ambas", structural_stop_candidate=True)
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger([row])])
    disambiguation = artifact["global"]["disambiguation"]
    assert disambiguation["structuralStopCandidate"]["count"] == 1
    assert disambiguation["routeByMaeReached"]["ruta_ambas"]["unknown"] == 1


def test_disambiguation_by_route_and_stop_path_axes():
    rows = [
        _row(thesis_exit_route="ruta_mae", stop_changed=False, symbol="AAA"),
        _row(thesis_exit_route="ruta_mae", stop_changed=True, breakeven_reached=True, symbol="BBB"),
        _row(thesis_exit_route=None, symbol="CCC"),  # sin_geometria + stop path unknown
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger(rows)])
    by_route = {row["route"]: row["cycles"] for row in artifact["byRoute"]}
    assert by_route == {"ruta_mae": 2, "sin_geometria": 1}
    by_stop = {row["stopPath"]: row["cycles"] for row in artifact["byStopPath"]}
    assert by_stop["sin_cambio"] == 1
    assert by_stop["breakeven"] == 1
    assert by_stop["unknown"] == 1
    labels = [row["stopPath"] for row in artifact["byStopPath"]]
    assert labels == [path for path in STOP_PATHS if path in by_stop]


# ── Correlación DECISIÓN↔CICLO (capa v6) ─────────────────────────────────────────


def test_decision_correlation_block_reports_routes_and_booleans():
    rows = [
        _row(
            decision_route="stop_evaluado_sin_materializar",
            structural_stop_candidate=True,
            stop_touch_days=1,
            stop_evaluated_on_touch=True,
            decider_ran_on_touch=True,
            stop_fired_not_filled=True,
            symbol="AAA",
        ),
        _row(
            decision_route="materializado",
            structural_stop_candidate=True,
            stop_touch_days=1,
            stop_evaluated_on_touch=True,
            decider_ran_on_touch=True,
            stop_fired_not_filled=False,
            symbol="BBB",
        ),
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger(rows)])
    correlation = artifact["global"]["decisionCorrelation"]
    assert correlation["cycles"] == 2
    assert correlation["route"] == {"materializado": 1, "stop_evaluado_sin_materializar": 1}
    assert correlation["stopEvaluatedOnTouch"] == {"count": 2, "measured": 2, "share": 1.0}
    assert correlation["stopFiredNotFilled"]["count"] == 1
    assert correlation["stopTouchDays"]["mean"] == pytest.approx(1.0)
    assert correlation["timelineStartsAt"] == "first_full_tick_after_entry"
    assert correlation["routeByStructuralStopCandidate"]["materializado"]["candidate"] == 1


def test_decision_correlation_by_route_axis_is_ordered_and_declared():
    rows = [
        _row(decision_route="materializado", symbol="AAA"),
        _row(decision_route=None, symbol="BBB"),  # hueco => sin_traza
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger(rows)])
    by_route = {row["decisionRoute"]: row["cycles"] for row in artifact["byDecisionRoute"]}
    assert by_route == {"materializado": 1, "sin_traza": 1}
    labels = [row["decisionRoute"] for row in artifact["byDecisionRoute"]]
    assert labels == [route for route in DECISION_ROUTES if route in by_route]


def test_decision_correlation_route_splits_the_a_and_c_cases():
    """Capa v7: A (``stop_evaluado_sin_orden``) y C (``orden_creada_sin_fill``) se cuentan aparte."""
    rows = [
        _row(decision_route="stop_evaluado_sin_orden", symbol="AAA"),
        _row(decision_route="orden_creada_sin_fill", symbol="BBB"),
        _row(decision_route="stop_evaluado_sin_materializar", symbol="CCC"),  # hueco no medido
    ]
    artifact = build_thesis_exit_artifact(draw_ledgers=[_ledger(rows)])
    correlation = artifact["global"]["decisionCorrelation"]
    assert correlation["route"] == {
        "orden_creada_sin_fill": 1,
        "stop_evaluado_sin_materializar": 1,
        "stop_evaluado_sin_orden": 1,
    }
    labels = [row["decisionRoute"] for row in artifact["byDecisionRoute"]]
    assert labels == [route for route in DECISION_ROUTES if route in correlation["route"]]


# ── Determinismo y contrato ──────────────────────────────────────────────────────


def test_artifact_is_deterministic_and_declares_its_contract():
    ledgers = [
        _ledger([_row(), _row(direction="short", mfe=1.5, realized=0.5)]),
        _ledger([_row(strategy=None, measurement="PARTIAL", net=None)]),
    ]
    first = build_thesis_exit_artifact(draw_ledgers=ledgers)
    again = build_thesis_exit_artifact(draw_ledgers=ledgers)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert first["schemaVersion"] == SCHEMA_VERSION == "dia-d-thesis-exit-v5"
    assert first["kind"] == KIND == "DIA_D_AUTO_THESIS_EXIT"
    assert first["readOnly"] is True
    assert first["basis"] == "entryDay"
    assert first["axes"]
    assert first["limits"]
    assert first["coverage"]["detailCaptured"] is True


def test_empty_draws_declare_none_not_zero():
    artifact = build_thesis_exit_artifact(draw_ledgers=[])
    assert artifact["draws"] == 0
    assert artifact["global"]["cycles"] == 0
    assert artifact["global"]["realizedRGross"]["expectancyR"] is None
    assert artifact["global"]["realizedRNet"]["total"] is None
    assert artifact["global"]["excursion"]["maeR"]["mean"] is None
    assert artifact["global"]["disambiguation"]["route"] == {}
    assert artifact["global"]["disambiguation"]["daysToFirstTouch"]["mean"] is None
    assert artifact["global"]["disambiguation"]["structuralStopCandidate"]["measured"] == 0
    assert artifact["global"]["decisionCorrelation"]["route"] == {}
    assert artifact["global"]["decisionCorrelation"]["stopEvaluatedOnTouch"]["measured"] == 0
    assert artifact["byStrategy"] == []
    assert artifact["byRoute"] == []
    assert artifact["byStopPath"] == []
    assert artifact["byDecisionRoute"] == []
    assert artifact["concentration"]["distinctSymbols"] == 0
    assert artifact["concentration"]["topSymbol"] is None


def test_no_motor_import_is_pulled_in():
    """El diagnóstico es puro: no importa el motor ni el replay durable."""
    import bolsa_application.dia_d_thesis_exit as module

    source = module.__file__ or ""
    assert "auto_simulation_worker" not in source
    assert "sim_durable_store" not in source
    assert "market_operability" not in source
