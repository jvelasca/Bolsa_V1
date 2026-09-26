"""AUTO-19A — tests de la BATERÍA de replay OOS estadístico (``auto_adaptive_replay``).

Lo que se prueba es la honestidad del instrumento, no que "el sistema funciona":

* que una pregunta **sin muestra** se declare ``inconclusive`` (nunca un veredicto inventado);
* que cada una de las cuatro preguntas **detecte** correctamente ``supported`` y
  ``not_supported`` cuando los números lo dicen;
* que la partición IS/OOS sea **cronológica** y con los mínimos declarados (una estrategia sin
  material no entra; su hueco se nombra);
* que el instrumento sea determinista y **orden-invariante** sobre el fixture grabado;
* que el fixture sintético se mida de punta a punta (es un auto-test del instrumento, no una
  validación de la estrategia real).
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import pytest

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_COVERAGE_HIGH,
    StrategyConfidence,
)
from bolsa_analytics.cognitive.auto_adaptive_replay import (
    REPLAY_METHOD,
    REPLAY_OOS_PCT_MAX,
    REPLAY_OOS_PCT_MIN,
    REPLAY_QUESTION_CONFIDENCE,
    REPLAY_QUESTION_COVERAGE,
    REPLAY_QUESTION_EFFECTIVE_N,
    REPLAY_QUESTION_SHRINKAGE,
    REPLAY_VERDICT_INCONCLUSIVE,
    REPLAY_VERDICT_NOT_SUPPORTED,
    REPLAY_VERDICT_SUPPORTED,
    ReplayCell,
    _question_confidence,
    _question_coverage,
    _question_effective_n,
    _question_shrinkage,
    build_replay_report,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (
    ADAPTIVE_INTERVAL_LEVEL_MIN,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "auto_replay_cycles.json"


def _cell(
    version: str = "s",
    *,
    raw_error: float | None = 0.5,
    shrunk_error: float | None = 0.4,
    effective_n: int = 10,
    band: str = "MEDIUM",
    coverage: str | None = "MEDIUM",
    edge: str = "MEDIUM",
    dispersion: float | None = 0.2,
    oos_measured_n: int = 6,
) -> ReplayCell:
    return ReplayCell(
        strategy_version=version,
        is_measured_n=10,
        is_episodes=10,
        is_effective_n=effective_n,
        is_expectancy_r=1.0,
        is_shrunk_expectancy_r=0.5,
        is_interval_lower=0.0,
        is_interval_upper=1.0,
        is_confidence=band,
        is_coverage=coverage,
        is_edge_confidence=edge,
        oos_measured_n=oos_measured_n,
        oos_expectancy_r=0.0,
        oos_dispersion_r=dispersion,
        oos_regime="TREND_UP",
        dominant_regime_coverage=coverage,
        raw_error=raw_error,
        shrunk_error=shrunk_error,
        raw_sign_ok=True,
        shrunk_sign_ok=True,
        edge_sign_ok=None,
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


def test_no_cycles_returns_four_declared_inconclusive_questions() -> None:
    report = build_replay_report([])
    payload = report.as_dict()

    assert report.cells == ()
    assert report.notes == ("no_cycles",)
    assert [row["question"] for row in payload["questions"]] == [
        REPLAY_QUESTION_SHRINKAGE,
        REPLAY_QUESTION_EFFECTIVE_N,
        REPLAY_QUESTION_CONFIDENCE,
        REPLAY_QUESTION_COVERAGE,
    ]
    assert all(row["verdict"] == REPLAY_VERDICT_INCONCLUSIVE for row in payload["questions"])
    assert all(row["sample"] == 0 for row in payload["questions"])
    assert payload["method"] == REPLAY_METHOD
    assert payload["shrinkPrior"] == 20.0


def test_a_strategy_without_enough_material_is_skipped_and_named() -> None:
    report = build_replay_report(_cycles("thin-edge", 6))

    assert report.cells == ()
    assert "skipped_strategy:thin-edge" in report.notes


def test_the_oos_fraction_is_clamped_and_declared() -> None:
    cycles = _cycles("orb-1", 40)

    high = build_replay_report(cycles, oos_pct=5.0)
    low = build_replay_report(cycles, oos_pct=-1.0)

    assert high.oos_pct == REPLAY_OOS_PCT_MAX
    assert low.oos_pct == REPLAY_OOS_PCT_MIN


# ── Cada pregunta detecta soporta / refuta / inconcluso ─────────────────────────────


def test_the_shrinkage_question_compares_the_error_means() -> None:
    supported = _question_shrinkage(
        [_cell(raw_error=1.0, shrunk_error=0.5) for _ in range(3)], 2
    )
    refuted = _question_shrinkage(
        [_cell(raw_error=0.5, shrunk_error=1.0) for _ in range(3)], 2
    )
    thin = _question_shrinkage([_cell()], 2)

    assert supported.verdict == REPLAY_VERDICT_SUPPORTED
    assert supported.sample == 3
    assert supported.metrics["meanShrunkError"] < supported.metrics["meanRawError"]
    assert refuted.verdict == REPLAY_VERDICT_NOT_SUPPORTED
    assert thin.verdict == REPLAY_VERDICT_INCONCLUSIVE
    assert thin.sample == 1


def test_the_effective_n_question_splits_by_the_median() -> None:
    supported = _question_effective_n(
        [
            _cell(effective_n=4, raw_error=1.0),
            _cell(effective_n=5, raw_error=0.8),
            _cell(effective_n=10, raw_error=0.9),
            _cell(effective_n=20, raw_error=0.1),
            _cell(effective_n=30, raw_error=0.2),
        ],
        2,
    )
    refuted = _question_effective_n(
        [
            _cell(effective_n=4, raw_error=0.1),
            _cell(effective_n=5, raw_error=0.2),
            _cell(effective_n=10, raw_error=0.3),
            _cell(effective_n=20, raw_error=1.0),
            _cell(effective_n=30, raw_error=0.9),
        ],
        2,
    )
    thin = _question_effective_n([_cell(effective_n=4), _cell(effective_n=30)], 2)

    assert supported.verdict == REPLAY_VERDICT_SUPPORTED
    assert supported.metrics["medianEffectiveN"] == 10
    assert refuted.verdict == REPLAY_VERDICT_NOT_SUPPORTED
    assert thin.verdict == REPLAY_VERDICT_INCONCLUSIVE


def test_the_confidence_question_compares_oos_dispersion() -> None:
    supported = _question_confidence(
        [
            _cell(band="HIGH", dispersion=0.1),
            _cell(band="HIGH", dispersion=0.2),
            _cell(band="LOW", dispersion=0.5),
            _cell(band="LOW", dispersion=0.6),
        ],
        2,
    )
    refuted = _question_confidence(
        [
            _cell(band="HIGH", dispersion=0.7),
            _cell(band="HIGH", dispersion=0.8),
            _cell(band="LOW", dispersion=0.1),
            _cell(band="LOW", dispersion=0.2),
        ],
        2,
    )
    thin = _question_confidence([_cell(band="HIGH"), _cell(band="LOW")], 2)

    assert supported.verdict == REPLAY_VERDICT_SUPPORTED
    assert supported.metrics["meanDispersionHigh"] < supported.metrics["meanDispersionLow"]
    assert refuted.verdict == REPLAY_VERDICT_NOT_SUPPORTED
    assert thin.verdict == REPLAY_VERDICT_INCONCLUSIVE


def test_a_single_oos_cycle_is_not_counted_as_stable_material() -> None:
    """Una celda con 1 ciclo OOS no prueba estabilidad: se excluye y la pregunta se declara."""
    question = _question_confidence(
        [
            _cell(band="HIGH", dispersion=0.1, oos_measured_n=1),
            _cell(band="HIGH", dispersion=0.2, oos_measured_n=1),
            _cell(band="LOW", dispersion=0.5),
            _cell(band="LOW", dispersion=0.6),
        ],
        2,
    )

    assert question.verdict == REPLAY_VERDICT_INCONCLUSIVE
    assert question.metrics["cellsHigh"] == 0


def test_the_coverage_question_compares_the_covered_regime() -> None:
    supported = _question_coverage(
        [
            _cell(coverage="HIGH", raw_error=0.1),
            _cell(coverage="HIGH", raw_error=0.2),
            _cell(coverage="LOW", raw_error=0.9),
            _cell(coverage="UNCOVERED", raw_error=0.8),
        ],
        2,
    )
    refuted = _question_coverage(
        [
            _cell(coverage="HIGH", raw_error=0.9),
            _cell(coverage="HIGH", raw_error=0.8),
            _cell(coverage="LOW", raw_error=0.1),
            _cell(coverage="LOW", raw_error=0.2),
        ],
        2,
    )
    thin = _question_coverage([_cell(coverage="HIGH"), _cell(coverage="LOW")], 2)

    assert supported.verdict == REPLAY_VERDICT_SUPPORTED
    assert supported.metrics["cellsCovered"] == 2
    assert refuted.verdict == REPLAY_VERDICT_NOT_SUPPORTED
    assert thin.verdict == REPLAY_VERDICT_INCONCLUSIVE


def test_the_cell_payload_is_json_shaped_and_rounded() -> None:
    payload = _cell(raw_error=0.123456, shrunk_error=0.2).as_dict()

    assert payload["rawError"] == 0.1235
    assert set(payload) == {
        "strategyVersion",
        "isMeasuredN",
        "isEpisodes",
        "isEffectiveN",
        "isExpectancyR",
        "isShrunkExpectancyR",
        "isIntervalLower",
        "isIntervalUpper",
        "isConfidence",
        "isCoverage",
        "isEdgeConfidence",
        "isEdgePositiveProbability",
        "isCyclePositiveShare",
        "oosMeasuredN",
        "oosExpectancyR",
        "oosDispersionR",
        "oosRegime",
        "dominantRegimeCoverage",
        "oosPositiveN",
        "oosPositiveShare",
        "rawError",
        "shrunkError",
        "rawSignOk",
        "shrunkSignOk",
        "edgeSignOk",
        "notes",
    }


# ── El fixture sintético: el instrumento se mide a sí mismo ─────────────────────────


def _fixture_cycles() -> list[dict[str, object]]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return payload["cycles"]


def test_the_synthetic_fixture_is_measured_end_to_end() -> None:
    report = build_replay_report(_fixture_cycles())
    payload = report.as_dict()

    assert len(report.cells) == 6, "7 estrategias, una sin material ⇒ 6 celdas"
    assert "skipped_strategy:thin-edge" in report.notes
    assert payload["method"] == REPLAY_METHOD
    assert {row["strategyVersion"] for row in payload["cells"]} == {
        "brk-fade",
        "brk-scalp",
        "mr-mean",
        "mr-vol",
        "orb-range",
        "orb-trend",
    }
    for row in payload["questions"]:
        assert row["verdict"] in {
            REPLAY_VERDICT_SUPPORTED,
            REPLAY_VERDICT_NOT_SUPPORTED,
            REPLAY_VERDICT_INCONCLUSIVE,
        }
        if row["verdict"] != REPLAY_VERDICT_INCONCLUSIVE:
            assert row["sample"] >= 2, "nunca un veredicto sin muestra"


def test_the_report_is_deterministic_and_order_invariant() -> None:
    cycles = _fixture_cycles()
    shuffled = list(cycles)
    random.Random(4).shuffle(shuffled)

    assert build_replay_report(cycles).as_dict() == build_replay_report(shuffled).as_dict()


def test_the_in_sample_is_the_old_tramo_and_the_out_of_sample_the_recent_one() -> None:
    """El split es CRONOLÓGICO: si el tramo viejo gana y el reciente pierde, el OOS lo delata."""
    base = date(2026, 1, 1)
    cycles = [
        {
            "cycleId": f"orb-1-{index}",
            "strategyVersion": "orb-1",
            "pnl": "5" if index < 21 else "-5",
            "riskAmount": "5",
            "marketRegime": "TREND_UP",
            "closedAt": (base + timedelta(days=index)).isoformat() + "T15:30:00+00:00",
            "cost": {"total": 0.0, "measurement": "COMPLETE", "costModelVersion": "cm1"},
        }
        for index in range(30)
    ]

    cell = build_replay_report(cycles, oos_pct=0.30).cells[0]

    assert cell.oos_measured_n == 9, "el 30 % del tramo final es el OOS"
    assert cell.oos_expectancy_r == pytest.approx(-1.0), "el OOS es la parte RECIENTE"
    assert cell.is_expectancy_r == pytest.approx(1.0), "el IS es la parte VIEJA"


def test_the_split_is_chronological_not_by_arrival() -> None:
    """Invertir la entrada no cambia la partición: el IS es el tramo VIEJO y el OOS el nuevo."""
    cycles = _cycles("orb-1", 40, pnl=4.0)
    forward = build_replay_report(cycles)
    backward = build_replay_report(list(reversed(cycles)))

    assert [cell.as_dict() for cell in forward.cells] == [
        cell.as_dict() for cell in backward.cells
    ]
    assert forward.cells[0].oos_measured_n > 0
    assert forward.cells[0].raw_error is not None


def test_a_cycle_without_an_instant_is_declared() -> None:
    cycles = _cycles("orb-1", 40)
    for row in cycles[:3]:
        row.pop("closedAt", None)

    report = build_replay_report(cycles)

    assert "undated_cycles" in report.notes


def test_the_cell_publishes_the_declared_and_realized_positive_probabilities() -> None:
    """La celda lleva la ``P(R>0)`` declarada del IS y la frecuencia positiva REALIZADA del OOS."""
    cycles = _cycles("orb-1", 40, pnl=4.0)  # R = 0.8 en TODOS los ciclos
    cell = build_replay_report(cycles).cells[0]

    assert cell.is_cycle_positive_share == 1.0
    assert cell.is_edge_positive_probability == 1.0
    assert cell.oos_positive_share == 1.0
    assert cell.oos_positive_n == cell.oos_measured_n
    assert cell.as_dict()["isCyclePositiveShare"] == 1.0
    assert cell.as_dict()["isEdgePositiveProbability"] == 1.0
    assert cell.as_dict()["oosPositiveShare"] == 1.0


def test_a_mixed_oos_declares_its_realized_positive_share() -> None:
    """La fracción positiva contada es sobre los ciclos OOS MEDIDOS, no sobre el total."""
    cycles = _cycles("orb-1", 40, pnl=4.0)
    for index in range(28, 40):  # los 12 ciclos del tramo OOS (30 %) cierran en negativo
        cycles[index]["pnl"] = "-4.0"
    cell = build_replay_report(cycles).cells[0]

    assert cell.oos_measured_n == 12
    assert cell.oos_positive_n == 0
    assert cell.oos_positive_share == 0.0
    assert cell.is_cycle_positive_share == 1.0, "el IS sigue siendo todo positivo"
    assert cell.is_edge_positive_probability == 1.0


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_the_interval_level_is_clamped_and_published(bad: float) -> None:
    """El nivel publicado es el EFECTIVO (clampeado), el mismo que usó el bootstrap."""
    report = build_replay_report(_cycles("orb-1", 40), interval_level=bad)

    assert report.interval_level == ADAPTIVE_INTERVAL_LEVEL_MIN
    assert len(report.questions) == 4


def test_a_cell_without_a_measured_regime_coverage_is_declared_not_counted_as_uncovered() -> None:
    """Cobertura NO MEDIDA (sin celda del régimen dominante) no es evidencia de no cobertura."""
    question = _question_coverage(
        [
            _cell(coverage="HIGH", raw_error=0.1),
            _cell(coverage="HIGH", raw_error=0.2),
            _cell(coverage=None, raw_error=0.9),
            _cell(coverage=None, raw_error=0.8),
        ],
        2,
    )

    assert question.verdict == REPLAY_VERDICT_INCONCLUSIVE
    assert question.metrics["cellsUnmeasured"] == 2
    assert question.metrics["cellsUncovered"] == 0


def test_the_regime_coverage_key_is_a_float_in_confidence_and_a_band_in_replay() -> None:
    """H4: ``regimeCoverage`` (float de ``StrategyConfidence``) y ``dominantRegimeCoverage`` (banda
    de ``ReplayCell``) son claves DISTINTAS: el mismo nombre no puede tener dos formas."""
    confidence = StrategyConfidence(
        strategy_version="orb-1",
        sample_size=10,
        effective_n=5,
        measurement_completeness="COMPLETE",
        risk_coverage=1.0,
        cost_coverage=1.0,
        regime_coverage=0.6,
        long_expectancy_r=0.4,
        recent_expectancy_r=0.3,
        decay="NONE",
        confidence="HIGH",
        by_regime=(),
        notes=(),
    )
    assert confidence.as_dict()["regimeCoverage"] == 0.6
    cell = _cell(coverage=ADAPTIVE_COVERAGE_HIGH)
    assert "regimeCoverage" not in cell.as_dict()
    assert cell.as_dict()["dominantRegimeCoverage"] == ADAPTIVE_COVERAGE_HIGH
