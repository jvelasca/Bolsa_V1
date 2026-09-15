"""PortfolioDecisionEngine — decisión operativa con vetos fail-closed (AUTO 2.0 · P0)."""

from bolsa_analytics.cognitive.auto_portfolio_snapshot import (
    DATA_FRESH,
    DATA_STALE,
    PortfolioPosition,
    build_auto_portfolio_snapshot,
)
from bolsa_analytics.cognitive.opportunity_ranker import score_opportunity
from bolsa_analytics.cognitive.risk_allocator import RiskAllocatorConfig
from bolsa_application.portfolio_decision_engine import (
    PortfolioDecisionConfig,
    decide_portfolio,
)


def _fresh_snapshot(**overrides: object) -> object:
    base: dict[str, object] = {
        "account_id": "acct-1",
        "capital": 100_000.0,
        "cash": 80_000.0,
        "equity": 100_000.0,
        "buying_power": 80_000.0,
        "risk_used": 500.0,
        "risk_budget": 2_000.0,
        "data_freshness": DATA_FRESH,
    }
    base.update(overrides)
    return build_auto_portfolio_snapshot(**base)


def _score(combined: float) -> object:
    # Todos los componentes al mismo valor ⇒ combined = value × (suma pesos = 1.0).
    return score_opportunity(
        "AAPL",
        edge=combined,
        robustness=combined,
        regime_fit=combined,
        momentum=combined,
        liquidity=combined,
        risk_reward=combined,
        execution_quality=combined,
    )


def test_approved_entry_builds_trade_plan() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        direction="long",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
        decision_id="dec-1",
    )
    assert decision.approved is True
    assert decision.action == "ENTRY"
    assert decision.reason_codes == ("approved",)
    assert decision.is_no_trade is False
    assert decision.trade_plan is not None
    assert decision.trade_plan.status == "TRIGGERED"
    assert decision.trade_plan.direction == "long"
    # stop ATR 1.5*2 = 3 ⇒ distance 3; risk_remaining 1500 pero max_risk_per_trade_pct
    # 1% de 100k = 1000 ⇒ risk_amount 1000 ⇒ qty 333.33, acotado por max_position_pct
    # 20% = 20 000€ ⇒ 200 shares.
    assert decision.trade_plan.quantity == 200.0
    assert decision.trade_plan.risk_amount == 1000.0
    assert decision.trade_plan.structural_stop == 97.0
    assert decision.trade_plan.target1 == 103.0
    assert decision.trade_plan.target2 == 106.0


def test_approved_entry_risk_sizing_without_position_cap() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        direction="long",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
        config=PortfolioDecisionConfig(
            min_edge=0.5,
            # max_risk_per_trade_pct 1.5% y max_position_pct 100% para ver el sizing puro.
            # risk_budget restante = 1500; min(1500, 1.5%*100k=1500) = 1500 ⇒ qty 500.
            allocator=RiskAllocatorConfig(
                max_risk_per_trade_pct=1.5,
                max_position_pct=100.0,
                max_position_value=None,
            ),
        ),
    )
    assert decision.approved is True
    assert decision.trade_plan.quantity == 500.0


def test_stale_data_blocks() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(data_freshness=DATA_STALE),
        regime="BULL_TREND",
    )
    assert decision.approved is False
    assert "stale_data" in decision.reason_codes
    assert decision.is_no_trade is True


def test_position_exists_holds() -> None:
    snap = _fresh_snapshot(
        positions=[PortfolioPosition("AAPL", 10.0, market_value=10_000.0)]
    )
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=snap,
        regime="BULL_TREND",
    )
    assert decision.action == "HOLD"
    assert "position_exists" in decision.reason_codes


def test_regime_invalid_blocks() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="UNKNOWN",
    )
    assert "regime_invalid" in decision.reason_codes


def test_bear_trend_blocks_new_long() -> None:
    """El gate es DIRECCIONAL: no se abre un LONG en tendencia bajista confirmada."""
    decision = decide_portfolio(
        instrument_id="AAPL",
        direction="long",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BEAR_TREND",
    )
    assert decision.action == "HOLD"
    assert decision.reason_codes == ("regime_invalid",)


def test_liquidity_insufficient_blocks() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
        liquidity_notional=0.0,
    )
    assert "liquidity_insufficient" in decision.reason_codes


def test_edge_below_threshold_blocks() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.2),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
    )
    assert "edge_below_threshold" in decision.reason_codes


def test_risk_budget_exhausted_blocks() -> None:
    snap = _fresh_snapshot(risk_used=2_000.0, risk_budget=2_000.0)
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=snap,
        regime="BULL_TREND",
    )
    assert "risk_budget_exceeded" in decision.reason_codes


def test_correlation_conflict_blocks() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
        correlation_with_portfolio=0.85,
        config=PortfolioDecisionConfig(max_correlation=0.7),
    )
    assert "correlation_conflict" in decision.reason_codes


def test_sector_concentration_blocks() -> None:
    # AAPL (Tech) proposal + MSFT (Tech) ya abierta supera max_sector_pct 50%.
    snap = _fresh_snapshot(
        positions=[PortfolioPosition("MSFT", 10.0, market_value=45_000.0, sector="Technology")]
    )
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        stop_price=96.0,
        opportunity_score=_score(0.9),
        snapshot=snap,
        regime="BULL_TREND",
        sector="Technology",
        config=PortfolioDecisionConfig(max_sector_pct=50.0),
    )
    assert "concentration_exceeded" in decision.reason_codes


def test_risk_reward_below_threshold_blocks() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        stop_price=96.0,
        target_price=102.0,  # reward 2 / risk 4 = 0.5 < 1.0
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
    )
    assert "risk_reward_below_threshold" in decision.reason_codes


def test_no_entry_price_blocks() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=None,
        atr=2.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
    )
    assert decision.approved is False


def test_decision_to_dict_shape() -> None:
    decision = decide_portfolio(
        instrument_id="AAPL",
        entry_price=100.0,
        stop_price=96.0,
        opportunity_score=_score(0.8),
        snapshot=_fresh_snapshot(),
        regime="BULL_TREND",
        decision_id="dec-1",
    )
    d = decision.to_dict()
    assert d["decisionId"] == "dec-1"
    assert d["approved"] is True
    assert d["tradePlan"]["structuralStop"] == 96.0
    assert d["allocation"]["quantity"] > 0
