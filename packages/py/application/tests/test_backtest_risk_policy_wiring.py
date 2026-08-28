"""Lab — BacktestRiskPolicy alineada a TradingPolicy (deuda relevos V1.25–V1.26)."""

from bolsa_analytics.cognitive.trading_policy_templates import (
    CONSERVATIVE_POLICY,
    MODERATE_POLICY,
)
from bolsa_application.backtests import backtest_risk_policy_from_trading_policy


def test_moderate_maps_one_pct() -> None:
    rp = backtest_risk_policy_from_trading_policy(MODERATE_POLICY)
    assert rp.max_risk_per_trade_pct == 1.0
    assert rp.stop_loss_pct == 5.0


def test_conservative_maps_half_pct() -> None:
    rp = backtest_risk_policy_from_trading_policy(CONSERVATIVE_POLICY)
    assert rp.max_risk_per_trade_pct == 0.5


def test_default_is_moderate() -> None:
    rp = backtest_risk_policy_from_trading_policy()
    assert rp.max_risk_per_trade_pct == MODERATE_POLICY.risk.max_risk_per_trade_pct
