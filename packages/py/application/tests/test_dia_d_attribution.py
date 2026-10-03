"""V2.88.39 · DÍA-D AUTO — contratos de la ATRIBUCIÓN del OOS (pura).

Invariantes que se fijan aquí:

* La descomposición del payoff satisface la identidad ``expectancyR = winRate·avgWinR +
  (1 − winRate)·avgLossR`` (residuo ``identityGap`` ~ 0); sin muestra, todo extremo es ``None``.
* La atribución es determinista y fail-closed: una etiqueta ausente cae en su cubo declarado
  ``sin_*``; un cubo sin ciclos medibles no aparece.
* La captura de MFE sólo existe con premio positivo medible; se define sobre ``max(realizedR,0)``
  (nunca negativa), declara ``captureRatio > 1`` aparte y mide el premio dejado en la mesa.
* La severidad de MAE se publica por POBLACIÓN (ALL/WINNERS/LOSERS); sin muestra, la fracción es
  ``None``. La fracción de TODOS los ciclos con MAE ``< -1R`` NO es la de perdedores.
* La concentración clasifica ``concentrated`` cuando retirar el peor ciclo voltea el signo.
* El artefacto es determinista, reutiliza el veredicto/`evidenceQuality` de ``dia_d_auto_feedback``
  y declara sus límites.
"""

from __future__ import annotations

import json

import pytest

from bolsa_application.dia_d_attribution import (
    SIN_REGIMEN,
    SIN_SECTOR,
    SIN_VERSION,
    attribute_by,
    build_dia_d_attribution_artifact,
    capture_study,
    concentration,
    index_excursions,
    mae_severity,
    payoff_decomposition,
    regime_key_reader,
    strategy_key_reader,
    symbol_key_reader,
)
from bolsa_application.dia_d_longitudinal import LONG, Excursion


def _trip(
    *,
    symbol: str = "AAA",
    entry_day: str = "2022-01-05",
    exit_day: str = "2022-01-06",
    realized_r: float,
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


# ── Descomposición del payoff ────────────────────────────────────────────────────


def test_payoff_decomposition_identity_and_empty():
    empty = payoff_decomposition([])
    assert empty["cycles"] == 0
    assert empty["winRate"] is None and empty["avgWinR"] is None and empty["avgLossR"] is None
    assert empty["expectancyR"] is None and empty["identityGap"] is None

    trips = [_trip(realized_r=2.0), _trip(realized_r=-1.0), _trip(realized_r=1.0)]
    out = payoff_decomposition(trips)
    assert out["cycles"] == 3
    assert out["wins"] == 2 and out["losses"] == 1
    assert out["winRate"] == pytest.approx(2 / 3)
    assert out["avgWinR"] == pytest.approx(1.5)
    assert out["avgLossR"] == pytest.approx(-1.0)
    assert out["payoffRatio"] == pytest.approx(1.5)
    assert out["expectancyR"] == pytest.approx(2 / 3)
    assert out["identityGap"] == pytest.approx(0.0, abs=1e-12)


def test_payoff_decomposition_edge_samples_declare_none_not_zero():
    all_wins = payoff_decomposition([_trip(realized_r=1.0), _trip(realized_r=2.0)])
    assert all_wins["avgLossR"] is None
    assert all_wins["payoffRatio"] is None
    assert all_wins["identityGap"] == pytest.approx(0.0)

    all_losses = payoff_decomposition([_trip(realized_r=-1.0), _trip(realized_r=-2.0)])
    assert all_losses["avgWinR"] is None
    assert all_losses["payoffRatio"] is None
    assert all_losses["winRate"] == pytest.approx(0.0)
    assert all_losses["identityGap"] == pytest.approx(0.0)


# ── Atribución por dimensión ─────────────────────────────────────────────────────


def test_attribute_by_regime_is_deterministic_and_declares_missing():
    trips = [
        _trip(symbol="AAA", entry_day="2022-01-05", realized_r=2.0),
        _trip(symbol="BBB", entry_day="2022-01-06", realized_r=-1.0),
        _trip(symbol="CCC", entry_day="2022-12-30", realized_r=-2.0),
    ]
    regimes = {"2022-01-05": "trend_up", "2022-01-06": "trend_up"}
    rows = attribute_by(trips, key_fn=regime_key_reader(regimes))
    assert [row["label"] for row in rows] == ["sin_regimen", "trend_up"]
    by_label = {row["label"]: row for row in rows}
    assert by_label["trend_up"]["cycles"] == 2
    assert by_label["trend_up"]["expectancyR"] == pytest.approx(0.5)
    assert by_label["trend_up"]["hitRate"] == pytest.approx(0.5)
    assert by_label[SIN_REGIMEN]["cycles"] == 1
    assert by_label[SIN_REGIMEN]["realizedRTotal"] == pytest.approx(-2.0)


def test_attribute_by_strategy_and_symbol_declare_fallbacks():
    trips = [
        _trip(symbol="AAA", strategy_version="v283-window-a", realized_r=1.0),
        _trip(symbol="AAA", strategy_version=None, realized_r=-1.0),
        _trip(symbol="BBB", strategy_version="v283-window-a", realized_r=3.0),
    ]
    by_strategy = attribute_by(trips, key_fn=strategy_key_reader())
    assert [row["label"] for row in by_strategy] == [SIN_VERSION, "v283-window-a"]
    assert {row["label"]: row["cycles"] for row in by_strategy} == {SIN_VERSION: 1, "v283-window-a": 2}

    by_symbol = attribute_by(trips, key_fn=symbol_key_reader())
    assert [row["label"] for row in by_symbol] == ["AAA", "BBB"]
    assert {row["label"]: row["cycles"] for row in by_symbol} == {"AAA": 2, "BBB": 1}


def test_attribute_by_reports_excursion_means_and_gap_counts():
    trips = [
        _trip(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=1.0),
        _trip(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=-1.0),
    ]
    rows = [
        _exc(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-1.0, mfe_r=2.0),
        _exc(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-3.0, mfe_r=0.5),
    ]
    index = index_excursions(rows)
    out = attribute_by(trips, key_fn=strategy_key_reader(), excursions_by_cycle=index)
    assert len(out) == 1
    bucket = out[0]
    assert bucket["meanMaeR"] == pytest.approx(-2.0)
    assert bucket["meanMfeR"] == pytest.approx(1.25)
    assert bucket["excursionsMeasured"] == 2
    assert bucket["excursionsUnmeasured"] == 0


# ── Captura de MFE y severidad de MAE ────────────────────────────────────────────


def test_capture_study_measures_and_flags_reversals():
    trips = [
        _trip(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=0.5),
        _trip(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=-0.5),
        _trip(symbol="CCC", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=1.0),
    ]
    rows = [
        _exc(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.3, mfe_r=2.0),
        _exc(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-1.0, mfe_r=1.5),
        _exc(symbol="CCC", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.1, mfe_r=-0.2),
    ]
    out = capture_study(trips, excursions_by_cycle=index_excursions(rows))
    assert out["measuredCycles"] == 2
    assert out["notMeasuredCycles"] == 1
    # AAA captura 0.5/2.0; BBB cierra en pérdida ⇒ captura 0 (NO -0.333) y deja el premio entero.
    assert out["captureRatio"]["mean"] == pytest.approx(0.125)
    assert out["captureRatio"]["median"] == pytest.approx(0.125)
    assert out["captureRatio"]["max"] == pytest.approx(0.25)
    assert out["captureRatio"]["aboveOneCount"] == 0
    assert out["capturedR"]["mean"] == pytest.approx(0.25)
    assert out["leftOnTableR"]["mean"] == pytest.approx(1.5)
    assert out["reversedCount"] == 1  # BBB llegó a +1.5R y cerró en -0.5R


def test_capture_study_never_negative_and_declares_above_one():
    trips = [
        _trip(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=-0.5),
        _trip(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=3.0),
    ]
    rows = [
        # MFE diminuto con cierre en pérdida: antes explotaba a -500; ahora es captura 0.
        _exc(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.5, mfe_r=0.001),
        # Cierre por encima del MFE medido: ratio 1.5, se declara en aboveOneCount (no se recorta).
        _exc(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.1, mfe_r=2.0),
    ]
    out = capture_study(trips, excursions_by_cycle=index_excursions(rows))
    assert out["measuredCycles"] == 2
    assert out["captureRatio"]["mean"] == pytest.approx(0.75)
    assert out["captureRatio"]["max"] == pytest.approx(1.5)
    assert out["captureRatio"]["aboveOneCount"] == 1
    assert out["capturedR"]["mean"] == pytest.approx(1.5)
    assert out["leftOnTableR"]["mean"] == pytest.approx(0.0005)  # (0.001 + 0.0) / 2


def test_capture_study_winner_and_loser_with_positive_mfe():
    trips = [
        _trip(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=2.0),
        _trip(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=-1.0),
    ]
    rows = [
        _exc(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.3, mfe_r=3.0),
        _exc(symbol="BBB", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-1.2, mfe_r=2.0),
    ]
    out = capture_study(trips, excursions_by_cycle=index_excursions(rows))
    assert out["captureRatio"]["mean"] == pytest.approx((2 / 3 + 0.0) / 2)
    assert out["capturedR"]["mean"] == pytest.approx(1.0)
    assert out["leftOnTableR"]["mean"] == pytest.approx((1.0 + 2.0) / 2)
    assert out["reversedCount"] == 1


def test_capture_study_empty_declares_none():
    out = capture_study([])
    assert out["measuredCycles"] == 0
    assert out["captureRatio"]["mean"] is None and out["captureRatio"]["median"] is None
    assert out["captureRatio"]["max"] is None
    assert out["capturedR"]["mean"] is None
    assert out["leftOnTableR"]["mean"] is None
    assert out["reversedCount"] == 0


def test_mae_severity_populations_split_winners_and_losers():
    # W1 es GANADOR pero con MAE -1.6R: cuenta en WINNERS, no sólo en "perdedores".
    trips = [
        _trip(symbol="W1", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=2.0),
        _trip(symbol="W2", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=1.0),
        _trip(symbol="L1", entry_day="2022-01-07", exit_day="2022-01-08", realized_r=-1.0),
        _trip(symbol="L2", entry_day="2022-01-07", exit_day="2022-01-08", realized_r=-2.0),
        _trip(symbol="L3", entry_day="2022-01-07", exit_day="2022-01-08", realized_r=-1.0),
    ]
    rows = [
        _exc(symbol="W1", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-1.6, mfe_r=1.0),
        _exc(symbol="W2", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-0.5, mfe_r=1.0),
        _exc(symbol="L1", entry_day="2022-01-07", exit_day="2022-01-08", mae_r=-1.2, mfe_r=1.0),
        _exc(symbol="L2", entry_day="2022-01-07", exit_day="2022-01-08", mae_r=-0.3, mfe_r=1.0),
        _exc(symbol="L3", entry_day="2022-01-07", exit_day="2022-01-08", mae_r=-0.9, mfe_r=1.0),
    ]
    populations = mae_severity(trips, excursions_by_cycle=index_excursions(rows))["populations"]

    assert populations["ALL"]["cycles"] == 5
    assert populations["ALL"]["breaches"]["-1.00"]["count"] == 2
    assert populations["ALL"]["breaches"]["-1.00"]["share"] == pytest.approx(2 / 5)
    assert populations["ALL"]["breaches"]["-1.25"]["count"] == 1
    assert populations["ALL"]["breaches"]["-1.50"]["count"] == 1
    assert populations["ALL"]["minMaeR"] == pytest.approx(-1.6)

    assert populations["WINNERS"]["cycles"] == 2
    assert populations["WINNERS"]["breaches"]["-1.00"]["count"] == 1
    assert populations["WINNERS"]["breaches"]["-1.00"]["share"] == pytest.approx(0.5)

    assert populations["LOSERS"]["cycles"] == 3
    assert populations["LOSERS"]["breaches"]["-1.00"]["count"] == 1
    assert populations["LOSERS"]["breaches"]["-1.00"]["share"] == pytest.approx(1 / 3)
    assert populations["LOSERS"]["breaches"]["-1.25"]["count"] == 0
    assert populations["LOSERS"]["minMaeR"] == pytest.approx(-1.2)


def test_mae_severity_mae_without_realized_stays_in_all_only():
    trips = [_trip(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", realized_r=None)]
    rows = [_exc(symbol="AAA", entry_day="2022-01-05", exit_day="2022-01-06", mae_r=-1.5, mfe_r=1.0)]
    populations = mae_severity(trips, excursions_by_cycle=index_excursions(rows))["populations"]
    assert populations["ALL"]["cycles"] == 1 and populations["ALL"]["breaches"]["-1.00"]["count"] == 1
    assert populations["WINNERS"]["cycles"] == 0
    assert populations["LOSERS"]["cycles"] == 0


def test_mae_severity_empty_declares_none():
    populations = mae_severity([])["populations"]
    assert populations["ALL"]["cycles"] == 0
    assert populations["ALL"]["meanMaeR"] is None
    assert populations["ALL"]["minMaeR"] is None
    assert populations["ALL"]["breaches"]["-1.00"]["count"] == 0
    assert populations["ALL"]["breaches"]["-1.00"]["share"] is None
    assert populations["WINNERS"]["cycles"] == 0 and populations["LOSERS"]["cycles"] == 0


# ── Concentración ────────────────────────────────────────────────────────────────


def test_concentration_flags_single_trade_dependence():
    concentrated = concentration([_trip(realized_r=-4.0), _trip(realized_r=1.0), _trip(realized_r=1.0), _trip(realized_r=1.0), _trip(realized_r=1.0)])
    assert concentrated["expectancyR"] == pytest.approx(0.0)
    assert concentrated["expectancyWithoutWorstR"] == pytest.approx(1.0)
    assert concentrated["signFlipsWithoutWorst"] is True
    assert concentrated["classification"] == "concentrated"

    broad = concentration([_trip(realized_r=-2.0), _trip(realized_r=-2.0), _trip(realized_r=-2.0)])
    assert broad["classification"] == "broad"
    assert broad["signFlipsWithoutWorst"] is False


def test_concentration_empty_declares_none():
    out = concentration([])
    assert out["cycles"] == 0
    assert out["expectancyR"] is None and out["classification"] is None
    assert out["signFlipsWithoutWorst"] is None


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def _positive_trips(count: int) -> list[dict[str, object]]:
    return [
        _trip(entry_day=f"2022-01-{index + 1:02d}", exit_day=f"2022-01-{index + 2:02d}", realized_r=1.0)
        for index in range(count)
    ]


def test_artifact_is_deterministic_and_declares_dimensions():
    trips = _positive_trips(20)
    rows = [
        _exc(
            symbol="AAA",
            entry_day=str(trip["entryDay"]),
            exit_day=str(trip["exitDay"]),
            mae_r=-0.5,
            mfe_r=2.0,
        )
        for trip in trips
    ]
    days = [str(trip["entryDay"]) for trip in trips]
    kwargs = {
        "window_from": days[0],
        "window_to": days[-1],
        "days": days,
        "operable_days": len(days),
        "round_trips": trips,
        "excursions_rows": rows,
        "regime_by_day": {day: "trend_up" for day in days},
        "sector_by_symbol": {"AAA": "tecnologia"},
        "top_k": 3,
    }
    artifact = build_dia_d_attribution_artifact(**kwargs)
    again = build_dia_d_attribution_artifact(**kwargs)
    assert json.dumps(artifact, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert artifact["summary"]["verdict"] == "OOS_SUPPORTED"
    assert artifact["summary"]["measuredCycles"] == 20
    assert artifact["basis"] == "entryDay"
    assert [row["label"] for row in artifact["byRegime"]] == ["trend_up"]
    assert [row["label"] for row in artifact["bySector"]] == ["tecnologia"]
    assert artifact["capture"]["captureRatio"]["mean"] == pytest.approx(0.5)
    assert artifact["capture"]["captureRatio"]["aboveOneCount"] == 0
    assert artifact["maeSeverity"]["populations"]["ALL"]["meanMaeR"] == pytest.approx(-0.5)
    assert artifact["maeSeverity"]["populations"]["WINNERS"]["cycles"] == 20
    assert artifact["maeSeverity"]["populations"]["LOSERS"]["cycles"] == 0
    assert artifact["concentration"]["cycles"] == 20
    assert artifact["limits"]


def test_artifact_declares_missing_sector_and_gap_not_zero():
    trips = _positive_trips(20)
    days = [str(trip["entryDay"]) for trip in trips]
    artifact = build_dia_d_attribution_artifact(
        window_from=days[0],
        window_to=days[-1],
        days=days,
        operable_days=len(days),
        round_trips=trips,
        excursions_rows=[],
        sector_by_symbol={},
    )
    assert [row["label"] for row in artifact["bySector"]] == [SIN_SECTOR]
    assert artifact["capture"]["measuredCycles"] == 0
    assert artifact["capture"]["captureRatio"]["mean"] is None
    assert artifact["maeSeverity"]["populations"]["ALL"]["meanMaeR"] is None
