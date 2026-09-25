"""AUTO-21 — tests de la EVIDENCIA del régimen actual (``auto_adaptive_regime_evidence``).

Lo que se prueba es que la lectura reutilice el bootstrap de ``AUTO-19A`` (mismo material, misma
``P(R > 0)``), que seleccione bien el régimen actual (explícito > más reciente > ``NO MEDIDO``) y que
una estrategia sin celda para ese régimen lo DECLARE en vez de heredar otra lectura.
"""

from __future__ import annotations

from datetime import date, timedelta

from bolsa_analytics.cognitive.auto_adaptive import ADAPTIVE_ADVERSE_REGIMES
from bolsa_analytics.cognitive.auto_adaptive_regime_evidence import (
    CURRENT_REGIME_EVIDENCE_METHOD,
    REGIME_EVIDENCE_NOTE_NO_CURRENT_REGIME,
    REGIME_EVIDENCE_NOTE_NO_CYCLES,
    REGIME_EVIDENCE_NOTE_NO_EVIDENCE_FOR_REGIME,
    build_current_regime_evidence,
    current_regime_from_cycles,
)

_BASE = date(2026, 1, 1)


def _cycles(
    version: str, regimes: list[str], r_values: list[float]
) -> list[dict[str, object]]:
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


def test_without_cycles_the_reading_is_declared_empty() -> None:
    evidence = build_current_regime_evidence([])

    assert evidence.regime is None
    assert evidence.adverse is None
    assert evidence.by_strategy == ()
    assert evidence.notes == (REGIME_EVIDENCE_NOTE_NO_CYCLES,)
    assert evidence.method == CURRENT_REGIME_EVIDENCE_METHOD


def test_the_current_regime_is_the_latest_with_a_declarable_regime() -> None:
    cycles = _cycles("orb-1", ["TREND_UP", "HIGH_VOL"] * 10, [0.5] * 20)

    assert current_regime_from_cycles(cycles) == "HIGH_VOL"
    evidence = build_current_regime_evidence(cycles, resamples=200, seed=3)

    assert evidence.regime == "HIGH_VOL"
    assert evidence.adverse is ("HIGH_VOL" in ADAPTIVE_ADVERSE_REGIMES)
    assert evidence.adverse is True


def test_an_explicit_regime_wins_over_the_latest() -> None:
    cycles = _cycles("orb-1", ["TREND_UP", "HIGH_VOL"] * 10, [0.5] * 20)

    evidence = build_current_regime_evidence(
        cycles, current_regime="TREND_UP", resamples=200, seed=3
    )

    assert evidence.regime == "TREND_UP"
    assert evidence.adverse is False


def test_the_regime_cell_reuses_the_bootstrap_and_publishes_probability_positive() -> None:
    cycles = _cycles("orb-1", ["TREND_UP", "HIGH_VOL"] * 10, [1.0, -1.0] * 10)
    evidence = build_current_regime_evidence(cycles, resamples=300, seed=7)

    row = evidence.evidence_for("orb-1")
    assert row is not None
    assert row.regime == "HIGH_VOL"
    assert row.measured_n == 10, "solo los ciclos de ESE régimen entran en su celda"
    assert row.episodes == 10
    assert row.probability_positive is not None
    assert row.expectancy_r is not None


def test_a_strategy_without_a_cell_for_the_regime_declares_the_gap() -> None:
    cycles = _cycles("orb-1", ["TREND_UP", "HIGH_VOL"] * 10, [1.0, -1.0] * 10)

    evidence = build_current_regime_evidence(
        cycles, current_regime="RANGE", resamples=200, seed=1
    )
    row = evidence.evidence_for("orb-1")

    assert row is not None
    assert row.measured_n == 0
    assert row.expectancy_r is None
    assert row.probability_positive is None
    assert row.edge_confidence == "UNKNOWN"
    assert row.notes == (REGIME_EVIDENCE_NOTE_NO_EVIDENCE_FOR_REGIME,)


def test_an_unknown_regime_is_not_a_current_regime() -> None:
    cycles = _cycles("orb-1", ["unknown"] * 8, [1.0] * 8)

    assert current_regime_from_cycles(cycles) is None
    evidence = build_current_regime_evidence(cycles, resamples=200, seed=1)

    assert evidence.regime is None
    assert REGIME_EVIDENCE_NOTE_NO_CURRENT_REGIME in evidence.notes
    assert evidence.as_dict()["byStrategy"]["orb-1"]["notes"] == [
        REGIME_EVIDENCE_NOTE_NO_EVIDENCE_FOR_REGIME
    ]


def test_each_strategy_is_reported_independently() -> None:
    cycles = _cycles("orb-a", ["TREND_UP"] * 8, [1.0] * 8) + _cycles(
        "orb-b", ["TREND_UP", "HIGH_VOL"] * 4, [0.5] * 8
    )

    evidence = build_current_regime_evidence(cycles, resamples=200, seed=2)

    assert evidence.regime == "HIGH_VOL"
    keys = [row.strategy_version for row in evidence.by_strategy]
    assert keys == ["orb-a", "orb-b"]
    # orb-a nunca operó HIGH_VOL: declara el hueco en vez de heredar la celda de orb-b.
    assert evidence.evidence_for("orb-a").measured_n == 0
    assert evidence.evidence_for("orb-b").measured_n == 4
