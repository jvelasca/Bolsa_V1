"""V2.88.41 · DÍA-D AUTO — contratos de la ATRIBUCIÓN MULTIRREGIMEN (pura).

Invariantes que se fijan aquí:

* La cobertura es declaraDA y completa: ``yearsMeasured ∪ yearsNotMeasured == yearsRequested``;
  un año sin ventana declarada cae en ``sin_ventana_declarada`` (fail-closed).
* Cada cubo (año / régimen / celda año × régimen) publica payoff, excursión, captura y la
  severidad de MAE por POBLACIÓN (ALL/WINNERS/LOSERS); un cubo sin ciclos medibles no aparece.
* La consistencia de la matriz se mantiene: las celdas de un año suman los ciclos de su fila.
* La regla del hueco no se relaja: sin muestra, medias y fracciones son ``None`` (nunca ``0``).
* El artefacto es determinista (sin reloj ni aleatorios).
"""

from __future__ import annotations

import json

from bolsa_application.dia_d_longitudinal import LONG, Excursion
from bolsa_application.dia_d_multi import (
    SIN_OPERATIONAL,
    SIN_YEAR,
    build_dia_d_multi_artifact,
    operational_regime_key_reader,
    year_key_reader,
)


def _trip(
    *,
    symbol: str = "AAA",
    entry_day: str = "2022-01-05",
    exit_day: str = "2022-01-06",
    realized_r: float | None,
    strategy_version: str | None = None,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "entryDay": entry_day,
        "exitDay": exit_day,
        "entryPrice": 100.0,
        "stop": 95.0,
        "realizedR": realized_r,
        "strategyVersion": strategy_version,
    }


def _exc(
    *,
    symbol: str = "AAA",
    entry_day: str = "2022-01-05",
    exit_day: str = "2022-01-06",
    mae_r: float | None,
    mfe_r: float | None,
    measured: bool = True,
) -> Excursion:
    return Excursion(
        symbol=symbol,
        entry_day=entry_day,
        exit_day=exit_day,
        direction=LONG,
        risk=5.0,
        mae_r=mae_r,
        mfe_r=mfe_r,
        measured=measured,
        reason=None if measured else "sin_barras_en_rango",
    )


# ── Lectores de dimensión ────────────────────────────────────────────────────────


def test_year_and_operational_readers_declare_fallbacks():
    assert year_key_reader()(_trip(entry_day="2023-04-05", realized_r=1.0)) == "2023"
    assert year_key_reader()(_trip(entry_day="", realized_r=1.0)) == ""

    reader = operational_regime_key_reader({"2023-04-05": "BULL_TREND"})
    assert reader(_trip(entry_day="2023-04-05", realized_r=1.0)) == "BULL_TREND"
    assert reader(_trip(entry_day="2023-04-06", realized_r=1.0)) == ""


# ── Cobertura ────────────────────────────────────────────────────────────────────


def test_coverage_splits_measured_and_not_measured():
    artifact = build_dia_d_multi_artifact(
        years=[2021, 2022],
        windows=[
            {"year": "2021", "measured": False, "reason": "sin_universo_pit"},
            {"year": "2022", "measured": True},
        ],
        round_trips=[_trip(entry_day="2022-01-05", realized_r=1.0)],
    )
    coverage = artifact["coverage"]
    assert coverage["yearsRequested"] == ["2021", "2022"]
    assert coverage["yearsMeasured"] == ["2022"]
    assert coverage["yearsEmpty"] == []
    assert coverage["yearsNotMeasured"] == [
        {"year": "2021", "reason": "sin_universo_pit"},
    ]


def test_coverage_declares_a_measured_year_with_no_cycles_as_empty():
    artifact = build_dia_d_multi_artifact(
        years=[2021, 2022],
        windows=[
            {"year": "2021", "measured": True},
            {"year": "2022", "measured": True},
        ],
        round_trips=[_trip(entry_day="2022-01-05", realized_r=1.0)],
    )
    assert artifact["coverage"]["yearsMeasured"] == ["2021", "2022"]
    assert artifact["coverage"]["yearsEmpty"] == ["2021"]
    assert [row["year"] for row in artifact["byYear"]] == ["2022"]


def test_coverage_fails_closed_when_a_requested_year_has_no_window():
    artifact = build_dia_d_multi_artifact(
        years=[2020, 2022],
        windows=[{"year": "2022", "measured": True}],
        round_trips=[_trip(entry_day="2022-01-05", realized_r=1.0)],
    )
    not_measured = artifact["coverage"]["yearsNotMeasured"]
    assert not_measured == [{"year": "2020", "reason": "sin_ventana_declarada"}]
    # La unión cubre TODOS los años pedidos (invariante falsable).
    requested = set(artifact["coverage"]["yearsRequested"])
    measured = set(artifact["coverage"]["yearsMeasured"])
    declared = {row["year"] for row in not_measured}
    assert measured | declared == requested


# ── año × régimen: consistencia de la matriz ─────────────────────────────────────


def test_by_year_by_regime_and_matrix_are_consistent():
    trips = [
        _trip(symbol="A", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=2.0),
        _trip(symbol="B", entry_day="2022-02-10", exit_day="2022-02-11", realized_r=-1.0),
        _trip(symbol="C", entry_day="2023-03-15", exit_day="2023-03-16", realized_r=1.0),
    ]
    regimes = {"2022-01-05": "trend_up", "2022-02-10": "trend_up", "2023-03-15": "high_vol"}
    operational = {
        "2022-01-05": "BULL_TREND",
        "2022-02-10": "BULL_TREND",
        "2023-03-15": "HIGH_VOLATILITY",
    }
    artifact = build_dia_d_multi_artifact(
        years=[2022, 2023],
        windows=[{"year": "2022", "measured": True}, {"year": "2023", "measured": True}],
        round_trips=trips,
        regime_by_day=regimes,
        operational_regime_by_day=operational,
    )
    by_year = {row["year"]: row for row in artifact["byYear"]}
    assert sorted(by_year) == ["2022", "2023"]
    assert by_year["2022"]["cycles"] == 2
    assert by_year["2023"]["cycles"] == 1

    assert [row["regime"] for row in artifact["byRegime"]] == ["high_vol", "trend_up"]
    assert [row["regime"] for row in artifact["byOperationalRegime"]] == [
        "BULL_TREND",
        "HIGH_VOLATILITY",
    ]

    matrix = {(row["year"], row["regime"]): row for row in artifact["byYearByRegime"]}
    assert matrix[("2022", "trend_up")]["cycles"] == 2
    assert matrix[("2023", "high_vol")]["cycles"] == 1
    # Consistencia: las celdas de un año suman los ciclos de su fila.
    for year, row in by_year.items():
        cells = [cell for cell in artifact["byYearByRegime"] if cell["year"] == year]
        assert sum(cell["cycles"] for cell in cells) == row["cycles"]


# ── Resultado: severidad por población ───────────────────────────────────────────


def test_bucket_splits_winners_and_losers_by_population():
    trips = [
        _trip(symbol="W1", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=2.0),
        _trip(symbol="W2", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=1.0),
        _trip(symbol="L1", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=-1.0),
    ]
    rows = [
        _exc(symbol="W1", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-1.6, mfe_r=2.0),
        _exc(symbol="W2", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.5, mfe_r=2.0),
        _exc(symbol="L1", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-1.2, mfe_r=0.5),
    ]
    artifact = build_dia_d_multi_artifact(
        years=[2022],
        windows=[{"year": "2022", "measured": True}],
        round_trips=trips,
        excursions_rows=rows,
        regime_by_day={"2022-01-05": "high_vol"},
    )
    populations = artifact["byYear"][0]["maeSeverity"]["populations"]
    assert populations["ALL"]["cycles"] == 3
    assert populations["WINNERS"]["cycles"] == 2
    assert populations["LOSERS"]["cycles"] == 1
    assert populations["WINNERS"]["breaches"]["-1.00"]["count"] == 1  # W1 atraviesa -1R y GANA
    assert populations["WINNERS"]["meanMaeR"] > populations["LOSERS"]["meanMaeR"]


# ── Excursión: captura acotada ───────────────────────────────────────────────────


def test_capture_is_bounded_and_declares_above_one():
    trips = [
        _trip(symbol="A", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=-0.5),
        _trip(symbol="B", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=3.0),
    ]
    rows = [
        # MFE diminuto con cierre en pérdida: la captura debe ser 0, nunca negativa.
        _exc(symbol="A", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.5, mfe_r=0.001),
        # Cierre por encima del MFE medido: ratio 1.5, se declara, no se recorta.
        _exc(symbol="B", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.1, mfe_r=2.0),
    ]
    artifact = build_dia_d_multi_artifact(
        years=[2022],
        windows=[{"year": "2022", "measured": True}],
        round_trips=trips,
        excursions_rows=rows,
    )
    capture = artifact["capture"]["captureRatio"]
    assert capture["mean"] is not None and capture["mean"] >= 0.0
    assert capture["aboveOneCount"] == 1


# ── Regla del hueco ──────────────────────────────────────────────────────────────


def test_empty_sample_declares_none_not_zero():
    artifact = build_dia_d_multi_artifact(
        years=[2022],
        windows=[{"year": "2022", "measured": True}],
        round_trips=[],
    )
    assert artifact["summary"]["measuredCycles"] == 0
    assert artifact["summary"]["expectancyR"] is None
    assert artifact["summary"]["realizedRTotal"] is None
    assert artifact["byYear"] == []
    assert artifact["byRegime"] == []
    assert artifact["byYearByRegime"] == []
    assert artifact["decomposition"]["cycles"] == 0
    assert artifact["decomposition"]["expectancyR"] is None
    assert artifact["capture"]["captureRatio"]["mean"] is None
    assert artifact["maeSeverity"]["populations"]["ALL"]["meanMaeR"] is None


def test_missing_dimensions_fall_into_declared_buckets():
    artifact = build_dia_d_multi_artifact(
        years=[2022],
        windows=[{"year": "2022", "measured": True}],
        round_trips=[_trip(symbol="A", entry_day="", realized_r=1.0)],
    )
    assert [row["year"] for row in artifact["byYear"]] == [SIN_YEAR]
    assert [row["regime"] for row in artifact["byOperationalRegime"]] == [SIN_OPERATIONAL]


# ── Determinismo ─────────────────────────────────────────────────────────────────


def test_artifact_is_deterministic():
    trips = [
        _trip(symbol="A", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=2.0),
        _trip(symbol="B", entry_day="2023-02-10", exit_day="2023-02-11", realized_r=-1.0),
    ]
    rows = [
        _exc(symbol="A", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.5, mfe_r=3.0),
        _exc(symbol="B", entry_day="2023-02-10", exit_day="2023-02-11", mae_r=-1.4, mfe_r=0.4),
    ]
    kwargs = {
        "years": [2022, 2023],
        "windows": [{"year": "2022", "measured": True}, {"year": "2023", "measured": True}],
        "round_trips": trips,
        "excursions_rows": rows,
        "regime_by_day": {"2022-01-05": "trend_up", "2023-02-10": "high_vol"},
        "operational_regime_by_day": {
            "2022-01-05": "BULL_TREND",
            "2023-02-10": "HIGH_VOLATILITY",
        },
        "top_k": 3,
    }
    first = build_dia_d_multi_artifact(**kwargs)
    again = build_dia_d_multi_artifact(**kwargs)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert first["schemaVersion"] == "dia-d-multi-v1"
    assert first["kind"] == "DIA_D_AUTO_MULTI_ATTRIBUTION"
    assert first["readOnly"] is True
    assert first["basis"] == "entryDay"
    assert first["limits"]
