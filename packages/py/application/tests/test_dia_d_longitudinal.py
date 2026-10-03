"""V2.88.38 · DÍA-D AUTO — contratos de la agregación LONGITUDINAL OOS (pura).

Invariantes que se fijan aquí:

* La dirección se **infiere** de la geometría ``stop`` vs ``entry`` (long: ``stop < entry``); una
  geometría imposible NO se asume larga (hueco declarado).
* MAE/MFE son extremos entre días (barras D1) normalizados por el riesgo al nacer; un ciclo sin
  geometría/riesgo/barras es un hueco declarado, nunca relleno con ``0``.
* La estabilidad se mide por cubos temporales de ``entryDay``; un cubo vacío no entra y la
  dispersión de una serie vacía es ``None``.
* El artefacto es determinista, reutiliza el veredicto/`evidenceQuality` de ``dia_d_auto_feedback``
  (no duplica umbrales) y declara sus límites.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from bolsa_application.dia_d_longitudinal import (
    LONG,
    REASON_NO_BARS,
    REASON_NO_DIRECTION,
    SHORT,
    bucket_key,
    bucket_series,
    build_dia_d_longitudinal_artifact,
    excursion_for_cycle,
    excursions,
    infer_direction,
    longest_operable_run,
    stability_summary,
    summarize_excursions,
)

_ORIGIN = datetime(2022, 1, 3, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 1_000


def _day(index: int) -> str:
    return (_ORIGIN + timedelta(days=index)).strftime("%Y-%m-%d")


def _bar(index: int, *, high: float, low: float) -> _Bar:
    return _Bar(
        timestamp=f"{_day(index)}T00:00:00Z",
        open=(high + low) / 2,
        high=high,
        low=low,
        close=(high + low) / 2,
    )


def _trip(
    *,
    symbol: str = "AAA",
    entry_day: str,
    exit_day: str,
    entry_price: float,
    stop: float,
    realized_r: float,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "entryDay": entry_day,
        "exitDay": exit_day,
        "entryPrice": entry_price,
        "stop": stop,
        "realizedR": realized_r,
    }


# ── Dirección inferida ───────────────────────────────────────────────────────────


def test_infer_direction_long_short_and_impossible():
    assert infer_direction(entry=100.0, stop=95.0) == LONG
    assert infer_direction(entry=100.0, stop=105.0) == SHORT
    assert infer_direction(entry=100.0, stop=100.0) is None
    assert infer_direction(entry=None, stop=95.0) is None
    assert infer_direction(entry="x", stop=95.0) is None


# ── MAE/MFE por ciclo ────────────────────────────────────────────────────────────


def test_excursion_long_uses_low_as_adverse_high_as_favorable():
    bars = {"AAA": [_bar(0, high=110.0, low=90.0), _bar(1, high=105.0, low=85.0)]}
    row = excursion_for_cycle(
        bars_by_symbol=bars,
        round_trip=_trip(entry_day=_day(0), exit_day=_day(1), entry_price=100.0, stop=95.0, realized_r=1.0),
    )
    assert row.measured is True
    assert row.direction == LONG
    assert row.risk == pytest.approx(5.0)
    assert row.mae_r == pytest.approx((85.0 - 100.0) / 5.0)  # −3.0
    assert row.mfe_r == pytest.approx((110.0 - 100.0) / 5.0)  # +2.0


def test_excursion_short_is_mirrored():
    bars = {"AAA": [_bar(0, high=110.0, low=90.0), _bar(1, high=105.0, low=85.0)]}
    row = excursion_for_cycle(
        bars_by_symbol=bars,
        round_trip=_trip(entry_day=_day(0), exit_day=_day(1), entry_price=100.0, stop=105.0, realized_r=-1.0),
    )
    assert row.measured is True
    assert row.direction == SHORT
    assert row.risk == pytest.approx(5.0)
    assert row.mae_r == pytest.approx((100.0 - 110.0) / 5.0)  # −2.0
    assert row.mfe_r == pytest.approx((100.0 - 85.0) / 5.0)  # +3.0


def test_excursion_without_bars_in_range_is_declared_gap():
    bars = {"AAA": [_bar(9, high=110.0, low=90.0)]}
    row = excursion_for_cycle(
        bars_by_symbol=bars,
        round_trip=_trip(entry_day=_day(0), exit_day=_day(1), entry_price=100.0, stop=95.0, realized_r=1.0),
    )
    assert row.measured is False
    assert row.mae_r is None and row.mfe_r is None
    assert row.reason == REASON_NO_BARS


def test_excursion_with_impossible_geometry_is_declared_gap():
    bars = {"AAA": [_bar(0, high=110.0, low=90.0)]}
    row = excursion_for_cycle(
        bars_by_symbol=bars,
        round_trip=_trip(entry_day=_day(0), exit_day=_day(0), entry_price=100.0, stop=100.0, realized_r=0.0),
    )
    assert row.measured is False
    assert row.reason == REASON_NO_DIRECTION


def test_excursions_are_sorted_by_entry_day_then_symbol():
    bars = {"AAA": [_bar(0, high=101.0, low=99.0)], "BBB": [_bar(0, high=101.0, low=99.0)]}
    rows = excursions(
        bars_by_symbol=bars,
        round_trips=[
            _trip(symbol="BBB", entry_day=_day(0), exit_day=_day(0), entry_price=100.0, stop=99.0, realized_r=1.0),
            _trip(symbol="AAA", entry_day=_day(0), exit_day=_day(0), entry_price=100.0, stop=99.0, realized_r=1.0),
        ],
    )
    assert [row.symbol for row in rows] == ["AAA", "BBB"]


def test_summarize_excursions_declares_gaps_and_uses_none_for_empty():
    bars = {"AAA": [_bar(0, high=110.0, low=90.0)]}
    measured = excursion_for_cycle(
        bars_by_symbol=bars,
        round_trip=_trip(entry_day=_day(0), exit_day=_day(0), entry_price=100.0, stop=95.0, realized_r=1.0),
    )
    gap = excursion_for_cycle(
        bars_by_symbol=bars,
        round_trip=_trip(entry_day=_day(7), exit_day=_day(8), entry_price=100.0, stop=95.0, realized_r=1.0),
    )
    summary = summarize_excursions([measured, gap])
    assert summary["measured"] == 1
    assert summary["unmeasured"] == 1
    assert summary["unmeasuredReasons"] == {REASON_NO_BARS: 1}
    assert summary["meanMaeR"] == pytest.approx(-2.0)
    assert summary["meanMfeR"] == pytest.approx(2.0)

    empty = summarize_excursions([])
    assert empty["meanMaeR"] is None and empty["meanMfeR"] is None
    assert empty["minMaeR"] is None and empty["maxMfeR"] is None


# ── Cubos temporales y estabilidad ───────────────────────────────────────────────


def test_bucket_key_year_quarter_month_and_garbage():
    assert bucket_key("2022-05-17", "year") == "2022"
    assert bucket_key("2022-05-17", "quarter") == "2022-Q2"
    assert bucket_key("2022-11-01", "quarter") == "2022-Q4"
    assert bucket_key("2022-05-17", "month") == "2022-05"
    assert bucket_key("no-es-fecha", "month") is None
    assert bucket_key(None, "month") is None


def test_bucket_series_groups_by_entry_day_and_hit_rate():
    trips = [
        _trip(entry_day="2022-01-05", exit_day="2022-01-06", entry_price=100.0, stop=95.0, realized_r=2.0),
        _trip(entry_day="2022-01-20", exit_day="2022-01-21", entry_price=100.0, stop=95.0, realized_r=-1.0),
        _trip(entry_day="2022-02-02", exit_day="2022-02-03", entry_price=100.0, stop=95.0, realized_r=1.0),
    ]
    series = bucket_series(trips, period="month")
    assert [row["bucket"] for row in series] == ["2022-01", "2022-02"]
    assert series[0]["cycles"] == 2
    assert series[0]["expectancyR"] == pytest.approx(0.5)
    assert series[0]["hitRate"] == pytest.approx(0.5)
    assert series[1]["cycles"] == 1


def test_stability_summary_counts_and_none_when_empty():
    series = [
        {"bucket": "2022-01", "cycles": 3, "expectancyR": 1.0},
        {"bucket": "2022-02", "cycles": 2, "expectancyR": -0.5},
        {"bucket": "2022-03", "cycles": 0, "expectancyR": None},
    ]
    summary = stability_summary(series, period="month")
    assert summary["measuredBuckets"] == 2
    assert summary["positiveBuckets"] == 1
    assert summary["negativeBuckets"] == 1
    assert summary["minExpectancyR"] == pytest.approx(-0.5)
    assert summary["maxExpectancyR"] == pytest.approx(1.0)

    empty = stability_summary([], period="month")
    assert empty["measuredBuckets"] == 0
    assert empty["minExpectancyR"] is None


# ── Tramo operable contiguo (plan B declarado) ───────────────────────────────────


def test_longest_operable_run_within_bounds():
    flags = [True, True, False, True, True, True, False, True]
    assert longest_operable_run(flags, start_index=0, end_index=7) == (3, 5)
    assert longest_operable_run(flags, start_index=0, end_index=1) == (0, 1)
    assert longest_operable_run(flags, start_index=2, end_index=2) is None
    assert longest_operable_run([], start_index=0, end_index=0) is None


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def _positive_trips(count: int) -> list[dict[str, object]]:
    return [
        _trip(entry_day=_day(i), exit_day=_day(i + 1), entry_price=100.0, stop=95.0, realized_r=1.0)
        for i in range(count)
    ]


def test_artifact_is_deterministic_and_reuses_verdict():
    trips = _positive_trips(20)
    days = [_day(i) for i in range(21)]
    artifact = build_dia_d_longitudinal_artifact(
        window_from=days[0],
        window_to=days[-1],
        days=days,
        operable_days=21,
        round_trips=trips,
        bucket_period="month",
    )
    again = build_dia_d_longitudinal_artifact(
        window_from=days[0],
        window_to=days[-1],
        days=days,
        operable_days=21,
        round_trips=trips,
        bucket_period="month",
    )
    assert json.dumps(artifact, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert artifact["summary"]["verdict"] == "OOS_SUPPORTED"
    assert artifact["summary"]["evidenceQuality"] == "SUPPORTED"
    assert artifact["summary"]["measuredCycles"] == 20
    assert artifact["basis"] == "entryDay"
    assert artifact["limits"]


def test_artifact_not_measured_below_floor():
    artifact = build_dia_d_longitudinal_artifact(
        window_from=_day(0),
        window_to=_day(2),
        days=[_day(0), _day(1), _day(2)],
        operable_days=3,
        round_trips=_positive_trips(3),
    )
    assert artifact["summary"]["verdict"] == "NOT_MEASURED"
    assert artifact["summary"]["evidenceQuality"] == "NOT_MEASURED"
    assert artifact["summary"]["expectancyR"] == pytest.approx(1.0)


def test_artifact_declares_per_symbol_values():
    trips = _positive_trips(20) + [
        _trip(symbol="BBB", entry_day=_day(i), exit_day=_day(i + 1), entry_price=100.0, stop=95.0, realized_r=-1.0)
        for i in range(10)
    ]
    artifact = build_dia_d_longitudinal_artifact(
        window_from=_day(0),
        window_to=_day(20),
        days=[_day(i) for i in range(21)],
        operable_days=21,
        round_trips=trips,
    )
    symbols = [row["symbol"] for row in artifact["values"]]
    assert symbols == ["AAA", "BBB"]
    by_symbol = {row["symbol"]: row for row in artifact["values"]}
    assert by_symbol["AAA"]["verdict"] == "OOS_SUPPORTED"
    assert by_symbol["BBB"]["verdict"] == "REFUTED"  # expectativa negativa
