"""AUTO-19B — tests de la CALIBRACIÓN del intervalo y del WALK-FORWARD (``auto_adaptive_calibration``).

Lo que se prueba es la honestidad del instrumento, no que "el sistema funcione":

* que un informe **sin muestra** declare sus seis preguntas ``inconclusive`` (nunca un veredicto
  inventado);
* que el walk-forward use ventanas **CRECIENTES** y cronológicas (el IS nunca contiene el OOS);
* que cada pregunta de calibración **detecte** ``supported``/``not_supported`` cuando los números lo
  dicen y declare ``inconclusive`` cuando le falta muestra o el grupo de comparación;
* que los pliegues **reutilicen** la aritmética de celda y las tres preguntas de ``AUTO-19A`` (un solo
  productor de la comparación);
* que el instrumento sea determinista y **orden-invariante** sobre el fixture grabado, y que el
  fixture sintético se mida de punta a punta;
* que **no** se rompa ``AUTO-19A``: el ``ReplayReport`` del fixture de la fase anterior sigue igual.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from bolsa_analytics.cognitive.auto_adaptive_calibration import (
    CALIBRATION_EDGE_SIGN_FLOOR_DEFAULT,
    CALIBRATION_FOLDS_DEFAULT,
    CALIBRATION_METHOD,
    CALIBRATION_QUESTION_CONFIDENCE,
    CALIBRATION_QUESTION_COVERAGE,
    CALIBRATION_QUESTION_EDGE_SIGN,
    CALIBRATION_QUESTION_EFFECTIVE_N,
    CALIBRATION_QUESTION_INTERVAL_COVERAGE,
    CALIBRATION_QUESTION_SHRINKAGE,
    CalibrationFold,
    _aggregate,
    _calibration_questions,
    _question_confidence_band,
    _question_edge_sign,
    _question_interval_coverage,
    build_calibration_report,
    resolve_calibration_folds,
    split_walk_forward_folds,
)
from bolsa_analytics.cognitive.auto_adaptive_replay import (
    REPLAY_VERDICT_INCONCLUSIVE,
    REPLAY_VERDICT_NOT_SUPPORTED,
    REPLAY_VERDICT_SUPPORTED,
    ReplayCell,
    build_replay_report,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "auto_calibration_cycles.json"
_REPLAY_FIXTURE = Path(__file__).parent / "fixtures" / "auto_replay_cycles.json"

_ALLOWED_VERDICTS = {
    REPLAY_VERDICT_SUPPORTED,
    REPLAY_VERDICT_NOT_SUPPORTED,
    REPLAY_VERDICT_INCONCLUSIVE,
}


def _cell(
    version: str = "s",
    *,
    lower: float | None = None,
    upper: float | None = None,
    oos: float | None = 0.0,
    edge: str = "UNKNOWN",
    edge_sign_ok: bool | None = None,
    band: str = "MEDIUM",
    coverage: str = "MEDIUM",
    dispersion: float | None = 0.2,
    oos_n: int = 6,
    raw_error: float | None = None,
    shrunk_error: float | None = None,
    effective_n: int = 10,
    is_r: float | None = 1.0,
) -> ReplayCell:
    return ReplayCell(
        strategy_version=version,
        is_measured_n=10,
        is_episodes=10,
        is_effective_n=effective_n,
        is_expectancy_r=is_r,
        is_shrunk_expectancy_r=0.5,
        is_interval_lower=lower,
        is_interval_upper=upper,
        is_confidence=band,
        is_coverage=coverage,
        is_edge_confidence=edge,
        oos_measured_n=oos_n,
        oos_expectancy_r=oos,
        oos_dispersion_r=dispersion,
        oos_regime="TREND_UP",
        regime_coverage=coverage,
        raw_error=raw_error,
        shrunk_error=shrunk_error,
        raw_sign_ok=True,
        shrunk_sign_ok=True,
        edge_sign_ok=edge_sign_ok,
    )


def _cycles(version: str, count: int, *, pnl: float = 4.0) -> list[dict[str, object]]:
    base = date(2026, 1, 1)
    return [
        {
            "cycleId": f"{version}-{index}",
            "strategyVersion": version,
            "pnl": str(pnl),
            "riskAmount": "5",
            "marketRegime": "TREND_UP" if index % 2 else "RANGE",
            "closedAt": (base + timedelta(days=index)).isoformat() + "T15:30:00+00:00",
            "cost": {"total": 0.0, "measurement": "COMPLETE", "costModelVersion": "cm1"},
        }
        for index in range(count)
    ]


# ── Sin material no hay veredicto ───────────────────────────────────────────────────


def test_no_cycles_returns_six_declared_inconclusive_questions() -> None:
    report = build_calibration_report([])
    payload = report.as_dict()

    assert report.folds == ()
    assert report.cells == ()
    assert report.notes == ("no_cycles",)
    assert [row["question"] for row in payload["questions"]] == [
        CALIBRATION_QUESTION_INTERVAL_COVERAGE,
        CALIBRATION_QUESTION_EDGE_SIGN,
        CALIBRATION_QUESTION_CONFIDENCE,
        CALIBRATION_QUESTION_SHRINKAGE,
        CALIBRATION_QUESTION_EFFECTIVE_N,
        CALIBRATION_QUESTION_COVERAGE,
    ]
    assert all(row["verdict"] == REPLAY_VERDICT_INCONCLUSIVE for row in payload["questions"])
    assert all(row["sample"] == 0 for row in payload["questions"])
    assert payload["method"] == CALIBRATION_METHOD
    assert payload["foldsRequested"] == CALIBRATION_FOLDS_DEFAULT
    assert payload["aggregate"]["foldCount"] == 0


def test_the_folds_are_clamped_to_the_declared_range() -> None:
    assert resolve_calibration_folds(None) == CALIBRATION_FOLDS_DEFAULT
    assert resolve_calibration_folds(1) == 2, "un solo pliegue no es un walk-forward"
    assert resolve_calibration_folds(0) == 2
    assert resolve_calibration_folds(9) == 5


def test_a_strategy_without_enough_material_is_skipped_and_named() -> None:
    report = build_calibration_report(_cycles("thin", 6))

    assert report.folds == ()
    assert "skipped_strategy:thin" in report.notes


def test_material_for_fewer_folds_than_requested_is_declared() -> None:
    """30 ciclos y 5 pliegues pedidos: el walk-forward mide 4 y declara el hueco."""
    report = build_calibration_report(_cycles("orb-1", 30), folds=5)
    versions = {fold.cell.strategy_version for fold in report.folds}

    assert versions == {"orb-1"}
    assert len(report.folds) == 4
    assert "insufficient_folds:orb-1" in report.notes


# ── El walk-forward: ventanas crecientes y sin contaminación ────────────────────────


def test_the_walk_forward_windows_grow_and_never_overlap() -> None:
    rows = [{"i": index} for index in range(36)]
    folds = split_walk_forward_folds(rows, n_folds=3, min_is=8, min_oos=4)

    assert len(folds) == 3
    previous_train = 0
    for train, test in folds:
        assert len(train) >= 8 and len(test) >= 4
        assert len(train) > previous_train, "las ventanas son CRECIENTES"
        previous_train = len(train)
        # El tramo OOS es el segmento INMEDIATAMENTE posterior: el IS no lo contiene.
        assert [row["i"] for row in test] == list(
            range(len(train), len(train) + len(test))
        )
    # El último pliegue absorbe el resto de la serie.
    assert len(folds[-1][0]) + len(folds[-1][1]) == 36


def test_a_series_without_room_for_a_single_fold_returns_nothing() -> None:
    rows = [{"i": index} for index in range(9)]

    assert split_walk_forward_folds(rows, n_folds=3, min_is=8, min_oos=4) == ()


def test_the_split_is_chronological_not_by_arrival() -> None:
    cycles = _cycles("orb-1", 40, pnl=4.0)
    forward = build_calibration_report(cycles)
    backward = build_calibration_report(list(reversed(cycles)))

    assert [fold.as_dict() for fold in forward.folds] == [
        fold.as_dict() for fold in backward.folds
    ]
    assert len(forward.folds) == 3


# ── La calibración del intervalo: cobertura y ancho ─────────────────────────────────


def test_interval_coverage_is_measured_against_the_declared_level() -> None:
    covered = _question_interval_coverage(
        [_cell(lower=-1.0, upper=1.0, oos=0.2) for _ in range(2)],
        min_cells=2,
        level=0.90,
        tolerance=0.10,
    )
    assert covered.verdict == REPLAY_VERDICT_SUPPORTED
    assert covered.sample == 2
    assert covered.metrics["coverageRate"] == 1.0
    assert covered.metrics["expectedCoverage"] == 0.9
    assert covered.metrics["meanIntervalWidth"] == 2.0


def test_interval_coverage_refutes_a_too_narrow_interval() -> None:
    refuted = _question_interval_coverage(
        [_cell(lower=-1.0, upper=1.0, oos=5.0) for _ in range(2)],
        min_cells=2,
        level=0.90,
        tolerance=0.10,
    )

    assert refuted.verdict == REPLAY_VERDICT_NOT_SUPPORTED
    assert refuted.metrics["covered"] == 0
    assert refuted.metrics["coverageRate"] == 0.0


def test_without_an_interval_there_is_nothing_to_cover() -> None:
    thin = _question_interval_coverage(
        [_cell(lower=None, upper=None, oos=0.2) for _ in range(3)],
        min_cells=2,
        level=0.90,
        tolerance=0.10,
    )

    assert thin.verdict == REPLAY_VERDICT_INCONCLUSIVE
    assert thin.sample == 0
    assert thin.metrics["coverageRate"] is None
    assert thin.metrics["meanIntervalWidth"] is None


# ── El signo del EDGE y la banda de medición ────────────────────────────────────────


def test_edge_sign_calibration_measures_accuracy_against_the_floor() -> None:
    supported = _question_edge_sign(
        [
            _cell(edge="HIGH", edge_sign_ok=True),
            _cell(edge="LOW", edge_sign_ok=True),
        ],
        min_cells=2,
        floor=0.5,
    )
    refuted = _question_edge_sign(
        [
            _cell(edge="HIGH", edge_sign_ok=False),
            _cell(edge="LOW", edge_sign_ok=False),
        ],
        min_cells=2,
        floor=0.5,
    )

    assert supported.verdict == REPLAY_VERDICT_SUPPORTED
    assert supported.metrics["edgeSignAccuracy"] == 1.0
    assert supported.metrics["cellsHigh"] == 1
    assert supported.metrics["cellsLow"] == 1
    assert refuted.verdict == REPLAY_VERDICT_NOT_SUPPORTED
    assert refuted.metrics["edgeSignAccuracy"] == 0.0


def test_medium_and_unknown_edges_do_not_claim_a_sign() -> None:
    thin = _question_edge_sign(
        [
            _cell(edge="MEDIUM", edge_sign_ok=None),
            _cell(edge="UNKNOWN", edge_sign_ok=None),
        ],
        min_cells=2,
        floor=0.5,
    )

    assert thin.verdict == REPLAY_VERDICT_INCONCLUSIVE
    assert thin.sample == 0


def test_confidence_calibration_compares_oos_dispersion() -> None:
    supported = _question_confidence_band(
        [
            _cell(band="HIGH", dispersion=0.1),
            _cell(band="HIGH", dispersion=0.2),
            _cell(band="LOW", dispersion=0.5),
            _cell(band="LOW", dispersion=0.6),
        ],
        min_cells=2,
    )
    thin = _question_confidence_band(
        [_cell(band="HIGH", dispersion=0.1), _cell(band="LOW", dispersion=0.5)],
        min_cells=2,
    )

    assert supported.verdict == REPLAY_VERDICT_SUPPORTED
    assert supported.metrics["meanDispersionHigh"] == 0.15
    assert supported.metrics["meanDispersionLow"] == 0.55
    assert supported.metrics["bands"]["HIGH"]["n"] == 2
    assert thin.verdict == REPLAY_VERDICT_INCONCLUSIVE


def test_a_single_oos_cycle_is_not_stable_material_for_the_band() -> None:
    question = _question_confidence_band(
        [
            _cell(band="HIGH", dispersion=0.1, oos_n=1),
            _cell(band="HIGH", dispersion=0.2, oos_n=1),
            _cell(band="LOW", dispersion=0.5),
            _cell(band="LOW", dispersion=0.6),
        ],
        min_cells=2,
    )

    assert question.verdict == REPLAY_VERDICT_INCONCLUSIVE
    assert question.metrics["cellsHigh"] == 0


# ── Las tres preguntas de AUTO-19A se reutilizan con clave propia ───────────────────


def test_the_replay_questions_are_reused_under_calibration_keys() -> None:
    questions = _calibration_questions(
        [
            _cell(raw_error=0.1, shrunk_error=0.9),
            _cell(raw_error=0.2, shrunk_error=0.8),
        ],
        min_cells=2,
        level=0.90,
        tolerance=0.10,
        edge_sign_floor=CALIBRATION_EDGE_SIGN_FLOOR_DEFAULT,
    )
    by_key = {row.question: row for row in questions}

    assert set(by_key) == {
        CALIBRATION_QUESTION_INTERVAL_COVERAGE,
        CALIBRATION_QUESTION_EDGE_SIGN,
        CALIBRATION_QUESTION_CONFIDENCE,
        CALIBRATION_QUESTION_SHRINKAGE,
        CALIBRATION_QUESTION_EFFECTIVE_N,
        CALIBRATION_QUESTION_COVERAGE,
    }
    assert by_key[CALIBRATION_QUESTION_SHRINKAGE].verdict == REPLAY_VERDICT_NOT_SUPPORTED
    assert by_key[CALIBRATION_QUESTION_SHRINKAGE].sample == 2


# ── El fixture sintético: el instrumento se mide a sí mismo ─────────────────────────


def _fixture_cycles() -> list[dict[str, object]]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return payload["cycles"]


def test_the_synthetic_fixture_is_measured_end_to_end() -> None:
    report = build_calibration_report(_fixture_cycles())
    payload = report.as_dict()

    assert report.method == CALIBRATION_METHOD
    assert len(report.folds) == 9, "3 estrategias × 3 pliegues"
    assert "skipped_strategy:wf-thin" in report.notes
    assert {fold.cell.strategy_version for fold in report.folds} == {
        "wf-trend",
        "wf-range",
        "wf-chop",
    }
    assert [fold.index for fold in report.folds][:3] == [1, 2, 3]
    for row in payload["questions"]:
        assert row["verdict"] in _ALLOWED_VERDICTS
        if row["verdict"] != REPLAY_VERDICT_INCONCLUSIVE:
            assert row["sample"] >= 2, "nunca un veredicto sin muestra"
    coverage = report.question(CALIBRATION_QUESTION_INTERVAL_COVERAGE)
    assert coverage is not None and coverage.metrics["foldCountWithInterval"] >= 2
    assert payload["aggregate"]["foldCount"] == 9


def test_the_report_is_deterministic_and_order_invariant() -> None:
    cycles = _fixture_cycles()
    shuffled = list(cycles)
    random.Random(7).shuffle(shuffled)

    assert build_calibration_report(cycles).as_dict() == build_calibration_report(
        shuffled
    ).as_dict()


def test_the_report_payload_is_json_shaped() -> None:
    payload = build_calibration_report(_fixture_cycles()).as_dict()

    assert set(payload) == {
        "method",
        "foldsRequested",
        "level",
        "seed",
        "folds",
        "cells",
        "questions",
        "aggregate",
        "notes",
    }
    assert set(payload["folds"][0]) == {"index", "cell"}
    assert payload["cells"] == [fold["cell"] for fold in payload["folds"]]
    assert set(payload["aggregate"]) == {
        "foldCount",
        "isFoldCount",
        "oosFoldCount",
        "pairedFoldCount",
        "meanIsExpectancyR",
        "meanOosExpectancyR",
        "stdOosExpectancyR",
        "positiveOosFoldShare",
        "oosCv",
        "walkForwardEfficiency",
    }
    counts = payload["aggregate"]
    assert counts["foldCount"] == counts["oosFoldCount"] == counts["pairedFoldCount"] == 9, (
        "en el fixture todo pliegue tiene IS y OOS: los tres conteos coinciden"
    )


# ── AUTO-19A no se rompe ────────────────────────────────────────────────────────────


def test_the_auto19a_replay_fixture_is_unchanged() -> None:
    payload = json.loads(_REPLAY_FIXTURE.read_text(encoding="utf-8"))
    report = build_replay_report(payload["cycles"])

    assert len(report.cells) == 6
    assert "skipped_strategy:thin-edge" in report.notes


# ── AUTO-20 · cierre de O1: el material no medible se DECLARA ───────────────────────


def _without_risk(rows: list[dict[str, object]], indexes: range) -> list[dict[str, object]]:
    for index in indexes:
        rows[index].pop("riskAmount", None)
    return rows


def test_a_strategy_without_any_measurable_r_is_declared_not_silently_dropped() -> None:
    """O1: una estrategia cuyos ciclos NO tienen R medible desaparecía sin dejar rastro."""
    report = build_calibration_report(_without_risk(_cycles("ghost", 30), range(30)))

    assert report.folds == (), "sin R medible no hay pliegues"
    assert "unmeasured_r:ghost" in report.notes, "el hueco se nombra, no se silencia"


def test_a_partially_measured_strategy_is_not_flagged_as_unmeasured() -> None:
    """Solo se declara la versión SIN ninguna fila medible: el hueco parcial no es un hueco."""
    report = build_calibration_report(_without_risk(_cycles("mixed", 30), range(3)))

    assert not any(note.startswith("unmeasured_r:") for note in report.notes)
    assert report.folds, "las filas medidas siguen midiéndose"


def test_cycles_without_a_version_are_declared() -> None:
    rows = _cycles("orb-1", 30)
    rows.append({"cycleId": "anon-1", "pnl": "4", "riskAmount": "5"})
    report = build_calibration_report(rows)

    assert "unversioned_cycles" in report.notes


# ── AUTO-20 · cierre de O2: la ratio NO mezcla muestras distintas ───────────────────


def test_walk_forward_efficiency_is_computed_on_paired_folds_only() -> None:
    """O2: la ratio usaba la media OOS de unos pliegues con la media IS de otros."""
    folds = (
        CalibrationFold(index=1, cell=_cell(oos=2.0, is_r=1.0)),
        CalibrationFold(index=2, cell=_cell(oos=None, is_r=3.0)),
    )
    aggregate = _aggregate(folds)

    assert aggregate["foldCount"] == 2
    assert aggregate["oosFoldCount"] == 1
    assert aggregate["isFoldCount"] == 2
    assert aggregate["pairedFoldCount"] == 1
    assert aggregate["meanIsExpectancyR"] == 2.0, "la media IS publicada ve los dos pliegues"
    # Emparejado: OOS 2.0 / IS 1.0 = 2.0. Mezclando sería 2.0 / 2.0 = 1.0 — la ratio mentiría.
    assert aggregate["walkForwardEfficiency"] == 2.0


def test_the_walk_forward_efficiency_is_none_without_a_paired_fold() -> None:
    folds = (CalibrationFold(index=1, cell=_cell(oos=None, is_r=1.0)),)
    aggregate = _aggregate(folds)

    assert aggregate["pairedFoldCount"] == 0
    assert aggregate["walkForwardEfficiency"] is None
    assert aggregate["meanOosExpectancyR"] is None
