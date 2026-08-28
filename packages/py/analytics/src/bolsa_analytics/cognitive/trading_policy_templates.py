"""Plantillas base ART-TRADING-POLICY (RFC-008 D1)."""

from __future__ import annotations

from copy import deepcopy

from bolsa_analytics.cognitive.trading_policy import (
    BlackoutConstraints,
    EvidenceThresholds,
    ExecutionConstraints,
    ExposureConstraints,
    HorizonConstraints,
    RiskConstraints,
    TradingPolicy,
    UniverseConstraints,
)
from bolsa_analytics.cognitive.exit_policy import (
    AGGRESSIVE_SWING_EXIT_POLICY,
    CONSERVATIVE_EXIT_POLICY,
    MODERATE_EXIT_POLICY,
)

_NOW = "2026-07-22T00:00:00.000Z"


CONSERVATIVE_POLICY = TradingPolicy(
    policy_id="POL-CONSERVATIVE-V1",
    version="1.0.0",
    template_id="conservative",
    name="Conservador",
    description="Preservación de capital: large-cap líquidas, sin apalancamiento, blackouts estrictos.",
    universe=UniverseConstraints(
        allowed_asset_classes=("equities",),
        allowed_universes=("sp500", "nasdaq100"),
        min_market_cap_usd=10_000_000_000,
        min_average_daily_volume_usd=20_000_000,
        max_spread_bps=15,
        min_atr_pct=0.3,
        max_atr_pct=4,
        excluded_sectors=("biotech",),
        excluded_tickers=(),
        allow_shorting=False,
        allow_otc=False,
        allow_crypto=False,
        allow_cfds=False,
    ),
    exposure=ExposureConstraints(
        max_leverage=1.0,
        max_open_positions=8,
        max_portfolio_concentration_pct=8.0,
        max_sector_exposure_pct=20.0,
        max_correlation_with_open_positions=0.65,
    ),
    risk=RiskConstraints(
        max_risk_per_trade_pct=0.5,
        hard_daily_drawdown_limit_pct=1.5,
        hard_weekly_drawdown_limit_pct=3.0,
        hard_max_drawdown_limit_pct=8.0,
        min_reward_to_risk_ratio=2.5,
        stop_loss_required=True,
        min_take_profit_r_multiple=2.0,
    ),
    blackouts=BlackoutConstraints(
        block_pre_earnings_hours=48,
        block_post_earnings_hours=24,
        block_fed_fomc=True,
        block_ecb=True,
        block_high_impact_macro=True,
        blocked_macro_event_types=("CPI", "PCE", "NFP", "PMI", "FOMC", "ECB"),
        block_mna_rumors=True,
        block_dividends_hours=24,
        block_splits_hours=48,
        allowed_trading_hours_utc=("13:30", "20:00"),
    ),
    horizon=HorizonConstraints(
        primary_timeframe="D1",
        min_holding_period_minutes=60 * 24,
        max_holding_period_days=90,
    ),
    execution=ExecutionConstraints(
        allowed_order_types=("limit", "stop", "stop_limit"),
        default_order_type="limit",
    ),
    evidence=EvidenceThresholds(
        minimum_required_credibility=80,
        minimum_walk_forward_efficiency=0.7,
        max_monte_carlo_p_value=0.05,
        minimum_dsr=0.7,
        require_edge_report_for_auto_live=True,
    ),
    exit_policy=CONSERVATIVE_EXIT_POLICY,
    updated_at=_NOW,
    created_at=_NOW,
)

MODERATE_POLICY = TradingPolicy(
    policy_id="POL-MODERATE-V1",
    version="1.0.0",
    template_id="moderate",
    name="Moderado",
    description="Equilibrio crecimiento/riesgo: mid+large cap, R:R 2:1, blackouts estándar.",
    universe=UniverseConstraints(
        allowed_asset_classes=("equities",),
        allowed_universes=("sp500", "nasdaq100", "russell1000"),
        min_market_cap_usd=2_000_000_000,
        min_average_daily_volume_usd=5_000_000,
        max_spread_bps=25,
        min_atr_pct=0.4,
        max_atr_pct=6,
        excluded_sectors=(),
        excluded_tickers=(),
        allow_shorting=False,
        allow_otc=False,
        allow_crypto=False,
        allow_cfds=False,
    ),
    exposure=ExposureConstraints(
        max_leverage=1.0,
        max_open_positions=12,
        max_portfolio_concentration_pct=12.0,
        max_sector_exposure_pct=30.0,
        max_correlation_with_open_positions=0.75,
    ),
    risk=RiskConstraints(
        max_risk_per_trade_pct=1.0,
        hard_daily_drawdown_limit_pct=2.0,
        hard_weekly_drawdown_limit_pct=5.0,
        hard_max_drawdown_limit_pct=12.0,
        min_reward_to_risk_ratio=2.0,
        stop_loss_required=True,
        min_take_profit_r_multiple=2.0,
    ),
    blackouts=BlackoutConstraints(
        block_pre_earnings_hours=24,
        block_post_earnings_hours=12,
        block_fed_fomc=True,
        block_ecb=True,
        block_high_impact_macro=True,
        blocked_macro_event_types=("CPI", "NFP", "FOMC"),
        block_mna_rumors=True,
        block_dividends_hours=12,
        block_splits_hours=24,
    ),
    horizon=HorizonConstraints(
        primary_timeframe="D1",
        min_holding_period_minutes=60 * 4,
        max_holding_period_days=45,
    ),
    execution=ExecutionConstraints(
        allowed_order_types=("market", "limit", "stop", "stop_limit"),
        default_order_type="limit",
    ),
    evidence=EvidenceThresholds(
        minimum_required_credibility=70,
        minimum_walk_forward_efficiency=0.6,
        max_monte_carlo_p_value=0.05,
        minimum_dsr=0.55,
        require_edge_report_for_auto_live=True,
    ),
    exit_policy=MODERATE_EXIT_POLICY,
    updated_at=_NOW,
    created_at=_NOW,
)

AGGRESSIVE_SWING_POLICY = TradingPolicy(
    policy_id="POL-AGGRESSIVE_SWING-V1",
    version="1.0.0",
    template_id="aggressive_swing",
    name="Swing agresivo",
    description="Mayor riesgo por trade; sigue exigiendo stop y Edge para auto-live.",
    universe=UniverseConstraints(
        allowed_asset_classes=("equities",),
        allowed_universes=("nasdaq100", "russell2000", "sp500"),
        min_market_cap_usd=500_000_000,
        min_average_daily_volume_usd=2_000_000,
        max_spread_bps=40,
        min_atr_pct=0.8,
        max_atr_pct=10,
        excluded_sectors=(),
        excluded_tickers=(),
        allow_shorting=True,
        allow_otc=False,
        allow_crypto=False,
        allow_cfds=False,
    ),
    exposure=ExposureConstraints(
        max_leverage=1.5,
        max_open_positions=15,
        max_portfolio_concentration_pct=18.0,
        max_sector_exposure_pct=40.0,
        max_correlation_with_open_positions=0.85,
    ),
    risk=RiskConstraints(
        max_risk_per_trade_pct=1.5,
        hard_daily_drawdown_limit_pct=3.0,
        hard_weekly_drawdown_limit_pct=7.0,
        hard_max_drawdown_limit_pct=18.0,
        min_reward_to_risk_ratio=1.8,
        stop_loss_required=True,
        min_take_profit_r_multiple=1.8,
    ),
    blackouts=BlackoutConstraints(
        block_pre_earnings_hours=12,
        block_post_earnings_hours=4,
        block_fed_fomc=True,
        block_ecb=False,
        block_high_impact_macro=True,
        blocked_macro_event_types=("CPI", "FOMC", "NFP"),
        block_mna_rumors=False,
        block_splits_hours=12,
    ),
    horizon=HorizonConstraints(
        primary_timeframe="H4",
        min_holding_period_minutes=60,
        max_holding_period_days=21,
    ),
    execution=ExecutionConstraints(
        allowed_order_types=("market", "limit", "stop", "stop_limit", "vwap"),
        default_order_type="market",
    ),
    evidence=EvidenceThresholds(
        minimum_required_credibility=65,
        minimum_walk_forward_efficiency=0.55,
        max_monte_carlo_p_value=0.08,
        minimum_dsr=0.45,
        require_edge_report_for_auto_live=True,
    ),
    exit_policy=AGGRESSIVE_SWING_EXIT_POLICY,
    updated_at=_NOW,
    created_at=_NOW,
)

POLICY_TEMPLATES: dict[str, TradingPolicy] = {
    "conservative": CONSERVATIVE_POLICY,
    "moderate": MODERATE_POLICY,
    "aggressive_swing": AGGRESSIVE_SWING_POLICY,
}


def get_policy_template(template_id: str) -> TradingPolicy:
    if template_id not in POLICY_TEMPLATES:
        raise KeyError(f"unknown policy template: {template_id}")
    return deepcopy(POLICY_TEMPLATES[template_id])
