"""EffectiveTradingPolicy — límites de encaje desde plantilla de perfil (V1.30)."""

from __future__ import annotations

from bolsa_analytics.cognitive.trading_policy import TradingPolicy
from bolsa_analytics.cognitive.trading_policy_templates import get_policy_template

_EFFECTIVE_TEMPLATE_IDS = frozenset({"conservative", "moderate", "aggressive_swing"})


def resolve_effective_trading_policy(template_id: str | None) -> TradingPolicy:
    """Política operativa efectiva; fallback moderate sin perfil."""
    tid = template_id if template_id in _EFFECTIVE_TEMPLATE_IDS else "moderate"
    return get_policy_template(tid)


def effective_max_sector_exposure_pct(template_id: str | None) -> float:
    return resolve_effective_trading_policy(template_id).exposure.max_sector_exposure_pct


def format_portfolio_fit_preview(policy: TradingPolicy) -> str:
    e = policy.exposure
    return (
        f"Encaja: max sector {e.max_sector_exposure_pct:.0f}% · "
        f"max posición {e.max_portfolio_concentration_pct:.0f}% · "
        f"{e.max_open_positions} pos. abiertas"
    )
