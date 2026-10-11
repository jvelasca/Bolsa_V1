"""`§8-a` — pruebas del reporte financiero OOS por `(estrategia × instrumento)`.

Muerden: el coste resta (neto ≤ bruto), la sensibilidad a costes es monótona, el contrato
de honestidad (sin muestra ⇒ `None`, nunca `0`), PF `None` sin pérdidas (nunca `∞`),
Sharpe `None` con varianza nula, la agrupación por `(versión, símbolo)`, el determinismo y
la adaptación de las filas del replay.
"""

from __future__ import annotations

from bolsa_application.oos_finance import (
    GROUP_AGGREGATE_KEY,
    CostOverlay,
    OosFill,
    build_oos_finance_report,
    fills_from_replay,
)


def _fill(
    symbol: str,
    side: str,
    qty: float,
    price: float,
    *,
    version: str | None = "ex-a",
) -> OosFill:
    return OosFill(
        symbol=symbol,
        strategy_version=version,
        side=side,
        quantity=qty,
        price=price,
    )


def _one_round_trip(entry: float, exit_: float, qty: float = 10.0) -> list[OosFill]:
    return [_fill("ACS", "buy", qty, entry), _fill("ACS", "sell", qty, exit_)]


def test_net_never_exceeds_gross_and_zero_cost_matches() -> None:
    # comisión 10 bps + slippage 5 bps.
    report = build_oos_finance_report(_one_round_trip(100.0, 110.0), min_trades=1)
    group = report.groups[0][1]
    assert group.gross_return_pct is not None and group.net_return_pct is not None
    assert group.gross_return_pct == 10.0
    # coste = 1000 * 15/10_000 = 1.5 ⇒ neto = 98.5 / 1000 = 9.85%.
    assert group.net_return_pct < group.gross_return_pct
    assert group.net_return_pct == 9.85
    assert group.commission_paid == 1.0
    assert group.slippage_paid == 0.5

    free = build_oos_finance_report(
        _one_round_trip(100.0, 110.0), commission_bps=0.0, slippage_bps=0.0, min_trades=1
    )
    free_group = free.groups[0][1]
    assert free_group.net_return_pct == free_group.gross_return_pct == 10.0


def test_cost_sensitivity_is_monotonic() -> None:
    report = build_oos_finance_report(
        _one_round_trip(100.0, 110.0), min_trades=1, stress_multiplier=3.0
    )
    group = report.groups[0][1]
    assert group.net_return_pct is not None
    assert group.net_return_pct_at_stress is not None
    assert group.net_return_pct_at_stress < group.net_return_pct
    # 3× coste = 4.5 ⇒ 95.5 / 1000 = 9.55%.
    assert group.net_return_pct_at_stress == 9.55


def test_below_min_trades_is_none_never_zero() -> None:
    report = build_oos_finance_report(_one_round_trip(100.0, 110.0), min_trades=10)
    group = report.groups[0][1]
    assert group.trades == 1
    assert group.gross_return_pct is None
    assert group.net_return_pct is None
    assert group.net_return_pct_at_stress is None
    assert group.max_drawdown_pct is None
    assert group.hit_rate is None
    assert group.profit_factor is None
    assert group.sharpe is None
    assert report.aggregate.net_return_pct is None
    # El hueco se declara (nunca se rellena con un 0 que finja medición).
    assert any("min_trades" in gap for gap in report.unmeasured)
    assert report.point_citable is False


def test_profit_factor_none_without_losses() -> None:
    # Dos ganadores ⇒ sin pérdidas ⇒ PF indefinido (None, nunca inf).
    fills = _one_round_trip(100.0, 110.0) + _one_round_trip(100.0, 120.0)
    report = build_oos_finance_report(fills, min_trades=1)
    group = report.groups[0][1]
    assert group.profit_factor is None
    assert group.hit_rate == 1.0
    assert any("profit factor indefinido" in gap for gap in report.unmeasured)


def test_profit_factor_and_hit_rate_with_mix() -> None:
    fills = _one_round_trip(100.0, 120.0) + _one_round_trip(100.0, 90.0)
    report = build_oos_finance_report(
        fills, commission_bps=0.0, slippage_bps=0.0, min_trades=1
    )
    group = report.groups[0][1]
    assert group.trades == 2
    assert group.hit_rate == 0.5
    # ganancia 200, pérdida 100 ⇒ PF = 2.0.
    assert group.profit_factor == 2.0
    # drawdown neto: pico 200, caída a 100 sobre 2000 de capital ⇒ 5%.
    assert group.max_drawdown_pct == 5.0


def test_sharpe_none_with_zero_variance() -> None:
    # Dos round-trips con retorno idéntico ⇒ desviación 0 ⇒ Sharpe sin dato.
    fills = _one_round_trip(100.0, 110.0) + _one_round_trip(50.0, 55.0)
    report = build_oos_finance_report(fills, min_trades=1)
    group = report.groups[0][1]
    assert group.sharpe is None
    assert any("sharpe sin dato" in gap for gap in report.unmeasured)


def test_sharpe_when_applicable() -> None:
    fills = _one_round_trip(100.0, 110.0) + _one_round_trip(100.0, 130.0)
    report = build_oos_finance_report(fills, commission_bps=0.0, slippage_bps=0.0, min_trades=2)
    group = report.groups[0][1]
    assert group.sharpe is not None and group.sharpe > 0


def test_grouping_by_strategy_and_symbol() -> None:
    fills = [
        _fill("ACS", "buy", 10, 100, version="ex-a"),
        _fill("ACS", "sell", 10, 110, version="ex-a"),
        _fill("ACS", "buy", 10, 100, version="ex-b"),
        _fill("ACS", "sell", 10, 130, version="ex-b"),
        _fill("ITX", "buy", 10, 50, version="ex-a"),
        _fill("ITX", "sell", 10, 45, version="ex-a"),
    ]
    report = build_oos_finance_report(fills, commission_bps=0.0, slippage_bps=0.0, min_trades=1)
    keys = [key for key, _ in report.groups]
    assert keys == [("ex-a", "ACS"), ("ex-a", "ITX"), ("ex-b", "ACS")]
    by_key = dict(report.groups)
    assert by_key[("ex-a", "ACS")].trades == 1
    assert by_key[("ex-a", "ITX")].net_return_pct is not None
    assert by_key[("ex-a", "ITX")].net_return_pct < 0
    assert by_key[("ex-b", "ACS")].trades == 1
    # El agregado cubre todos los grupos.
    assert report.aggregate.trades == 3
    assert GROUP_AGGREGATE_KEY == ("__ALL__", "__ALL__")


def test_deterministic_and_stable_order() -> None:
    acs = [_fill("ACS", "buy", 10, 100, version="ex-a"), _fill("ACS", "sell", 10, 110, version="ex-a")]
    itx = [_fill("ITX", "buy", 10, 50, version="ex-a"), _fill("ITX", "sell", 10, 55, version="ex-a")]
    first = build_oos_finance_report(acs + itx, min_trades=1).to_dict()
    # Idempotente: la misma entrada ⇒ el mismo reporte.
    assert first == build_oos_finance_report(acs + itx, min_trades=1).to_dict()
    # Orden estable: si se intercambia el ORDEN de los grupos (conservando el FIFO de cada
    # uno), el reporte queda idéntico — el agregado es la unión en orden de clave.
    assert first == build_oos_finance_report(itx + acs, min_trades=1).to_dict()
    keys = [(g["strategyVersion"], g["symbol"]) for g in first["groups"]]
    assert keys == [("ex-a", "ACS"), ("ex-a", "ITX")]
    assert first["aggregate"]["trades"] == 2


def test_cost_overlay_scales_and_rejects_negative() -> None:
    overlay = CostOverlay(commission_bps=10.0, slippage_bps=5.0)
    assert overlay.scaled(2.0).bps() == 30.0
    ok = True
    try:
        CostOverlay(commission_bps=-1.0)
    except ValueError:
        ok = False
    assert ok is False


def test_fills_from_replay_adapts_and_skips_garbage() -> None:
    rows = [
        {"symbol": "ACS", "side": "BUY", "quantity": 10, "price": 100, "strategyVersion": "v1"},
        {"symbol": "ACS", "side": "sell", "quantity": 10, "price": 110, "strategyVersion": "v1"},
        {"symbol": "ACS", "side": "sell"},  # ilegible ⇒ se descarta.
        "no-es-un-dict",
        {"symbol": "ITX", "side": "buy", "quantity": 1, "price": 2},  # sin versión.
    ]
    fills = fills_from_replay(rows)
    assert len(fills) == 3
    assert fills[0].side == "buy"  # ``fills_from_replay`` normaliza el lado a minúsculas.
    report = build_oos_finance_report(fills, min_trades=1)
    keys = [key for key, _ in report.groups]
    assert ("v1", "ACS") in keys
    assert (None, "ITX") in keys


def test_intraday_sell_without_open_is_ignored() -> None:
    # Venta sin compra previa: no se fabrica un round-trip en corto.
    report = build_oos_finance_report([_fill("ACS", "sell", 10, 110)], min_trades=1)
    assert report.aggregate.trades == 0
