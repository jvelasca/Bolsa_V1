"""ART-TRADING-POLICY — manual operativo hard (RFC-008 D1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.exit_policy import ExitPolicy

AssetClass = Literal["equities", "fx", "crypto", "commodities", "rates", "options"]
PolicyTemplateId = Literal["conservative", "moderate", "aggressive_swing", "custom"]
PrimaryTimeframe = Literal["M5", "M15", "H1", "H4", "D1", "W1"]
AllowedOrderType = Literal[
    "market", "limit", "stop", "stop_limit", "twap", "vwap", "iceberg"
]


@dataclass(frozen=True, slots=True)
class UniverseConstraints:
    allowed_asset_classes: tuple[AssetClass, ...]
    min_average_daily_volume_usd: float
    excluded_sectors: tuple[str, ...]
    excluded_tickers: tuple[str, ...]
    allow_shorting: bool
    allow_otc: bool
    allow_crypto: bool
    allow_cfds: bool
    allowed_universes: tuple[str, ...] = ()
    min_market_cap_usd: float | None = None
    max_spread_bps: float | None = None
    min_atr_pct: float | None = None
    max_atr_pct: float | None = None


@dataclass(frozen=True, slots=True)
class ExposureConstraints:
    max_leverage: float
    max_open_positions: int
    max_portfolio_concentration_pct: float
    max_sector_exposure_pct: float
    max_correlation_with_open_positions: float | None = None


@dataclass(frozen=True, slots=True)
class RiskConstraints:
    max_risk_per_trade_pct: float
    hard_daily_drawdown_limit_pct: float
    hard_max_drawdown_limit_pct: float
    min_reward_to_risk_ratio: float
    stop_loss_required: bool
    hard_weekly_drawdown_limit_pct: float | None = None
    min_take_profit_r_multiple: float | None = None


@dataclass(frozen=True, slots=True)
class BlackoutConstraints:
    block_pre_earnings_hours: float
    block_post_earnings_hours: float
    block_fed_fomc: bool
    block_ecb: bool
    block_high_impact_macro: bool
    blocked_macro_event_types: tuple[str, ...]
    block_mna_rumors: bool
    block_dividends_hours: float | None = None
    block_splits_hours: float | None = None
    allowed_trading_hours_utc: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True)
class HorizonConstraints:
    primary_timeframe: PrimaryTimeframe
    min_holding_period_minutes: int
    max_holding_period_days: int


@dataclass(frozen=True, slots=True)
class ExecutionConstraints:
    allowed_order_types: tuple[AllowedOrderType, ...]
    default_order_type: AllowedOrderType


@dataclass(frozen=True, slots=True)
class EvidenceThresholds:
    minimum_required_credibility: float
    minimum_walk_forward_efficiency: float
    max_monte_carlo_p_value: float
    require_edge_report_for_auto_live: bool
    minimum_dsr: float | None = None


@dataclass(frozen=True, slots=True)
class TradingPolicy:
    policy_id: str
    version: str
    template_id: PolicyTemplateId
    name: str
    universe: UniverseConstraints
    exposure: ExposureConstraints
    risk: RiskConstraints
    blackouts: BlackoutConstraints
    horizon: HorizonConstraints
    execution: ExecutionConstraints
    evidence: EvidenceThresholds
    updated_at: str
    created_at: str
    artifact_type: str = "ART-TRADING-POLICY"
    schema_version: str = "1.0.0"
    description: str | None = None
    weight_rule_set_id: str | None = None
    exit_policy: ExitPolicy | None = None

    def to_dict(self) -> dict[str, Any]:
        u = self.universe
        b = self.blackouts
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "policyId": self.policy_id,
            "version": self.version,
            "templateId": self.template_id,
            "name": self.name,
            "description": self.description,
            "universe": {
                "allowedAssetClasses": list(u.allowed_asset_classes),
                "allowedUniverses": list(u.allowed_universes),
                "minMarketCapUSD": u.min_market_cap_usd,
                "minAverageDailyVolumeUSD": u.min_average_daily_volume_usd,
                "maxSpreadBps": u.max_spread_bps,
                "minAtrPct": u.min_atr_pct,
                "maxAtrPct": u.max_atr_pct,
                "excludedSectors": list(u.excluded_sectors),
                "excludedTickers": list(u.excluded_tickers),
                "allowShorting": u.allow_shorting,
                "allowOtc": u.allow_otc,
                "allowCrypto": u.allow_crypto,
                "allowCfds": u.allow_cfds,
            },
            "exposure": {
                "maxLeverage": self.exposure.max_leverage,
                "maxOpenPositions": self.exposure.max_open_positions,
                "maxPortfolioConcentrationPct": self.exposure.max_portfolio_concentration_pct,
                "maxSectorExposurePct": self.exposure.max_sector_exposure_pct,
                "maxCorrelationWithOpenPositions": self.exposure.max_correlation_with_open_positions,
            },
            "risk": {
                "maxRiskPerTradePct": self.risk.max_risk_per_trade_pct,
                "hardDailyDrawdownLimitPct": self.risk.hard_daily_drawdown_limit_pct,
                "hardWeeklyDrawdownLimitPct": self.risk.hard_weekly_drawdown_limit_pct,
                "hardMaxDrawdownLimitPct": self.risk.hard_max_drawdown_limit_pct,
                "minRewardToRiskRatio": self.risk.min_reward_to_risk_ratio,
                "stopLossRequired": self.risk.stop_loss_required,
                "minTakeProfitRMultiple": self.risk.min_take_profit_r_multiple,
            },
            "blackouts": {
                "blockPreEarningsHours": b.block_pre_earnings_hours,
                "blockPostEarningsHours": b.block_post_earnings_hours,
                "blockFedFomc": b.block_fed_fomc,
                "blockEcb": b.block_ecb,
                "blockHighImpactMacro": b.block_high_impact_macro,
                "blockedMacroEventTypes": list(b.blocked_macro_event_types),
                "blockMnaRumors": b.block_mna_rumors,
                "blockDividendsHours": b.block_dividends_hours,
                "blockSplitsHours": b.block_splits_hours,
                "allowedTradingHoursUTC": None
                if b.allowed_trading_hours_utc is None
                else {
                    "start": b.allowed_trading_hours_utc[0],
                    "end": b.allowed_trading_hours_utc[1],
                },
            },
            "horizon": {
                "primaryTimeframe": self.horizon.primary_timeframe,
                "minHoldingPeriodMinutes": self.horizon.min_holding_period_minutes,
                "maxHoldingPeriodDays": self.horizon.max_holding_period_days,
            },
            "execution": {
                "allowedOrderTypes": list(self.execution.allowed_order_types),
                "defaultOrderType": self.execution.default_order_type,
            },
            "evidence": {
                "minimumRequiredCredibility": self.evidence.minimum_required_credibility,
                "minimumWalkForwardEfficiency": self.evidence.minimum_walk_forward_efficiency,
                "maxMonteCarloPValue": self.evidence.max_monte_carlo_p_value,
                "minimumDsr": self.evidence.minimum_dsr,
                "requireEdgeReportForAutoLive": self.evidence.require_edge_report_for_auto_live,
            },
            "weightRuleSetId": self.weight_rule_set_id,
            "exit": None if self.exit_policy is None else self.exit_policy.to_dict(),
            "updatedAt": self.updated_at,
            "createdAt": self.created_at,
        }
