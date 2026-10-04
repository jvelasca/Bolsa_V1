"""V2.88.43 · DÍA-D AUTO — contratos del BOOTSTRAP de ciclos y la banda TOTAL (pura).

Invariantes que se fijan aquí:

* La banda publica la descomposición venue/sampling/total por métrica; sin muestra es ``None``
  (**nunca** ``0``).
* ``totalVar = venueVar + samplingVar`` y ``varianceShare`` suma ``1``.
* ``samplingVar == 0`` si las muestras de cada sorteo son constantes (el bootstrap no inventa ruido).
* ``pointCitable`` sólo es ``True`` si la banda **no** cruza cero, ``|media| > 1.96·SE`` y hay al
  menos ``MIN_DRAWS_FOR_BAND`` sorteos; con menos se declara (``insufficient_draws``).
* La fragilidad declara el ``n`` efectivo (pocos sorteos / pocos ciclos por sorteo).
* El ledger de ciclos conserva las etiquetas declaradas y los huecos de excursión como ``None``.
* El artefacto es determinista (misma semilla y ``B`` ⇒ payload byte a byte idéntico).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from bolsa_application.dia_d_multi import build_dia_d_multi_artifact
from bolsa_application.dia_d_multi_sampling import (
    KIND,
    LEDGER_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_cycle_ledger,
    build_sampling_artifact,
)
from bolsa_application.dia_d_multi_uncertainty import build_band_artifact

# ── Utilidades de muestra (ciclos sintéticos, sin I/O) ───────────────────────────


def _trips(
    rows: list[tuple[str, float]],
    *,
    regime: str = "high_vol",
    op: str = "HIGH_VOLATILITY",
) -> list[dict[str, Any]]:
    trips: list[dict[str, Any]] = []
    for index, (year, realized) in enumerate(rows):
        day = f"{year}-01-{5 + index:02d}"
        trips.append(
            {
                "symbol": f"S{index}",
                "entryDay": day,
                "exitDay": f"{year}-01-{6 + index:02d}",
                "realizedR": realized,
            }
        )
    return trips


def _ledger(
    rows: list[tuple[str, float]],
    *,
    regime: str = "high_vol",
    op: str = "HIGH_VOLATILITY",
) -> dict[str, Any]:
    """Ledger de ciclos de UN sorteo con las filas ``(año, realizedR)`` dadas."""
    trips = _trips(rows, regime=regime, op=op)
    return build_cycle_ledger(
        round_trips=trips,
        regime_by_day={str(trip["entryDay"]): regime for trip in trips},
        operational_regime_by_day={str(trip["entryDay"]): op for trip in trips},
    )


def _artifact(
    rows: list[tuple[str, float]],
    *,
    regime: str = "high_vol",
    op: str = "HIGH_VOLATILITY",
) -> dict[str, Any]:
    """Artefacto ``dia-d-multi-v1`` de UN sorteo (para reconstruir la banda del venue)."""
    trips = _trips(rows, regime=regime, op=op)
    years = sorted({str(trip["entryDay"])[:4] for trip in trips})
    return build_dia_d_multi_artifact(
        years=years,
        windows=[{"year": year, "measured": True} for year in years],
        round_trips=trips,
        regime_by_day={str(trip["entryDay"]): regime for trip in trips},
        operational_regime_by_day={str(trip["entryDay"]): op for trip in trips},
    )


# ── Ledger de ciclos ─────────────────────────────────────────────────────────────


def test_ledger_rows_carry_labels_and_missing_excursion_is_none():
    trips = _trips([("2022", 1.5)])
    ledger = build_cycle_ledger(
        round_trips=trips,
        excursions_rows=[],
        regime_by_day={"2022-01-05": "range"},
        operational_regime_by_day={"2022-01-05": "SIDEWAYS"},
    )
    assert ledger["schemaVersion"] == LEDGER_SCHEMA_VERSION
    row = ledger["cycles"][0]
    assert row["realizedR"] == 1.5
    assert row["year"] == "2022"
    assert row["regime"] == "range"
    assert row["operationalRegime"] == "SIDEWAYS"
    # Sin excursión medida: hueco declarado, nunca 0.
    assert row["maeR"] is None
    assert row["mfeR"] is None


def test_ledger_attaches_measured_excursion_by_cycle_key():
    trips = _trips([("2022", 1.5)])
    ledger = build_cycle_ledger(
        round_trips=trips,
        excursions_rows=[
            {"symbol": "S0", "entryDay": "2022-01-05", "exitDay": "2022-01-06", "maeR": -1.2, "mfeR": 3.0}
        ],
    )
    row = ledger["cycles"][0]
    assert row["maeR"] == -1.2
    assert row["mfeR"] == 3.0


def test_ledger_v2_is_additive_and_keeps_the_labels_the_fold_reads():
    """El ledger v2 añade el diagnóstico sin romper lo que la banda (v2_95) ya consumía."""
    trips = _trips([("2022", 1.5)])
    ledger = build_cycle_ledger(
        round_trips=trips,
        regime_by_day={"2022-01-05": "range"},
        operational_regime_by_day={"2022-01-05": "SIDEWAYS"},
    )
    assert ledger["schemaVersion"] == "dia-d-multi-cycle-ledger-v2"
    row = ledger["cycles"][0]
    # Campos v1 intactos (los que lee `_cell_cycles`).
    assert row["realizedR"] == 1.5
    assert row["year"] == "2022"
    assert row["regime"] == "range"
    assert row["operationalRegime"] == "SIDEWAYS"
    # Campos v2 aditivos: sin detalle capturado se declaran huecos, nunca 0.
    assert row["exitMechanism"] == "SIN_MECANISMO"
    assert row["frictionMeasurement"] == "UNKNOWN"
    assert row["frictionR"] is None
    assert row["netRealizedR"] is None
    assert row["entryAdverseR"] is None
    # Y la banda sigue leyendo el mismo ledger con el MISMO resultado agregado.
    artifact = build_sampling_artifact(draw_ledgers=[ledger, ledger], resamples=20)
    assert artifact["global"]["metrics"]["expectancyR"]["mean"] == 1.5


# ── Banda: descomposición venue / sampling / total ───────────────────────────────


def test_total_variance_is_venue_plus_sampling_and_shares_sum_to_one():
    artifact = build_sampling_artifact(
        draw_ledgers=[
            _ledger([("2022", 1.0), ("2022", 2.0)]),
            _ledger([("2022", 0.0), ("2022", 1.0)]),
        ],
        resamples=200,
    )
    metric = artifact["global"]["metrics"]["expectancyR"]
    assert metric["total"]["var"] == pytest.approx(metric["venue"]["var"] + metric["sampling"]["var"])
    share = metric["varianceShare"]
    assert share["venue"] + share["sampling"] == pytest.approx(1.0)


def test_sampling_variance_is_zero_when_each_draw_is_constant():
    ledger = _ledger([("2022", 1.0), ("2022", 1.0), ("2022", 1.0)])
    artifact = build_sampling_artifact(draw_ledgers=[ledger, ledger], resamples=100)
    metric = artifact["global"]["metrics"]["expectancyR"]
    assert metric["sampling"]["var"] == 0.0
    assert metric["venue"]["var"] == 0.0
    assert metric["total"]["var"] == 0.0


def test_realized_total_is_cycles_times_expectancy_when_counts_match():
    artifact = build_sampling_artifact(
        draw_ledgers=[
            _ledger([("2022", 2.0), ("2022", 0.0)]),
            _ledger([("2022", 1.0), ("2022", 1.0)]),
        ],
        resamples=50,
    )
    expectancy = artifact["global"]["metrics"]["expectancyR"]["mean"]
    total = artifact["global"]["metrics"]["realizedRTotal"]["mean"]
    # Ambos sorteos tienen n = 2: su resultado total es n veces su expectativa.
    assert total == pytest.approx(2.0 * expectancy)


# ── Presencia de cubos y regla del hueco ─────────────────────────────────────────


def test_cell_absent_in_a_draw_lowers_draws_with_cell():
    two_years = _ledger([("2022", 1.0), ("2023", 2.0)])
    only_2022 = _ledger([("2022", 1.0)])
    artifact = build_sampling_artifact(draw_ledgers=[two_years, only_2022], resamples=20)
    rows = {row["year"]: row for row in artifact["byYear"]}
    assert rows["2023"]["drawsWithCell"] == 1
    assert rows["2022"]["drawsWithCell"] == 2


def test_no_draws_declares_none_not_zero():
    artifact = build_sampling_artifact(draw_ledgers=[], resamples=10)
    assert artifact["draws"] == 0
    assert artifact["global"]["metrics"]["expectancyR"]["mean"] is None
    assert artifact["global"]["metrics"]["expectancyR"]["total"]["band"] is None
    assert artifact["global"]["validity"]["totalPointCitable"] is False
    assert artifact["global"]["validity"]["total"]["note"] == "sin_muestra"
    assert artifact["byYear"] == []


# ── Citabilidad por eje ──────────────────────────────────────────────────────────


def test_venue_point_citable_is_false_when_the_draws_cross_zero():
    artifact = build_sampling_artifact(
        draw_ledgers=[_ledger([("2022", 1.0)]), _ledger([("2022", -1.0)])],
        resamples=50,
    )
    metric = artifact["global"]["metrics"]["realizedRTotal"]
    assert metric["venue"]["crossesZeroR"] is True
    assert artifact["global"]["validity"]["venuePointCitable"] is False


def test_total_point_citable_is_true_when_the_band_is_narrow_and_away_from_zero():
    artifact = build_sampling_artifact(
        draw_ledgers=[
            _ledger([("2022", 5.0), ("2022", 5.0)]),
            _ledger([("2022", 5.1), ("2022", 5.1)]),
            _ledger([("2022", 4.9), ("2022", 4.9)]),
        ],
        resamples=100,
    )
    metric = artifact["global"]["metrics"]["realizedRTotal"]
    assert metric["venue"]["crossesZeroR"] is False
    assert artifact["global"]["validity"]["totalPointCitable"] is True


def test_single_draw_is_not_citable():
    artifact = build_sampling_artifact(
        draw_ledgers=[_ledger([("2022", 5.0), ("2022", 5.0)])],
        resamples=50,
    )
    assert artifact["global"]["validity"]["totalPointCitable"] is False
    assert artifact["global"]["validity"]["total"]["note"] == "insufficient_draws"


# ── Fragilidad declarada ─────────────────────────────────────────────────────────


def test_fragility_flags_few_cycles_per_draw():
    artifact = build_sampling_artifact(
        draw_ledgers=[_ledger([("2022", 1.0)]), _ledger([("2022", 2.0)])],
        resamples=10,
    )
    fragility = artifact["global"]["fragility"]
    assert fragility["fragile"] is True
    assert "few_cycles_per_draw" in fragility["reasons"]


def test_fragility_is_clean_with_enough_draws_and_cycles():
    ledger = _ledger([("2022", float(index)) for index in range(6)])
    artifact = build_sampling_artifact(
        draw_ledgers=[ledger, ledger, ledger, ledger], resamples=10
    )
    assert artifact["global"]["fragility"]["fragile"] is False


# ── Cruce con la banda del venue (autochequeo) ───────────────────────────────────


def test_venue_band_cross_check_matches_the_pure_venue_band():
    rows = [("2022", -5.0), ("2022", -4.0)]
    ledgers = [_ledger(rows), _ledger(rows)]
    venue = build_band_artifact(draws=[_artifact(rows), _artifact(rows)])
    artifact = build_sampling_artifact(draw_ledgers=ledgers, resamples=50, venue_band=venue)
    check = artifact["venueBandCrossCheck"]
    assert check["available"] is True
    assert check["evidenceDrift"] is False
    assert check["driftedKeys"] == []


# ── Determinismo y contrato ──────────────────────────────────────────────────────


def test_artifact_is_deterministic_and_declares_its_contract():
    ledgers = [
        _ledger([("2022", 1.0), ("2022", -1.0)]),
        _ledger([("2022", 0.5), ("2022", -0.5)]),
    ]
    first = build_sampling_artifact(draw_ledgers=ledgers, resamples=64, seed=1234)
    again = build_sampling_artifact(draw_ledgers=ledgers, resamples=64, seed=1234)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert first["schemaVersion"] == SCHEMA_VERSION == "dia-d-multi-sampling-v1"
    assert first["kind"] == KIND == "DIA_D_AUTO_MULTI_SAMPLING"
    assert first["readOnly"] is True
    assert first["resamplingUnit"] == "cycle"
    assert first["resamples"] == 64
    assert first["seed"] == 1234
    assert first["limits"]
