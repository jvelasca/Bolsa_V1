"""AUTO-21 — tests de la CORRELACIÓN entre estrategias por cubo temporal (``auto_adaptive_correlation``).

Lo que se prueba es la disciplina de medición:

* que dos estrategias con cubos COMPARTIDOS publican un número (y que series idénticas dan 1.0);
* que sin solape / con pocos cubos / con una serie constante la correlación es ``None`` y el hueco
  se DECLARA (``no_shared_buckets`` / ``insufficient_buckets`` / ``constant_series``) — nunca un 0;
* que la lectura es determinista y orden-invariante, y que el cubo se puede declarar (día/semana/mes).
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from bolsa_analytics.cognitive.auto_adaptive_correlation import (
    CORRELATION_BUCKET_DEFAULT,
    CORRELATION_BUCKET_WEEK,
    CORRELATION_MIN_BUCKETS_DEFAULT,
    CORRELATION_NOTE_CONSTANT_SERIES,
    CORRELATION_NOTE_INSUFFICIENT_BUCKETS,
    CORRELATION_NOTE_NO_CYCLES,
    CORRELATION_NOTE_NO_SHARED_BUCKETS,
    STRATEGY_CORRELATION_METHOD,
    bucket_key,
    build_strategy_correlation_report,
    pearson_correlation,
)

_BASE = date(2026, 1, 1)


def _cycle(version: str, index: int, day: int, r: float) -> dict[str, object]:
    return {
        "cycleId": f"{version}-{index}",
        "strategyVersion": version,
        "pnl": str(round(r * 5.0, 6)),
        "riskAmount": "5",
        "marketRegime": "TREND_UP",
        "closedAt": (_BASE + timedelta(days=day)).isoformat() + "T15:30:00+00:00",
        "cost": {"total": 0.0, "measurement": "COMPLETE", "costModelVersion": "cm1"},
    }


def _series(version: str, days: list[int], values: list[float]) -> list[dict[str, object]]:
    return [
        _cycle(version, index, day, r)
        for index, (day, r) in enumerate(zip(days, values, strict=True))
    ]


# ── El número, cuando la muestra lo sostiene ────────────────────────────────────────


def test_identical_series_on_shared_buckets_correlate_perfectly() -> None:
    days = [0, 1, 2, 3, 4]
    values = [1.0, -0.5, 0.3, 0.9, -0.2]
    rows = _series("a", days, values) + _series("b", days, values)

    report = build_strategy_correlation_report(rows)

    assert report.method == STRATEGY_CORRELATION_METHOD
    assert report.bucket == CORRELATION_BUCKET_DEFAULT
    assert report.strategies == ("a", "b")
    pair = report.pair("a", "b")
    assert pair is not None
    assert pair.correlation == pytest.approx(1.0)
    assert pair.shared_buckets == 5
    assert pair.notes == ()
    assert report.as_dict()["pairs"][0]["sharedBuckets"] == 5


def test_a_perfectly_opposite_series_correlates_minus_one() -> None:
    days = [0, 1, 2, 3, 4]
    values = [1.0, -0.5, 0.3, 0.9, -0.2]
    rows = _series("a", days, values) + _series("b", days, [-value for value in values])

    pair = build_strategy_correlation_report(rows).pair("a", "b")

    assert pair is not None
    assert pair.correlation == pytest.approx(-1.0)


def test_the_report_is_deterministic_and_order_invariant() -> None:
    days = [0, 1, 2, 3, 4]
    rows = _series("b", days, [1.0, 0.2, -0.4, 0.7, 0.1]) + _series(
        "a", days, [-0.1, 0.5, 0.3, -0.2, 0.9]
    )
    shuffled = list(rows)
    random.Random(3).shuffle(shuffled)

    assert build_strategy_correlation_report(rows).as_dict() == (
        build_strategy_correlation_report(shuffled).as_dict()
    )


# ── El hueco, cuando la muestra no lo sostiene ──────────────────────────────────────


def test_no_cycle_returns_a_declared_empty_matrix() -> None:
    report = build_strategy_correlation_report([])

    assert report.strategies == ()
    assert report.pairs == ()
    assert report.notes == (CORRELATION_NOTE_NO_CYCLES,)
    assert report.as_dict()["pairs"] == []


def test_without_shared_buckets_the_gap_is_declared() -> None:
    rows = _series("a", [0, 1, 2, 3, 4], [1.0, 0.5, 0.3, 0.9, 0.2]) + _series(
        "b", [10, 11, 12, 13, 14], [1.0, 0.5, 0.3, 0.9, 0.2]
    )

    pair = build_strategy_correlation_report(rows).pair("a", "b")

    assert pair is not None
    assert pair.correlation is None
    assert pair.shared_buckets == 0
    assert pair.notes == (CORRELATION_NOTE_NO_SHARED_BUCKETS,)


def test_too_few_shared_buckets_are_declared_not_faked() -> None:
    rows = _series("a", [0, 1, 2, 10, 11], [1.0, 0.5, 0.3, 0.9, 0.2]) + _series(
        "b", [0, 1, 2, 20, 21], [0.2, 0.9, 0.3, 0.5, 1.0]
    )

    pair = build_strategy_correlation_report(rows).pair("a", "b")

    assert pair is not None
    assert pair.shared_buckets == 3
    assert pair.correlation is None
    assert pair.notes == (CORRELATION_NOTE_INSUFFICIENT_BUCKETS,)


def test_a_constant_series_declares_it_instead_of_zero() -> None:
    days = [0, 1, 2, 3, 4]
    rows = _series("a", days, [0.4] * 5) + _series("b", days, [1.0, 0.5, 0.3, 0.9, 0.2])

    pair = build_strategy_correlation_report(rows).pair("a", "b")

    assert pair is not None
    assert pair.correlation is None
    assert pair.notes == (CORRELATION_NOTE_CONSTANT_SERIES,)


def test_undated_cycles_are_declared() -> None:
    days = [0, 1, 2, 3, 4]
    rows = _series("a", days, [1.0, 0.5, 0.3, 0.9, 0.2]) + _series(
        "b", days, [0.2, 0.9, 0.3, 0.5, 1.0]
    )
    extra = _cycle("a", 99, 5, 0.6)
    extra.pop("closedAt", None)
    rows.append(extra)

    report = build_strategy_correlation_report(rows)

    assert "undated_cycles" in report.notes
    assert report.pair("a", "b") is not None


# ── Utilidades declaradas ───────────────────────────────────────────────────────────


def test_pearson_correlation_declares_its_edges() -> None:
    assert pearson_correlation([1.0], [1.0]) == (None, (CORRELATION_NOTE_INSUFFICIENT_BUCKETS,))
    assert pearson_correlation([1.0, 1.0], [0.0, 1.0]) == (
        None,
        (CORRELATION_NOTE_CONSTANT_SERIES,),
    )
    value, notes = pearson_correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0])
    assert value == pytest.approx(1.0)
    assert notes == ()


def test_bucket_key_switches_between_day_week_and_month() -> None:
    instant = _BASE

    assert bucket_key(instant, "day") == "2026-01-01"
    assert bucket_key(instant, "week") == "2026-W01"
    assert bucket_key(instant, "month") == "2026-01"
    # Un cubo no soportado cae al defecto declarado en vez de inventar uno.
    assert bucket_key(instant, "hora") == "2026-01-01"
    assert build_strategy_correlation_report(
        [], bucket=CORRELATION_BUCKET_WEEK
    ).bucket == CORRELATION_BUCKET_WEEK


def test_the_minimum_buckets_is_declared() -> None:
    report = build_strategy_correlation_report([], min_buckets=1)

    assert report.min_buckets == 2, "con 2 cubos Pearson es ±1: no es una lectura honesta"
    assert CORRELATION_MIN_BUCKETS_DEFAULT >= 4
