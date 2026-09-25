"""AUTO-19A — tests del motor de INCERTIDUMBRE y confianza de EDGE (``auto_adaptive_uncertainty``).

Lo que se prueba es la disciplina de medición, que es el punto entero del módulo:

* que el intervalo sea un **bootstrap por EPISODIOS** (rachas de régimen), no por ciclos sueltos:
  60 ciclos de una sola fase no son 60 observaciones independientes;
* que ``lower <= point <= upper`` SIEMPRE (el intervalo no puede contradecir su propio punto);
* que sin muestra suficiente **no haya intervalo** (``insufficient_episodes``) y el edge quede
  ``UNKNOWN`` —nunca un ``LOW`` por ausencia de medición—;
* que la banda de **EDGE** sea un eje PROPIO, derivado del signo del intervalo frente a cero y
  modulado por cobertura/deterioro/base, DISTINTO de la banda de medición;
* que el bootstrap sea determinista (semilla declarada) y **orden-invariante**;
* que las celdas ``strategy × regime`` se midan sobre las MISMAS rachas, no sobre un segundo
  material que pudiera divergir.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_BASIS_DATA_DEGRADED,
    ADAPTIVE_BASIS_UNKNOWN,
    ADAPTIVE_COVERAGE_HIGH,
    ADAPTIVE_DECAY_NONE,
    ADAPTIVE_DECAY_SEVERE,
    ADAPTIVE_DECAY_UNKNOWN,
    build_adaptive_confidence,
)
from bolsa_analytics.cognitive.auto_adaptive_uncertainty import (
    ADAPTIVE_EDGE_HIGH,
    ADAPTIVE_EDGE_LOW,
    ADAPTIVE_EDGE_MEDIUM,
    ADAPTIVE_EDGE_NOTE_BASIS_DEGRADED,
    ADAPTIVE_EDGE_NOTE_CROSSES_ZERO,
    ADAPTIVE_EDGE_NOTE_LOW_COVERAGE,
    ADAPTIVE_EDGE_NOTE_NEGATIVE,
    ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT,
    ADAPTIVE_EDGE_NOTE_SEVERE_DECAY,
    ADAPTIVE_EDGE_UNKNOWN,
    ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
    ADAPTIVE_UNCERTAINTY_INSUFFICIENT_EPISODES,
    ADAPTIVE_UNCERTAINTY_METHOD,
    ADAPTIVE_UNCERTAINTY_NO_CYCLES,
    ExpectancyInterval,
    _edge_confidence,
    build_adaptive_uncertainty,
    percentile,
)

_BASE = date(2026, 1, 1)


def _cycles(
    version: str,
    regimes: list[str],
    r_values: list[float],
) -> list[dict[str, object]]:
    """Ciclos medidos con instante real, régimen declarado y R (= ``pnl / 5``) exacto."""
    rows: list[dict[str, object]] = []
    for index, (regime, r_value) in enumerate(zip(regimes, r_values, strict=True)):
        rows.append(
            {
                "cycleId": f"{version}-{index}",
                "strategyVersion": version,
                "pnl": str(round(r_value * 5.0, 6)),
                "riskAmount": "5",
                "marketRegime": regime,
                "closedAt": (_BASE + timedelta(days=index)).isoformat() + "T15:30:00+00:00",
                "cost": {"total": 0.0, "measurement": "COMPLETE", "costModelVersion": "cm1"},
            }
        )
    return rows


def _interval(
    point: float | None,
    lower: float | None,
    upper: float | None,
    *,
    effective_n: int = 10,
) -> ExpectancyInterval:
    return ExpectancyInterval(
        point=point,
        lower=lower,
        upper=upper,
        level=0.90,
        method=ADAPTIVE_UNCERTAINTY_METHOD,
        effective_n=effective_n,
        episodes=effective_n,
        measured_n=effective_n,
        resamples=100,
    )


# ── Bootstrap por EPISODIOS ─────────────────────────────────────────────────────────


def test_no_cycles_publishes_a_declared_empty_reading() -> None:
    reading = build_adaptive_uncertainty([])

    assert reading.available is False
    assert reading.by_strategy == ()
    assert reading.notes == (ADAPTIVE_UNCERTAINTY_NO_CYCLES,)
    assert reading.as_dict()["byStrategy"] == {}


def test_one_single_regime_phase_does_not_fabricate_an_interval() -> None:
    """6 ciclos de UNA fase de mercado son 1 observación: hay punto, no hay percentil honesto."""
    cycles = _cycles("orb-1", ["TREND_UP"] * 6, [1.0] * 6)
    reading = build_adaptive_uncertainty(cycles)
    row = reading.uncertainty_for("orb-1")

    assert row is not None
    assert row.interval.point == pytest.approx(1.0)
    assert row.interval.lower is None and row.interval.upper is None
    assert row.interval.episodes == 1
    assert ADAPTIVE_UNCERTAINTY_INSUFFICIENT_EPISODES in row.interval.notes
    assert row.edge_confidence == ADAPTIVE_EDGE_UNKNOWN, "sin medición no se afirma edge"
    assert ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT in row.notes


def test_many_episodes_publish_a_positive_interval_and_a_high_edge() -> None:
    """60 rachas independientes de R positivo: el intervalo entero es positivo ⇒ edge ``HIGH``."""
    regimes = ["TREND_UP", "RANGE"] * 30
    cycles = _cycles("orb-1", regimes, [1.0] * 60)
    reading = build_adaptive_uncertainty(cycles, resamples=500, seed=7)
    row = reading.uncertainty_for("orb-1")

    assert row is not None
    assert row.interval.effective_n == 60
    assert row.interval.measured_n == 60
    assert row.interval.lower is not None and row.interval.upper is not None
    assert row.interval.lower <= row.interval.point <= row.interval.upper
    assert row.interval.lower > 0.0
    assert row.interval.dispersion_r == pytest.approx(0.0)
    assert row.coverage == ADAPTIVE_COVERAGE_HIGH
    assert row.edge_confidence == ADAPTIVE_EDGE_HIGH
    assert reading.as_dict()["method"] == ADAPTIVE_UNCERTAINTY_METHOD
    assert reading.as_dict()["seed"] == 7


def test_the_bootstrap_is_reproducible_and_order_invariant() -> None:
    regimes = ["TREND_UP", "RANGE"] * 15
    values = [1.0, -0.4, 0.6, 0.9, -0.2] * 6
    cycles = _cycles("orb-1", regimes, values)

    first = build_adaptive_uncertainty(cycles, resamples=400, seed=11)
    second = build_adaptive_uncertainty(list(reversed(cycles)), resamples=400, seed=11)
    different_seed = build_adaptive_uncertainty(cycles, resamples=400, seed=99)

    assert first.as_dict() == second.as_dict(), "el orden de llegada no puede cambiar la lectura"
    assert first.as_dict() != different_seed.as_dict(), "la semilla declarada sí cambia el azar"


def test_the_interval_always_contains_its_point_even_with_a_wild_sample() -> None:
    """El punto publicado se ensancha si hiciera falta: un intervalo no puede contradecirlo."""
    regimes = ["TREND_UP", "RANGE", "HIGH_VOL"] * 5
    values = [10.0, -8.0, 0.5] * 5
    cycles = _cycles("orb-1", regimes, values)
    reading = build_adaptive_uncertainty(cycles, resamples=600, seed=3)
    row = reading.uncertainty_for("orb-1")

    assert row is not None
    assert row.interval.lower is not None and row.interval.upper is not None
    assert row.interval.lower <= row.interval.point <= row.interval.upper


def test_the_cells_are_measured_over_the_same_episodes_as_the_strategy() -> None:
    regimes = ["TREND_UP", "RANGE"] * 20
    cycles = _cycles("orb-1", regimes, [1.0, 0.5] * 20)
    confidence = build_adaptive_confidence(cycles)
    reading = build_adaptive_uncertainty(cycles, confidence=confidence, resamples=300, seed=5)
    row = reading.uncertainty_for("orb-1")

    assert row is not None
    declared = [cell.regime for cell in confidence.confidence_for("orb-1").by_regime]
    assert set(declared) == {"TREND_UP", "RANGE"}
    assert [cell.regime for cell in row.by_regime] == declared, "las celdas heredan el orden del cruce"
    assert all(cell.interval.episodes == 20 for cell in row.by_regime)


def test_undated_cycles_are_declared_and_still_measured() -> None:
    cycles = _cycles("orb-1", ["TREND_UP", "RANGE"] * 6, [1.0, 0.5] * 6)
    for row in cycles:
        row.pop("closedAt", None)

    reading = build_adaptive_uncertainty(cycles, resamples=200, seed=1)

    assert "undated_cycles" in reading.notes
    assert reading.available is True


def test_the_reading_is_a_json_shaped_payload() -> None:
    cycles = _cycles("orb-1", ["TREND_UP", "RANGE"] * 4, [1.0, 0.5] * 4)
    payload = build_adaptive_uncertainty(cycles, resamples=100, seed=2).as_dict()

    assert set(payload) == {"method", "level", "resamples", "seed", "available", "byStrategy", "notes"}
    row = payload["byStrategy"]["orb-1"]
    assert set(row) == {
        "strategyVersion",
        "expectancyInterval",
        "edgeConfidence",
        "coverage",
        "byRegime",
        "notes",
    }
    assert set(row["expectancyInterval"]) == {
        "point",
        "lower",
        "upper",
        "level",
        "method",
        "effectiveN",
        "episodes",
        "measuredN",
        "resamples",
        "dispersionR",
        "probabilityPositive",
        "notes",
    }


def test_probability_positive_is_the_share_of_positive_bootstrap_means() -> None:
    """AUTO-21: P(R>0) es la fracción de medias bootstrap > 0, con el mismo material que el intervalo."""
    regimes = ["TREND_UP", "RANGE"] * 10
    values = [-1.0, -2.0] * 10
    cycles = _cycles("orb-1", regimes, values)
    reading = build_adaptive_uncertainty(cycles, resamples=400, seed=5)
    row = reading.uncertainty_for("orb-1")

    assert row is not None
    assert row.interval.probability_positive == 0.0, "ninguna media bootstrap supera cero"
    assert row.interval.as_dict()["probabilityPositive"] == 0.0


def test_probability_positive_is_none_without_a_bootstrap() -> None:
    """Sin rachas suficientes no hay bootstrap: la probabilidad se declara ``None``, no un 0 falso."""
    cycles = _cycles("orb-1", ["TREND_UP"] * 6, [1.0] * 6)
    reading = build_adaptive_uncertainty(cycles)

    row = reading.uncertainty_for("orb-1")
    assert row is not None
    assert row.interval.probability_positive is None


def test_a_fully_positive_sample_declares_probability_one() -> None:
    regimes = ["TREND_UP", "RANGE"] * 15
    cycles = _cycles("orb-1", regimes, [0.5] * 30)
    reading = build_adaptive_uncertainty(cycles, resamples=300, seed=3)

    row = reading.uncertainty_for("orb-1")
    assert row is not None
    assert row.interval.probability_positive == 1.0


# ── La banda de EDGE: un eje PROPIO, derivado del intervalo ─────────────────────────


def test_an_interval_fully_above_zero_is_a_high_edge() -> None:
    edge, notes = _edge_confidence(
        _interval(0.5, 0.2, 0.9),
        coverage=ADAPTIVE_COVERAGE_HIGH,
        decay=ADAPTIVE_DECAY_NONE,
        basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_HIGH
    assert notes == ()


def test_a_positive_point_that_crosses_zero_is_only_a_medium_edge() -> None:
    edge, notes = _edge_confidence(
        _interval(0.4, -0.2, 0.9),
        coverage=ADAPTIVE_COVERAGE_HIGH,
        decay=ADAPTIVE_DECAY_NONE,
        basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_MEDIUM
    assert ADAPTIVE_EDGE_NOTE_CROSSES_ZERO in notes


def test_a_non_positive_point_is_a_low_edge() -> None:
    edge, notes = _edge_confidence(
        _interval(-0.3, -0.8, 0.2),
        coverage=ADAPTIVE_COVERAGE_HIGH,
        decay=ADAPTIVE_DECAY_NONE,
        basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_LOW
    assert ADAPTIVE_EDGE_NOTE_NEGATIVE in notes


def test_no_measurement_is_unknown_not_low() -> None:
    edge, notes = _edge_confidence(
        _interval(None, None, None),
        coverage=ADAPTIVE_COVERAGE_HIGH,
        decay=ADAPTIVE_DECAY_NONE,
        basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_UNKNOWN
    assert ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT in notes


def test_too_few_episodes_are_unknown_even_with_a_point() -> None:
    edge, notes = _edge_confidence(
        _interval(0.9, None, None, effective_n=1),
        coverage=ADAPTIVE_COVERAGE_HIGH,
        decay=ADAPTIVE_DECAY_NONE,
        basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        min_episodes=ADAPTIVE_INTERVAL_MIN_EPISODES_DEFAULT,
    )

    assert edge == ADAPTIVE_EDGE_UNKNOWN
    assert ADAPTIVE_EDGE_NOTE_NO_MEASUREMENT in notes


def test_low_coverage_lowers_the_edge_one_step_and_declares_it() -> None:
    edge, notes = _edge_confidence(
        _interval(0.5, 0.2, 0.9),
        coverage="LOW",
        decay=ADAPTIVE_DECAY_NONE,
        basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_MEDIUM
    assert ADAPTIVE_EDGE_NOTE_LOW_COVERAGE in notes


def test_severe_decay_and_a_degraded_basis_each_lower_the_edge() -> None:
    edge, notes = _edge_confidence(
        _interval(0.5, 0.2, 0.9),
        coverage=ADAPTIVE_COVERAGE_HIGH,
        decay=ADAPTIVE_DECAY_SEVERE,
        basis_transition=ADAPTIVE_BASIS_DATA_DEGRADED,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_LOW, "dos degradaciones desde HIGH con suelo LOW"
    assert ADAPTIVE_EDGE_NOTE_SEVERE_DECAY in notes
    assert ADAPTIVE_EDGE_NOTE_BASIS_DEGRADED in notes


def test_the_edge_never_degenerates_below_low_while_there_is_measurement() -> None:
    edge, _notes = _edge_confidence(
        _interval(0.5, 0.2, 0.9),
        coverage="LOW",
        decay=ADAPTIVE_DECAY_SEVERE,
        basis_transition=ADAPTIVE_BASIS_DATA_DEGRADED,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_LOW, "con medición, el suelo es LOW; UNKNOWN es solo no-medición"


def test_an_unknown_decay_does_not_lower_the_edge() -> None:
    """``UNKNOWN`` no es deterioro: es no haber podido comparar, y no se castiga."""
    edge, notes = _edge_confidence(
        _interval(0.5, 0.2, 0.9),
        coverage=ADAPTIVE_COVERAGE_HIGH,
        decay=ADAPTIVE_DECAY_UNKNOWN,
        basis_transition=ADAPTIVE_BASIS_UNKNOWN,
        min_episodes=2,
    )

    assert edge == ADAPTIVE_EDGE_HIGH
    assert notes == ()


# ── Utilidades declaradas ───────────────────────────────────────────────────────────


def test_percentile_interpolates_and_declares_the_empty_case() -> None:
    assert percentile([], 0.5) is None
    assert percentile([3.0], 0.9) == pytest.approx(3.0)
    assert percentile([0.0, 10.0], 0.5) == pytest.approx(5.0)
    assert percentile([0.0, 10.0], 0.0) == pytest.approx(0.0)
    assert percentile([0.0, 10.0], 1.0) == pytest.approx(10.0)


def test_the_level_and_resamples_are_clamped_and_declared() -> None:
    cycles = _cycles("orb-1", ["TREND_UP", "RANGE"] * 3, [1.0, 0.5] * 3)

    high = build_adaptive_uncertainty(cycles, level=5.0, resamples=0, seed=1)
    low = build_adaptive_uncertainty(cycles, level=-1.0, resamples=1, seed=1)

    assert high.level == 0.99 and high.resamples == 1
    assert low.level == 0.5 and low.resamples == 1


def test_a_shuffled_input_without_instants_is_not_promised_as_order_invariant() -> None:
    """Sin fechas legibles no hay orden: solo se promete lo que el material sostiene."""
    cycles = _cycles("orb-1", ["TREND_UP", "RANGE"] * 4, [1.0, 0.5] * 4)
    for row in cycles:
        row.pop("closedAt", None)
    shuffled = list(cycles)
    random.Random(2).shuffle(shuffled)

    reading = build_adaptive_uncertainty(shuffled, resamples=100, seed=1)

    assert reading.available is True
