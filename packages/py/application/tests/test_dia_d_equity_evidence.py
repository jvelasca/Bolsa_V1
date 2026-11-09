"""DÍA-D · EVIDENCIA MONETARIA — curva de equity y veredicto umbral a umbral de la política.

Lo que se fija aquí (sin red, sin PostgreSQL):

* Los flujos salen de los **fills** (lado, cantidad, precio), no de una regla de tres sobre R.
* Un fill ilegible **no** es un cero: se declara fuera de la curva.
* Una ventana sin movimiento **no** es «ventana plana»: queda fuera del denominador.
* El veredicto global solo es ``ACCREDITED`` con TODOS los umbrales medidos y cumplidos; un
  umbral sin medir deja ``NOT_ACCREDITED`` y uno incumplido deja ``REFUTED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from bolsa_application.dia_d_equity_evidence import (
    EVIDENCE_ACCREDITED,
    EVIDENCE_NOT_ACCREDITED,
    EVIDENCE_REFUTED,
    build_equity_evidence,
    buy_and_hold_pct,
    evaluate_evidence_policy,
    flows_from_fill_rows,
    holdout_split,
    max_drawdown_pct,
    net_return_pct,
    realized_cost_bps,
    realized_cost_round_trip_bps,
    window_returns,
)


@dataclass(frozen=True, slots=True)
class _Policy:
    """Doble mínimo de ``AccountEvidencePolicy`` (defaults estrictos del contrato)."""

    account_id: str = "acct-test"
    min_windows: int = 30
    min_trades_total: int = 100
    min_positive_window_pct: float = 60.0
    min_net_return_pct: float = 0.0
    max_drawdown_pct: float = 15.0
    min_excess_vs_buy_hold_pct: float = 0.0
    min_commission_bps: float = 5.0
    min_slippage_bps: float = 5.0
    min_spread_bps: float = 2.0

    @property
    def min_round_trip_cost_bps(self) -> float:
        return 2.0 * (self.min_commission_bps + self.min_slippage_bps) + self.min_spread_bps

    def to_dict(self) -> dict[str, Any]:
        return {"accountId": self.account_id}


def _fill(
    side: str,
    quantity: float,
    price: float,
    day: str,
    *,
    cycle: str | None = None,
    mid: float | None = None,
) -> dict[str, Any]:
    return {
        "side": side,
        "quantity": quantity,
        "price": price,
        "createdAt": day,
        "cycleId": cycle,
        "referenceMid": mid,
    }


def _bar(day: str, close: float) -> dict[str, Any]:
    return {"timestamp": f"{day}T00:00:00+00:00", "close": close}


# --- flujos de caja -------------------------------------------------------------------------


def test_buy_leaves_cash_and_sell_brings_it_back() -> None:
    flows, unmeasured = flows_from_fill_rows(
        [
            _fill("buy", 10, 100.0, "2025-01-02", cycle="c1"),
            _fill("sell", 10, 110.0, "2025-01-10", cycle="c1"),
        ]
    )

    assert unmeasured == 0
    assert [flow.amount for flow in flows] == [-1000.0, 1100.0]
    assert [flow.day for flow in flows] == ["2025-01-02", "2025-01-10"]


def test_an_unreadable_fill_is_declared_not_counted_as_zero() -> None:
    flows, unmeasured = flows_from_fill_rows(
        [
            _fill("buy", 10, 100.0, "2025-01-02"),
            {"side": "buy", "quantity": 0, "price": 100.0, "createdAt": "2025-01-03"},
            {"side": "HOLD", "quantity": 1, "price": 100.0, "createdAt": "2025-01-03"},
            {"side": "buy", "quantity": 1, "price": 100.0, "createdAt": ""},
        ]
    )

    assert len(flows) == 1
    assert unmeasured == 3


def test_a_fill_without_instant_falls_back_to_its_cycle_entry_day() -> None:
    flows, unmeasured = flows_from_fill_rows(
        [{"side": "sell", "quantity": 2, "price": 50.0, "cycleId": "c9"}],
        day_by_cycle={"c9": "2025-03-04"},
    )

    assert unmeasured == 0
    assert flows[0].day == "2025-03-04"


def test_decimal_fills_are_measured_not_discarded() -> None:
    """Los fills durables traen ``Decimal``: rechazarlos vaciaba la curva entera."""

    from dataclasses import dataclass
    from decimal import Decimal

    @dataclass(frozen=True)
    class _Row:
        side: str
        quantity: Decimal
        price: Decimal
        reference_mid: Decimal | None
        created_at: Any
        cycle_id: str | None
        instrument_id: str | None = None

    flows, unmeasured = flows_from_fill_rows(
        [
            _Row(
                "buy", Decimal("10"), Decimal("100"), Decimal("99.9"), "2025-01-02T10:00:00Z", "c1"
            ),
            _Row(
                "sell",
                Decimal("10"),
                Decimal("110"),
                Decimal("110.1"),
                "2025-01-09T10:00:00Z",
                "c1",
            ),
        ]
    )

    assert unmeasured == 0
    assert [flow.amount for flow in flows] == [-1000.0, 1100.0]
    assert realized_cost_bps(
        [
            _Row("buy", Decimal("10"), Decimal("100"), Decimal("99.9"), "2025-01-02", "c1"),
        ]
    ) == pytest.approx(abs(100.0 / 99.9 - 1.0) * 10_000.0)


# --- curva, retorno y drawdown --------------------------------------------------------------


def test_net_return_and_drawdown_of_a_known_curve() -> None:
    flows, _ = flows_from_fill_rows(
        [
            _fill("buy", 10, 100.0, "2025-01-02", cycle="c1"),
            _fill("sell", 10, 90.0, "2025-01-06", cycle="c1"),
            _fill("buy", 10, 90.0, "2025-01-08", cycle="c2"),
            _fill("sell", 10, 99.0, "2025-01-15", cycle="c2"),
        ]
    )
    evidence = build_equity_evidence(
        fill_rows=[
            _fill("buy", 10, 100.0, "2025-01-02", cycle="c1"),
            _fill("sell", 10, 90.0, "2025-01-06", cycle="c1"),
            _fill("buy", 10, 90.0, "2025-01-08", cycle="c2"),
            _fill("sell", 10, 99.0, "2025-01-15", cycle="c2"),
        ],
        round_trips=[{"symbol": "X"} for _ in range(2)],
        bars_by_symbol={},
        watch=[],
        initial_equity=10_000.0,
    )

    assert flows  # los mismos flujos, por la vía directa
    # 10.000 → 9.000 (el 2) → 9.900 (el 6) → 9.000 (el 8) → 9.990 (el 15)
    assert evidence["netReturnPct"] == pytest.approx(-0.1)
    assert evidence["maxDrawdownPct"] == pytest.approx(10.0)
    assert evidence["curvePoints"] == 5
    # v2.101: la base de la curva es un CAMPO declarado, no solo una caveat en prosa.
    assert evidence["curveBasis"] == "realized_cash"
    assert "NO de la cartera" in evidence["curveBasisNote"]


def test_curve_without_flows_cannot_be_measured() -> None:
    evidence = build_equity_evidence(
        fill_rows=[],
        round_trips=[],
        bars_by_symbol={},
        watch=["X"],
        initial_equity=10_000.0,
    )

    assert evidence["netReturnPct"] is None
    assert evidence["maxDrawdownPct"] is None
    assert evidence["curve"] == []
    assert any("netReturnPct" in item for item in evidence["notMeasured"])


def test_unmeasurable_initial_equity_yields_no_curve() -> None:
    assert net_return_pct([]) is None
    assert max_drawdown_pct([("2025-01-02", 100.0)]) is None


# --- ventanas -------------------------------------------------------------------------------


def test_windows_without_movement_are_not_counted_as_flat() -> None:
    curve = [
        ("2025-01-02", 10_000.0),
        ("2025-01-03", 10_100.0),  # +100 → positiva
        ("2025-01-06", 10_100.0),  # sin cambio → NO medida
        ("2025-01-07", 9_900.0),  # negativa
        ("2025-01-08", 10_300.0),  # positiva
    ]

    windows = window_returns(curve, granularity="day")

    assert windows["measuredWindows"] == 3
    assert windows["positiveWindows"] == 2
    assert windows["negativeWindows"] == 1
    assert round(windows["positivePct"], 2) == round(200 / 3, 2)


def test_window_pct_is_none_when_nothing_moved() -> None:
    windows = window_returns([("2025-01-02", 10_000.0), ("2025-01-03", 10_000.0)])

    assert windows["measuredWindows"] == 0
    assert windows["positivePct"] is None


def test_year_granularity_buckets_by_year() -> None:
    curve = [
        ("2024-12-30", 10_000.0),
        ("2024-12-31", 10_500.0),
        ("2025-01-02", 10_500.0),
        ("2025-06-02", 9_500.0),
    ]

    yearly = window_returns(curve, granularity="year")

    assert yearly["measuredWindows"] == 2
    assert yearly["positiveWindows"] == 1
    assert yearly["negativeWindows"] == 1


# --- benchmark ------------------------------------------------------------------------------


def test_buy_and_hold_is_equal_weight_and_needs_both_ends() -> None:
    bars = {
        "A": [_bar("2025-01-02", 100.0), _bar("2025-01-10", 110.0)],
        "B": [_bar("2025-01-02", 200.0), _bar("2025-01-10", 180.0)],
        # C no tiene barra al final: no se promedia a medias.
        "C": [_bar("2025-01-02", 50.0), _bar("2025-01-07", 500.0)],
    }

    benchmark = buy_and_hold_pct(
        bars_by_symbol=bars, watch=["A", "B", "C"], start_day="2025-01-02", end_day="2025-01-10"
    )

    assert benchmark["symbolsMeasured"] == 2
    assert benchmark["symbolsRequested"] == 3
    assert benchmark["pct"] == pytest.approx((10.0 + (-10.0)) / 2)


def test_buy_and_hold_without_extremes_is_declared_not_zero() -> None:
    benchmark = buy_and_hold_pct(
        bars_by_symbol={"A": [_bar("2025-01-05", 100.0)]},
        watch=["A"],
        start_day="2025-01-02",
        end_day="2025-01-10",
    )

    assert benchmark["pct"] is None
    assert benchmark["reason"] == "sin_barras_en_los_extremos"


# --- holdout y coste ------------------------------------------------------------------------


def test_holdout_split_reserves_the_last_days() -> None:
    days = [f"2025-01-{day:02d}" for day in range(1, 11)]

    split = holdout_split(days, holdout_pct=30.0)

    assert split["outOfSampleDays"] == 3
    assert split["inSampleDays"] == 7
    assert split["cutDay"] == "2025-01-08"


def test_realized_cost_is_none_when_no_fill_declares_a_mid() -> None:
    assert realized_cost_bps([_fill("buy", 1, 100.0, "2025-01-02")]) is None
    assert round(realized_cost_bps([_fill("buy", 1, 100.1, "2025-01-02", mid=100.0)]), 1) == 10.0


def test_round_trip_cost_doubles_the_per_side_friction() -> None:
    """El umbral de la política es ida+vuelta: comparar el per-side lo dejaba a la mitad."""

    rows = [
        _fill("buy", 10, 100 * (1 + 12.71 / 10_000), "2025-01-02", mid=100.0),
        _fill("sell", 10, 100 * (1 - 12.71 / 10_000), "2025-01-10", mid=100.0),
    ]

    per_side = realized_cost_bps(rows)
    round_trip = realized_cost_round_trip_bps(rows)

    assert per_side == pytest.approx(12.71, abs=1e-6)
    assert round_trip == pytest.approx(25.42, abs=1e-6)


def test_round_trip_cost_adds_a_declared_commission_per_side() -> None:
    rows = [_fill("buy", 1, 100.1, "2025-01-02", mid=100.0)]

    # 10 bps de fricción por lado + 10 bps de comisión por lado ⇒ 40 bps ida+vuelta.
    assert realized_cost_round_trip_bps(rows, commission_bps_per_side=10) == pytest.approx(40.0)
    # Si la comisión YA viaja dentro del precio, sumarla otra vez la contaría dos veces.
    assert realized_cost_round_trip_bps(
        rows, commission_bps_per_side=10, commission_in_price=True
    ) == pytest.approx(20.0)


def test_round_trip_cost_is_none_without_a_price_measurement() -> None:
    assert realized_cost_round_trip_bps([_fill("buy", 1, 100.0, "2025-01-02")]) is None
    assert (
        realized_cost_round_trip_bps(
            [_fill("buy", 1, 100.0, "2025-01-02")], commission_bps_per_side=10
        )
        is None
    )


# --- veredicto ------------------------------------------------------------------------------


def _evaluate(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "measured_windows": 100,
        "measured_trades": 200,
        "positive_window_pct": 70.0,
        "net_return": 5.0,
        "drawdown": 10.0,
        "excess_vs_buy_hold": 2.0,
        "realized_cost_round_trip_bps": 30.0,
        "policy": _Policy(),
    }
    base.update(overrides)
    return evaluate_evidence_policy(**base)


def test_all_thresholds_met_is_accredited() -> None:
    evaluation = _evaluate()

    assert evaluation["verdict"] == EVIDENCE_ACCREDITED
    assert evaluation["failed"] == []
    assert evaluation["notMeasured"] == []


def test_one_failed_threshold_refutes_the_evidence() -> None:
    evaluation = _evaluate(net_return=-1.0)

    assert evaluation["verdict"] == EVIDENCE_REFUTED
    assert evaluation["failed"] == ["minNetReturnPct"]


def test_drawdown_is_a_ceiling_not_a_floor() -> None:
    assert _evaluate(drawdown=15.0)["verdict"] == EVIDENCE_ACCREDITED
    assert _evaluate(drawdown=15.1)["verdict"] == EVIDENCE_REFUTED


def test_an_unmeasured_threshold_never_becomes_an_approval() -> None:
    evaluation = _evaluate(excess_vs_buy_hold=None)

    assert evaluation["verdict"] == EVIDENCE_NOT_ACCREDITED
    assert evaluation["notMeasured"] == ["minExcessVsBuyHoldPct"]


def test_a_realized_cost_below_the_floor_fails() -> None:
    # La política exige 22 bps ida+vuelta: 20 bps medidos NO pasan.
    evaluation = _evaluate(realized_cost_round_trip_bps=20.0)

    assert evaluation["verdict"] == EVIDENCE_REFUTED
    assert evaluation["failed"] == ["minRoundTripCostBps"]


def test_the_round_trip_floor_is_measured_in_round_trip_units() -> None:
    """12,71 bps por lado son 25,42 ida+vuelta: el umbral de 22 bps PASA."""

    evaluation = _evaluate(realized_cost_round_trip_bps=25.42)

    assert evaluation["failed"] == []
    assert evaluation["verdict"] == EVIDENCE_ACCREDITED


def test_build_attaches_the_evaluation_and_declares_the_gaps() -> None:
    fill_rows = [
        _fill("buy", 10, 100.0, "2025-01-02", cycle="c1", mid=100.0),
        _fill("sell", 10, 101.0, "2025-01-10", cycle="c1", mid=100.9),
    ]
    evidence = build_equity_evidence(
        fill_rows=fill_rows,
        round_trips=[{"symbol": "A", "entryDay": "2025-01-02", "exitDay": "2025-01-10"}],
        bars_by_symbol={"A": [_bar("2025-01-02", 100.0), _bar("2025-01-10", 120.0)]},
        watch=["A"],
        initial_equity=10_000.0,
        holdout_pct=30.0,
        policy=_Policy(),
    )

    evaluation = evidence["policyEvaluation"]
    # Una sola operación y tres ventanas incumplen sus mínimos ⇒ REFUTED.
    assert evaluation["verdict"] == EVIDENCE_REFUTED
    measured = {check["name"]: check["verdict"] for check in evaluation["checks"]}
    assert measured["minNetReturnPct"] == "PASS"
    assert measured["maxDrawdownPct"] == "PASS"
    assert measured["minTradesTotal"] == "FAIL"
    assert measured["minWindows"] == "FAIL"
    # El benchmark SÍ se midió: +20 % comprar y mantener contra +0,1 % de la cuenta.
    assert evidence["buyHold"]["excessPct"] == pytest.approx(0.1 - 20.0)
    assert measured["minExcessVsBuyHoldPct"] == "FAIL"
    assert evidence["holdout"]["outOfSampleDays"] >= 0
