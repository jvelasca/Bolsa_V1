"""AutoPortfolioSnapshot — estado canónico único (AUTO 2.0 · P0)."""

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    DATA_FRESH,
    DATA_STALE,
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    PortfolioPosition,
    aggregate_exposure,
    build_auto_portfolio_snapshot,
)
from bolsa_analytics.cognitive.measurement import MEASUREMENT_PARTIAL
from bolsa_analytics.cognitive.open_order import build_open_order


def test_build_snapshot_canonical_fields() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        capital=100_000.0,
        cash=61_300.0,
        equity=100_420.0,
        buying_power=61_300.0,
        positions=[
            PortfolioPosition("AAPL", 37.0, market_value=22_000.0, sector="Technology"),
            PortfolioPosition("MSFT", 20.0, market_value=20_000.0, sector="Technology"),
        ],
        open_orders=(
            build_open_order(
                execution_id="exec-1",
                order_id="ord-1",
                instrument_id="NVDA",
                side="sell",
                quantity=50.0,
                price=120.0,
                sector="Technology",
            ),
        ),
        daily_pnl=420.0,
        realized_pnl=120.0,
        unrealized_pnl=300.0,
        risk_used=1_800.0,
        risk_budget=2_000.0,
        drawdown_pct=-1.2,
        active_strategies=["v42", "v42", "v31"],
        market_regime="BULL_TREND",
        last_reconciliation="clean",
        data_freshness=DATA_FRESH,
        as_of="2026-09-15T09:00:00Z",
    )
    assert snap.account_id == "acct-1"
    assert snap.capital == 100_000.0
    assert snap.risk_used == 1_800.0
    assert snap.risk_remaining == 200.0
    assert snap.data_is_fresh is True
    assert snap.active_strategies == ("v42", "v31")
    assert snap.exposure.total_pct is not None
    # AAPL 22k + MSFT 20k = 42k sobre 100.42k equity.
    assert round(snap.exposure.total_pct, 1) == 41.8
    d = snap.to_dict()
    assert d["riskRemaining"] == 200.0
    assert d["exposure"]["byAsset"]["AAPL"] > 0
    assert d["activeStrategies"] == ["v42", "v31"]
    # V2.40.4: el libro de órdenes es una tupla, no un contador.
    assert d["openOrderCount"] == 1
    assert d["openOrders"][0]["executionId"] == "exec-1"
    assert d["orderBookMeasurement"] == MEASUREMENT_COMPLETE
    assert d["reservedCash"] == 0.0
    assert d["availableCash"] == 61_300.0


# ── V2.40.4: órdenes pendientes como capital/riesgo comprometido ─────────────


def test_pending_buy_reserves_cash_and_lowers_available() -> None:
    """``cash`` no es lo disponible si hay BUY en vuelo: 50k − 12k = 38k."""
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="NVDA",
        side="buy",
        quantity=100.0,
        price=120.0,
        sector="Technology",
        risk_amount=600.0,
    )
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        cash=50_000.0,
        equity=100_000.0,
        risk_used=500.0,
        risk_budget=2_000.0,
        open_orders=(order,),
    )
    assert snap.open_order_count == 1
    assert snap.reserved_cash == 12_000.0
    assert snap.available_cash == 38_000.0
    assert snap.pending_risk == 600.0
    assert snap.pending_exposure == 12.0
    assert snap.order_book_is_complete is True
    # El riesgo pendiente consume presupuesto aunque no haya posición abierta.
    assert snap.risk_remaining == 900.0


def test_pending_buy_without_risk_is_not_complete() -> None:
    """Un BUY sin riesgo declarado deja el libro a medias ⇒ medición no COMPLETE."""
    riskless = build_open_order(
        execution_id="exec-1",
        instrument_id="NVDA",
        side="buy",
        quantity=100.0,
        price=120.0,
        sector="Technology",
    )
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1", cash=50_000.0, equity=100_000.0, open_orders=(riskless,)
    )
    # Ninguna orden cuantificable del todo ⇒ UNKNOWN (no se puede afirmar la reserva).
    assert snap.order_book_measurement == MEASUREMENT_UNKNOWN
    assert snap.order_book_is_complete is False
    # El riesgo pendiente es un SUELO (0 conocido), no una afirmación de "sin riesgo".
    assert snap.pending_risk == 0.0
    assert snap.reserved_cash == 12_000.0

    quantified = build_open_order(
        execution_id="exec-2",
        instrument_id="MSFT",
        side="buy",
        quantity=10.0,
        price=100.0,
        sector="Technology",
        risk_amount=50.0,
    )
    partial = build_auto_portfolio_snapshot(
        account_id="acct-1",
        cash=50_000.0,
        equity=100_000.0,
        open_orders=(riskless, quantified),
    )
    assert partial.order_book_measurement == MEASUREMENT_PARTIAL
    assert partial.order_book_is_complete is False


def test_pending_buy_without_finance_context_is_unknown() -> None:
    order = build_open_order(execution_id="exec-1", instrument_id="NVDA", side="buy")
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1", cash=50_000.0, equity=100_000.0, open_orders=(order,)
    )
    assert snap.order_book_measurement == MEASUREMENT_UNKNOWN
    assert snap.reserved_cash == 0.0
    assert snap.available_cash == 50_000.0


def test_pending_sell_reserves_qty_not_cash() -> None:
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="AAA",
        side="sell",
        quantity=30.0,
        price=100.0,
        sector="Tech",
    )
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1", cash=50_000.0, equity=100_000.0, open_orders=(order,)
    )
    assert snap.reserved_cash == 0.0
    assert snap.available_cash == 50_000.0
    assert snap.pending_risk == 0.0
    assert snap.pending_exposure == 0.0
    assert snap.open_order_summary.pending_sell_qty == {"AAA": 30.0}
    assert snap.order_book_is_complete is True


def test_empty_order_book_is_complete_and_leaves_cash_untouched() -> None:
    snap = build_auto_portfolio_snapshot(account_id="acct-1", cash=50_000.0)
    assert snap.open_order_count == 0
    assert snap.order_book_measurement == MEASUREMENT_COMPLETE
    assert snap.reserved_cash == 0.0
    assert snap.available_cash == 50_000.0


def test_available_cash_is_none_without_cash() -> None:
    snap = build_auto_portfolio_snapshot(account_id="acct-1")
    assert snap.available_cash is None


def test_open_order_book_measurement_can_be_asserted_explicitly() -> None:
    """El llamante que leyó el libro a medias puede declararlo sin inventar órdenes."""
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1", cash=50_000.0, order_book_measurement=MEASUREMENT_UNKNOWN
    )
    assert snap.order_book_measurement == MEASUREMENT_UNKNOWN
    assert snap.order_book_is_complete is False


def test_risk_remaining_never_negative() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1", risk_used=2_500.0, risk_budget=2_000.0
    )
    assert snap.risk_remaining == 0.0


def test_risk_remaining_none_without_budget() -> None:
    snap = build_auto_portfolio_snapshot(account_id="acct-1", risk_used=500.0)
    assert snap.risk_remaining is None


def test_risk_used_derived_from_positions_when_absent() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[
            PortfolioPosition("AAPL", 10.0, market_value=10_000.0, risk_amount=500.0),
            PortfolioPosition("MSFT", 10.0, market_value=10_000.0, risk_amount=600.0),
        ],
    )
    assert snap.risk_used == 1_100.0
    # Sin riesgo por posición ⇒ risk_used ausente (no se inventa 0).
    snap2 = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[PortfolioPosition("AAPL", 10.0, market_value=10_000.0)],
    )
    assert snap2.risk_used is None


def test_exposure_empty_when_no_equity_and_no_market_values() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        positions=[PortfolioPosition("AAPL", 10.0)],
    )
    assert snap.exposure.total_pct is None
    assert snap.exposure.by_asset == {}
    assert snap.exposure.by_sector == {}


def test_exposure_falls_back_to_market_value_sum() -> None:
    # Sin equity: denominador = suma de valores de mercado (22k), AAPL = 100%.
    breakdown = aggregate_exposure(
        (PortfolioPosition("AAPL", 10.0, market_value=22_000.0, sector="Technology"),),
        equity=None,
    )
    assert breakdown.total_pct == 100.0
    assert breakdown.by_asset == {"AAPL": 100.0}


def test_unknown_sector_grouped() -> None:
    breakdown = aggregate_exposure(
        (
            PortfolioPosition("A", 1.0, market_value=100.0),
            PortfolioPosition("B", 1.0, market_value=100.0),
        ),
        equity=200.0,
    )
    assert breakdown.by_sector == {"<unknown>": 100.0}


def test_invalid_positions_dropped() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[
            PortfolioPosition("AAPL", 10.0, market_value=10_000.0),
            {"quantity": 5.0},  # sin instrumento ⇒ descartada
            "basura",  # forma rara ⇒ descartada
        ],
    )
    assert len(snap.positions) == 1
    assert snap.positions[0].instrument_id == "AAPL"


def test_data_is_fresh_fail_closed() -> None:
    assert build_auto_portfolio_snapshot(account_id="a").data_is_fresh is False
    assert build_auto_portfolio_snapshot(account_id="a", data_freshness=DATA_STALE).data_is_fresh is False
    assert build_auto_portfolio_snapshot(account_id="a", data_freshness=DATA_FRESH).data_is_fresh is True


def test_position_to_dict_roundtrip_coercion() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[{"instrumentId": "AAPL", "quantity": 10, "marketValue": 10_000.0, "sector": "Tech"}],
    )
    assert snap.positions[0].instrument_id == "AAPL"
    assert snap.positions[0].sector == "Tech"


# ── V2.40.4: estado de MEDICIÓN de los agregados ─────────────────────────────


def test_risk_measurement_complete_when_all_declare() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[
            PortfolioPosition("AAPL", 10.0, market_value=10_000.0, risk_amount=500.0),
            PortfolioPosition("MSFT", 10.0, market_value=10_000.0, risk_amount=600.0),
        ],
    )
    assert snap.risk_measurement == MEASUREMENT_COMPLETE
    assert snap.risk_is_complete is True
    assert snap.risk_used == 1_100.0


def test_risk_measurement_partial_when_some_declare() -> None:
    """Con riesgo medible a medias el agregado es un SUELO, no el total."""
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[
            PortfolioPosition("AAPL", 10.0, market_value=10_000.0, risk_amount=500.0),
            PortfolioPosition("MSFT", 10.0, market_value=10_000.0),
        ],
    )
    assert snap.risk_measurement == MEASUREMENT_PARTIAL
    assert snap.risk_is_complete is False


def test_risk_measurement_unknown_when_none_declares() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[PortfolioPosition("AAPL", 10.0, market_value=10_000.0)],
    )
    assert snap.risk_used is None
    assert snap.risk_measurement == MEASUREMENT_UNKNOWN
    assert snap.risk_is_complete is False


def test_risk_measurement_complete_without_positions_or_with_explicit_used() -> None:
    # Sin posiciones no hay nada que medir: el agregado vacío es exacto.
    assert (
        build_auto_portfolio_snapshot(account_id="a").risk_measurement == MEASUREMENT_COMPLETE
    )
    # Un ``risk_used`` explícito es una AFIRMACIÓN del llamante ⇒ medido.
    snap = build_auto_portfolio_snapshot(
        account_id="a", risk_used=500.0, positions=[PortfolioPosition("AAPL", 10.0)]
    )
    assert snap.risk_measurement == MEASUREMENT_COMPLETE


def test_risk_measurement_explicit_override_wins() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="a",
        risk_used=500.0,
        risk_measurement=MEASUREMENT_PARTIAL,
        positions=[PortfolioPosition("AAPL", 10.0)],
    )
    assert snap.risk_measurement == MEASUREMENT_PARTIAL
    # Un valor no canónico se ignora (nunca se publica un estado inventado).
    snap2 = build_auto_portfolio_snapshot(account_id="a", risk_measurement="basura")
    assert snap2.risk_measurement == MEASUREMENT_COMPLETE


def test_exposure_measurement_partial_and_unknown() -> None:
    """La exposición solo es COMPLETE si TODAS las posiciones se pudieron valorar."""
    partial = aggregate_exposure(
        (
            PortfolioPosition("AAPL", 10.0, market_value=10_000.0, sector="Tech"),
            PortfolioPosition("MSFT", 10.0, sector="Tech"),  # sin market_value
        ),
        equity=100_000.0,
    )
    assert partial.measurement == MEASUREMENT_PARTIAL
    assert partial.is_complete is False
    # El número sigue siendo aritmética pura sobre lo valorable (no un cero engañoso).
    assert partial.total_pct == 10.0

    unknown = aggregate_exposure(
        (PortfolioPosition("MSFT", 10.0, sector="Tech"),), equity=100_000.0
    )
    assert unknown.measurement == MEASUREMENT_UNKNOWN
    assert unknown.total_pct is None

    complete = aggregate_exposure(
        (PortfolioPosition("AAPL", 10.0, market_value=10_000.0, sector="Tech"),),
        equity=100_000.0,
    )
    assert complete.measurement == MEASUREMENT_COMPLETE
    assert complete.is_complete is True


def test_exposure_measurement_ignores_zero_quantity_positions() -> None:
    """Una posición cerrada no es "exposición no valorable"."""
    breakdown = aggregate_exposure(
        (
            PortfolioPosition("AAPL", 10.0, market_value=10_000.0, sector="Tech"),
            PortfolioPosition("FLAT", 0.0),
        ),
        equity=100_000.0,
    )
    assert breakdown.measurement == MEASUREMENT_COMPLETE


def test_snapshot_exposure_helper_and_to_dict() -> None:
    snap = build_auto_portfolio_snapshot(
        account_id="acct-1",
        equity=100_000.0,
        positions=[
            PortfolioPosition("AAPL", 10.0, market_value=10_000.0, risk_amount=500.0),
            PortfolioPosition("MSFT", 10.0, risk_amount=600.0),
        ],
    )
    assert snap.exposure_is_complete is False
    d = snap.to_dict()
    assert d["riskMeasurement"] == MEASUREMENT_COMPLETE
    assert d["exposure"]["measurement"] == MEASUREMENT_PARTIAL
