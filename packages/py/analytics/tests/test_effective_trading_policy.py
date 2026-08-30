"""EffectiveTradingPolicy — encaje vs cartera (V1.30)."""

from bolsa_analytics.cognitive.effective_trading_policy import (
    effective_max_sector_exposure_pct,
    format_portfolio_fit_preview,
    resolve_effective_trading_policy,
)
from bolsa_analytics.cognitive.trading_policy_templates import MODERATE_POLICY


def test_resolve_effective_trading_policy_fallback_moderate() -> None:
    policy = resolve_effective_trading_policy(None)
    assert policy.template_id == "moderate"
    assert policy.exposure.max_sector_exposure_pct == 30.0


def test_effective_max_sector_by_template() -> None:
    assert effective_max_sector_exposure_pct("conservative") == 20.0
    assert effective_max_sector_exposure_pct("aggressive_swing") == 40.0


def test_format_portfolio_fit_preview() -> None:
    text = format_portfolio_fit_preview(MODERATE_POLICY)
    assert "max sector 30%" in text
    assert "max posición 12%" in text
