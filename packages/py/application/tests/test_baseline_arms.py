"""Tests de las líneas base falsables (auditoría externa 2026-11-08).

Lo que se clava: los cinco umbrales literales (no pueden moverse tras ver resultados), la
convención per-side/round-trip de los costes, la curva equiponderada, el filtro de régimen
con ejecución al open siguiente y la regla «dato ausente = NOT_MEASURED, jamás 0».
"""

from __future__ import annotations

import pytest

from bolsa_application.baseline_arms import (
    BASELINE_THRESHOLDS,
    BaselineCosts,
    buy_hold_curve,
    evaluate_baseline,
    summarize_curve,
    trend_regime_curve,
)


def _bar(day: str, close: float, *, open_: float | None = None) -> dict[str, float | str]:
    return {
        "timestamp": f"{day}T00:00:00Z",
        "open": close if open_ is None else open_,
        "high": max(close, close if open_ is None else open_),
        "low": min(close, close if open_ is None else open_),
        "close": close,
        "volume": 1_000.0,
    }


def _days(count: int) -> list[str]:
    return [f"2024-01-{index + 1:02d}" for index in range(count)]


class TestThresholdsFrozen:
    def test_limits_are_the_preregistered_literals(self) -> None:
        assert BASELINE_THRESHOLDS == {
            "minNetReturnPct": 0.0,
            "maxDrawdownPct": 15.0,
            "minPositiveWindowPct": 60.0,
            "minExcessVsBuyHoldPct": 0.0,
            "minRoundTripCostBps": 22.0,
        }

    def test_costs_use_per_side_convention_and_round_trip_doubles(self) -> None:
        costs = BaselineCosts(commission_bps=10.0, slippage_bps=5.0, spread_bps=2.0)
        assert costs.per_side_bps == pytest.approx(16.0)
        assert costs.round_trip_bps == pytest.approx(32.0)
        assert costs.round_trip_bps == pytest.approx(2 * costs.per_side_bps)
        assert costs.to_dict()["roundTripBps"] == pytest.approx(32.0)


class TestBuyHoldCurve:
    def test_equal_weight_basket_averages_normalized_returns(self) -> None:
        days = _days(2)
        bars = {
            "AAA": [_bar(days[0], 100.0), _bar(days[1], 200.0)],
            "BBB": [_bar(days[0], 50.0), _bar(days[1], 50.0)],
        }
        curve = buy_hold_curve(bars_by_symbol=bars, watch=["AAA", "BBB"], days=days)
        assert [day for day, _ in curve] == days
        assert curve[0][1] == pytest.approx(100_000.0)
        assert curve[-1][1] == pytest.approx(150_000.0)
        assert summarize_curve(curve)["netReturnPct"] == pytest.approx(50.0)

    def test_symbol_without_bars_is_skipped_not_counted_as_zero(self) -> None:
        days = _days(2)
        bars = {
            "AAA": [_bar(days[0], 100.0), _bar(days[1], 110.0)],
            "SIN-DATOS": [],
        }
        curve = buy_hold_curve(bars_by_symbol=bars, watch=["AAA", "SIN-DATOS"], days=days)
        assert curve[-1][1] == pytest.approx(110_000.0)

    def test_missing_day_forward_fills_last_close(self) -> None:
        days = _days(3)
        bars = {"AAA": [_bar(days[0], 100.0), _bar(days[2], 120.0)]}
        curve = buy_hold_curve(bars_by_symbol=bars, watch=["AAA"], days=days)
        assert [value for _, value in curve] == pytest.approx([100_000.0, 100_000.0, 120_000.0])

    def test_single_bar_is_not_measured(self) -> None:
        days = _days(1)
        bars = {"AAA": [_bar(days[0], 100.0)]}
        curve = buy_hold_curve(bars_by_symbol=bars, watch=["AAA"], days=days)
        assert curve == []
        assert summarize_curve(curve)["netReturnPct"] is None


class TestTrendRegimeCurve:
    def test_rising_market_holds_long_and_beats_cash(self) -> None:
        days = _days(30)
        bars = {"AAA": [_bar(day, 100.0 + index) for index, day in enumerate(days)]}
        curve, meta = trend_regime_curve(
            bars_by_symbol=bars, watch=["AAA"], days=days, sma_window=5
        )
        assert meta["smaWindow"] == 5
        assert meta["unmeasurableSignalDays"] == 4
        assert meta["realizedCostBps"] == pytest.approx(32.0)
        assert summarize_curve(curve)["netReturnPct"] > 0

    def test_falling_market_stays_in_cash_and_does_not_fake_returns(self) -> None:
        days = _days(30)
        bars = {"AAA": [_bar(day, 200.0 - index) for index, day in enumerate(days)]}
        curve, meta = trend_regime_curve(
            bars_by_symbol=bars, watch=["AAA"], days=days, sma_window=5
        )
        assert meta["roundTrips"] == 0
        summary = summarize_curve(curve)
        assert summary["netReturnPct"] == pytest.approx(0.0)
        assert summary["maxDrawdownPct"] == pytest.approx(0.0)
        # Sin movimiento no hay ventana medida: no es "100 % de ventanas positivas".
        assert summary["positiveWindowPct"] is None

    def test_execution_uses_next_open_not_the_signal_close(self) -> None:
        days = _days(4)
        # La señal se dispara al cierre del día 3 (120 > SMA2=110); la compra va al open del
        # día 4 (150), no al cierre que la disparó ni al cierre final (200).
        bars = {
            "AAA": [
                _bar(days[0], 100.0, open_=100.0),
                _bar(days[1], 100.0, open_=100.0),
                _bar(days[2], 120.0, open_=100.0),
                _bar(days[3], 200.0, open_=150.0),
            ]
        }
        curve, meta = trend_regime_curve(
            bars_by_symbol=bars, watch=["AAA"], days=days, sma_window=2, initial_equity=100_000.0
        )
        assert meta["roundTrips"] == 0
        expected = 100_000.0 * (1.0 - BaselineCosts().per_side_bps / 10_000.0) * 200.0 / 150.0
        assert curve[-1][1] == pytest.approx(expected, rel=1e-9)


class TestEvaluateBaseline:
    def _summary(self, **overrides: float | None) -> dict[str, float | None]:
        base: dict[str, float | None] = {
            "netReturnPct": 12.0,
            "maxDrawdownPct": 9.0,
            "positiveWindowPct": 65.0,
            "excessVsBuyHoldPct": 2.0,
        }
        base.update(overrides)
        return base

    def test_all_five_measured_and_passing_accredits(self) -> None:
        result = evaluate_baseline(self._summary(), realized_cost_round_trip_bps=32.0)
        assert result["verdict"] == "ACCREDITED"
        assert result["failed"] == []
        assert result["notMeasured"] == []

    def test_any_failure_refutes(self) -> None:
        result = evaluate_baseline(
            self._summary(netReturnPct=-1.0), realized_cost_round_trip_bps=32.0
        )
        assert result["verdict"] == "REFUTED"
        assert result["failed"] == ["minNetReturnPct"]

    def test_drawdown_limit_is_an_upper_bound(self) -> None:
        assert (
            evaluate_baseline(
                self._summary(maxDrawdownPct=15.0), realized_cost_round_trip_bps=32.0
            )["verdict"]
            == "ACCREDITED"
        )
        assert (
            evaluate_baseline(
                self._summary(maxDrawdownPct=15.01), realized_cost_round_trip_bps=32.0
            )["verdict"]
            == "REFUTED"
        )

    def test_unmeasured_cost_never_passes(self) -> None:
        result = evaluate_baseline(self._summary(), realized_cost_round_trip_bps=None)
        assert result["verdict"] == "NOT_ACCREDITED"
        assert result["notMeasured"] == ["minRoundTripCostBps"]

    def test_unmeasured_window_never_counts_as_zero(self) -> None:
        result = evaluate_baseline(
            self._summary(positiveWindowPct=None), realized_cost_round_trip_bps=32.0
        )
        assert result["verdict"] == "NOT_ACCREDITED"
        assert result["notMeasured"] == ["minPositiveWindowPct"]

    def test_cheap_execution_fails_the_cost_floor(self) -> None:
        result = evaluate_baseline(self._summary(), realized_cost_round_trip_bps=12.7)
        assert result["verdict"] == "REFUTED"
        assert result["failed"] == ["minRoundTripCostBps"]
