"""AutoPortfolioSnapshot — estado canónico único (AUTO 2.0 · P0)."""

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    DATA_FRESH,
    DATA_STALE,
    PortfolioPosition,
    aggregate_exposure,
    build_auto_portfolio_snapshot,
)


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
        open_orders=1,
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
