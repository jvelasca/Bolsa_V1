"""OperatingPolicy — composición InvestorProfile → políticas operativas (V1.35)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.exit_policy import ExitPolicy, resolve_exit_policy
from bolsa_analytics.cognitive.trading_policy import TradingPolicy

OperatingPolicyTemplateId = Literal["conservative", "moderate", "aggressive_swing"]


@dataclass(frozen=True, slots=True)
class EntryPolicy:
    requires_setup: bool = True


@dataclass(frozen=True, slots=True)
class PositionSizingPolicy:
    max_open_positions: int
    max_portfolio_concentration_pct: float


@dataclass(frozen=True, slots=True)
class TrailingPolicy:
    trail_width: str
    ratchet_only: bool = True


@dataclass(frozen=True, slots=True)
class TimePolicy:
    max_holding_period_days: int
    min_holding_period_minutes: int


@dataclass(frozen=True, slots=True)
class ConcentrationPolicy:
    max_sector_exposure_pct: float
    max_leverage: float


@dataclass(frozen=True, slots=True)
class OperatingPolicy:
    template_id: OperatingPolicyTemplateId
    entry: EntryPolicy
    risk: Any
    sizing: PositionSizingPolicy
    exit: ExitPolicy
    trailing: TrailingPolicy
    time: TimePolicy
    concentration: ConcentrationPolicy

    def to_dict(self) -> dict[str, Any]:
        return {
            "templateId": self.template_id,
            "entry": {"requiresSetup": self.entry.requires_setup},
            "risk": dict(self.risk.to_dict()) if hasattr(self.risk, "to_dict") else {},
            "sizing": {
                "maxOpenPositions": self.sizing.max_open_positions,
                "maxPortfolioConcentrationPct": self.sizing.max_portfolio_concentration_pct,
            },
            "exit": self.exit.to_dict(),
            "trailing": {
                "trailWidth": self.trailing.trail_width,
                "ratchetOnly": self.trailing.ratchet_only,
            },
            "time": {
                "maxHoldingPeriodDays": self.time.max_holding_period_days,
                "minHoldingPeriodMinutes": self.time.min_holding_period_minutes,
            },
            "concentration": {
                "maxSectorExposurePct": self.concentration.max_sector_exposure_pct,
                "maxLeverage": self.concentration.max_leverage,
            },
        }


def _normalize_template(template_id: str | None) -> OperatingPolicyTemplateId:
    if template_id == "conservative":
        return "conservative"
    if template_id == "aggressive_swing":
        return "aggressive_swing"
    return "moderate"


def _resolve_trading_policy(template_id: OperatingPolicyTemplateId) -> TradingPolicy:
    from bolsa_analytics.cognitive.trading_policy_templates import get_policy_template

    return get_policy_template(template_id)


def resolve_operating_policy(template_id: str | None = None) -> OperatingPolicy:
    tid = _normalize_template(template_id)
    trading = _resolve_trading_policy(tid)
    exit_policy = resolve_exit_policy(tid)
    return OperatingPolicy(
        template_id=tid,
        entry=EntryPolicy(),
        risk=trading.risk,
        sizing=PositionSizingPolicy(
            max_open_positions=trading.exposure.max_open_positions,
            max_portfolio_concentration_pct=trading.exposure.max_portfolio_concentration_pct,
        ),
        exit=exit_policy,
        trailing=TrailingPolicy(trail_width=exit_policy.trail_width),
        time=TimePolicy(
            max_holding_period_days=trading.horizon.max_holding_period_days,
            min_holding_period_minutes=trading.horizon.min_holding_period_minutes,
        ),
        concentration=ConcentrationPolicy(
            max_sector_exposure_pct=trading.exposure.max_sector_exposure_pct,
            max_leverage=trading.exposure.max_leverage,
        ),
    )
