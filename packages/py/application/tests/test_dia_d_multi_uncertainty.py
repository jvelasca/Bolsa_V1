"""V2.88.42 · DÍA-D AUTO — contratos de la BANDA multirregimen (pura).

Invariantes que se fijan aquí:

* La banda publica ``min``/``median``/``max``/``mean``/``stdev`` por cubo; sin muestra es ``None``
  (**nunca** ``0``).
* Un cubo ausente en un sorteo baja ``drawsWithCell`` (no se inventa un valor).
* ``validity`` publica DOS etiquetas SEPARADAS (H1): ``sensitivityBand`` (``pointCitable`` sólo es
  ``True`` si la banda de R total **no** cruza cero, ``|media| > 1.96·SE`` y hay al menos
  ``MIN_DRAWS_FOR_BAND`` sorteos; con menos, se declara ``insufficient_draws``) y
  ``statisticalConfidence`` (``NOT_MEASURED`` con re-sorteos del venue; nunca se infiere de ellos).
* La cobertura cuenta por año y por sorteo (medido / vacío / no medido), sin rellenar huecos.
* El artefacto es determinista (sin reloj ni aleatorios).
"""

from __future__ import annotations

import json
from typing import Any

from bolsa_application.dia_d_multi import build_dia_d_multi_artifact
from bolsa_application.dia_d_multi_uncertainty import (
    DESIGN_INDEPENDENT,
    DESIGN_VENUE_DRAW,
    KIND,
    POINT_CITABLE_SCOPE,
    SCHEMA_VERSION,
    build_band_artifact,
)


def _trip(
    *,
    symbol: str = "AAA",
    year: int = 2022,
    realized_r: float | None,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "entryDay": f"{year}-01-05",
        "exitDay": f"{year}-01-06",
        "entryPrice": 100.0,
        "stop": 95.0,
        "realizedR": realized_r,
        "strategyVersion": "v283-window-a",
    }


def _exc(*, symbol: str = "AAA", year: int = 2022, mae_r: float, mfe_r: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "entryDay": f"{year}-01-05",
        "exitDay": f"{year}-01-06",
        "maeR": mae_r,
        "mfeR": mfe_r,
    }


def _draw(*, realized_r: float, year: int = 2022, mae_r: float = -1.2, mfe_r: float = 2.0) -> dict[str, Any]:
    """Artefacto ``dia-d-multi-v1`` de un solo ciclo (un sorteo del venue)."""
    return build_dia_d_multi_artifact(
        years=[year],
        windows=[{"year": str(year), "measured": True}],
        round_trips=[_trip(year=year, realized_r=realized_r)],
        excursions_rows=[_exc(year=year, mae_r=mae_r, mfe_r=mfe_r)],
        regime_by_day={f"{year}-01-05": "high_vol"},
        operational_regime_by_day={f"{year}-01-05": "HIGH_VOLATILITY"},
    )


# ── Banda: min/median/max/mean/stdev ─────────────────────────────────────────────


def test_band_reports_order_statistics_and_moments():
    artifact = build_band_artifact(
        draws=[_draw(realized_r=-1.0), _draw(realized_r=-2.0), _draw(realized_r=-3.0)]
    )
    band = artifact["global"]["bands"]["expectancyR"]
    assert band is not None
    assert band["n"] == 3
    assert band["min"] == -3.0
    assert band["max"] == -1.0
    assert band["median"] == -2.0
    assert band["mean"] == -2.0
    assert band["stdev"] == (2.0 / 3.0) ** 0.5  # poblacional
    assert artifact["draws"] == 3


def test_band_of_a_missing_metric_is_none_never_zero():
    # El MFE medio global NO se publica a nivel de artefacto: la banda lo declara hueco.
    artifact = build_band_artifact(draws=[_draw(realized_r=1.0), _draw(realized_r=0.5)])
    assert artifact["global"]["bands"]["meanMfeR"] is None
    # ... pero SÍ está por año (donde el cubo lo mide).
    by_year = artifact["byYear"][0]
    assert by_year["bands"]["meanMfeR"] is not None


# ── Presencia por cubo ───────────────────────────────────────────────────────────


def test_cell_absent_in_a_draw_lowers_draws_with_cell():
    with_2023 = build_dia_d_multi_artifact(
        years=[2022, 2023],
        windows=[{"year": "2022", "measured": True}, {"year": "2023", "measured": True}],
        round_trips=[_trip(year=2022, realized_r=1.0), _trip(symbol="BBB", year=2023, realized_r=2.0)],
    )
    only_2022 = build_dia_d_multi_artifact(
        years=[2022],
        windows=[{"year": "2022", "measured": True}],
        round_trips=[_trip(year=2022, realized_r=1.0)],
    )
    artifact = build_band_artifact(draws=[with_2023, only_2022])
    rows = {row["year"]: row for row in artifact["byYear"]}
    assert rows["2023"]["drawsWithCell"] == 1
    assert rows["2022"]["drawsWithCell"] == 2
    assert artifact["draws"] == 2


# ── Citabilidad del punto ────────────────────────────────────────────────────────


def test_point_citable_is_false_when_the_band_crosses_zero():
    artifact = build_band_artifact(draws=[_draw(realized_r=-1.0), _draw(realized_r=1.0)])
    sensitivity = artifact["global"]["validity"]["sensitivityBand"]
    assert sensitivity["crossesZeroR"] is True
    assert sensitivity["pointCitable"] is False


def test_point_citable_is_true_when_the_band_is_away_from_zero_and_narrow():
    artifact = build_band_artifact(
        draws=[_draw(realized_r=-5.0), _draw(realized_r=-5.1), _draw(realized_r=-4.9)]
    )
    sensitivity = artifact["global"]["validity"]["sensitivityBand"]
    assert sensitivity["crossesZeroR"] is False
    assert sensitivity["pointCitable"] is True
    assert sensitivity["ci95HalfWidth"] is not None and sensitivity["ci95HalfWidth"] > 0.0


def test_insufficient_draws_blocks_citability():
    artifact = build_band_artifact(draws=[_draw(realized_r=-5.0)])
    sensitivity = artifact["global"]["validity"]["sensitivityBand"]
    assert sensitivity["pointCitable"] is False
    assert sensitivity["note"] == "insufficient_draws"


def test_no_draws_declares_none_not_zero():
    artifact = build_band_artifact(draws=[])
    assert artifact["draws"] == 0
    assert artifact["global"]["bands"]["realizedRTotal"] is None
    sensitivity = artifact["global"]["validity"]["sensitivityBand"]
    assert sensitivity["pointCitable"] is False
    assert sensitivity["note"] == "sin_muestra"
    assert artifact["byYear"] == []


# ── H1: sensibilidad del sorteo vs confianza estadística (etiquetas SEPARADAS) ───


def test_h1_sensitivity_and_statistical_confidence_are_separate_labels():
    """H1 — con re-sorteos del venue, ``pointCitable`` NO implica confianza estadística."""
    artifact = build_band_artifact(
        draws=[_draw(realized_r=-5.0), _draw(realized_r=-5.1), _draw(realized_r=-4.9)]
    )
    validity = artifact["global"]["validity"]

    assert validity["design"] == DESIGN_VENUE_DRAW
    assert artifact["design"] == DESIGN_VENUE_DRAW
    sensitivity = validity["sensitivityBand"]
    assert sensitivity["pointCitableScope"] == POINT_CITABLE_SCOPE
    # La banda es citable COMO SENSIBILIDAD...
    assert sensitivity["pointCitable"] is True
    # ... pero la confianza estadística NO se mide con re-sorteos del mismo dato.
    statistical = validity["statisticalConfidence"]
    assert statistical["status"] == "NOT_MEASURED"
    assert statistical["established"] is False
    assert statistical["se"] is None
    assert statistical["reason"]
    assert statistical["requires"]


def test_h1_permutation_does_not_change_the_two_labels():
    """H1 — el veredicto de ambas etiquetas es determinista bajo permutación de los sorteos."""
    draws = [_draw(realized_r=-5.0), _draw(realized_r=-5.1), _draw(realized_r=-4.9)]
    forward = build_band_artifact(draws=draws)["global"]["validity"]
    reversed_order = build_band_artifact(draws=list(reversed(draws)))["global"]["validity"]
    assert forward == reversed_order


def test_h1_independent_sample_measures_statistical_confidence():
    """H1 — solo si el llamante DECLARA observaciones independientes se computa la confianza."""
    artifact = build_band_artifact(
        draws=[_draw(realized_r=-5.0), _draw(realized_r=-5.1), _draw(realized_r=-4.9)],
        design=DESIGN_INDEPENDENT,
    )
    validity = artifact["global"]["validity"]
    assert validity["design"] == DESIGN_INDEPENDENT
    statistical = validity["statisticalConfidence"]
    assert statistical["status"] == "MEASURED"
    assert statistical["established"] is True
    assert statistical["se"] is not None
    assert statistical["reason"] is None


def test_h1_gap_still_marks_statistical_confidence_not_measured():
    """H1 — sin muestra, ambas etiquetas declaran el hueco (nunca un ``0``), incluso con diseño."""
    artifact = build_band_artifact(draws=[], design=DESIGN_INDEPENDENT)
    validity = artifact["global"]["validity"]
    assert validity["sensitivityBand"]["pointCitable"] is False
    assert validity["statisticalConfidence"]["status"] == "MEASURED"
    assert validity["statisticalConfidence"]["established"] is False


# ── Cobertura por año ────────────────────────────────────────────────────────────


def test_coverage_counts_measured_and_empty_per_year():
    measured = build_dia_d_multi_artifact(
        years=[2022, 2023],
        windows=[{"year": "2022", "measured": True}, {"year": "2023", "measured": True}],
        round_trips=[_trip(year=2022, realized_r=1.0), _trip(symbol="BBB", year=2023, realized_r=2.0)],
    )
    empty = build_dia_d_multi_artifact(
        years=[2022, 2023],
        windows=[{"year": "2022", "measured": True}, {"year": "2023", "measured": True}],
        round_trips=[_trip(year=2022, realized_r=1.0)],
    )
    artifact = build_band_artifact(draws=[measured, empty])
    coverage = {row["year"]: row for row in artifact["coverage"]["perYear"]}
    assert coverage["2022"]["measured"] == 2
    assert coverage["2023"]["measured"] == 1
    assert coverage["2023"]["empty"] == 1


# ── Determinismo y forma ─────────────────────────────────────────────────────────


def test_artifact_is_deterministic_and_declares_its_contract():
    draws = [_draw(realized_r=-1.0), _draw(realized_r=-2.0), _draw(realized_r=-3.0)]
    first = build_band_artifact(draws=draws, seed_shift={"K": 3}, meta={"phase": "test"})
    again = build_band_artifact(draws=draws, seed_shift={"K": 3}, meta={"phase": "test"})
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert first["schemaVersion"] == SCHEMA_VERSION == "dia-d-multi-band-v2"
    assert first["kind"] == KIND == "DIA_D_AUTO_MULTI_BAND"
    assert first["readOnly"] is True
    assert first["basis"] == "entryDay"
    assert first["design"] == DESIGN_VENUE_DRAW
    assert first["limits"]
