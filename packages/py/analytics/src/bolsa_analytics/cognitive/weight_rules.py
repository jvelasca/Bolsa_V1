"""WeightRules contextuales — horizonte + régimen (RFC-008 D6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Bump cuando cambie la matriz / lógica de resolve_weight_rules (auditabilidad).
WEIGHT_RULES_VERSION = "2.0.0"

HorizonHint = Literal["intraday", "swing", "position", "long_term"]
MarketRegime = Literal["risk_on", "neutral", "risk_off", "crisis", "uncertain"]


@dataclass(frozen=True, slots=True)
class WeightRuleResult:
    w_ta: float
    w_fund: float
    w_macro: float
    w_news: float
    horizon: HorizonHint
    regime: MarketRegime
    rationale: str
    # hint de sizing 0–1 (crisis/risk_off reduce)
    size_hint: float = 1.0
    veto_new_long: bool = False

    def normalized_opportunity_weights(self) -> tuple[float, float, float]:
        """Pesos TA/FUND/MACRO renormalizados (news fuera — usar normalized_with_news)."""
        s = self.w_ta + self.w_fund + self.w_macro
        if s <= 0:
            return 1.0, 0.0, 0.0
        return self.w_ta / s, self.w_fund / s, self.w_macro / s

    def normalized_with_news(self) -> tuple[float, float, float, float]:
        """Pesos TA/FUND/MACRO/NEWS renormalizados (suma 1)."""
        s = self.w_ta + self.w_fund + self.w_macro + self.w_news
        if s <= 0:
            return 1.0, 0.0, 0.0, 0.0
        return self.w_ta / s, self.w_fund / s, self.w_macro / s, self.w_news / s


def _base_for_horizon(horizon: HorizonHint) -> tuple[float, float, float, float, str]:
    """ta, fund, macro, news, note."""
    if horizon == "intraday":
        return 0.88, 0.02, 0.08, 0.02, "intraday: fund≈0"
    if horizon == "long_term":
        return 0.28, 0.52, 0.15, 0.05, "long_term: fund dominante"
    if horizon == "position":
        return 0.38, 0.42, 0.15, 0.05, "position: fund alto"
    return 0.52, 0.30, 0.13, 0.05, "swing: TA+FUND+macro"


def resolve_weight_rules(
    horizon: HorizonHint = "swing",
    regime: MarketRegime = "neutral",
) -> WeightRuleResult:
    """
    WeightRules v2: no pesos universales fijos.
    Crisis → macro/risk dominan; puede veto_new_long.
    """
    w_ta, w_fund, w_macro, w_news, h_note = _base_for_horizon(horizon)
    size = 1.0
    veto_long = False
    r_note = regime

    if regime == "crisis":
        w_ta, w_fund, w_macro, w_news = 0.25, 0.10, 0.55, 0.10
        size = 0.25
        veto_long = True
        r_note = "crisis: macro/risk dominan; veto long nuevo"
    elif regime == "risk_off":
        w_ta *= 0.85
        w_fund *= 0.75
        w_macro = max(w_macro, 0.28)
        size = 0.55
        r_note = "risk_off: macro↑ size↓"
    elif regime == "risk_on":
        w_macro *= 0.7
        w_ta *= 1.05
        w_fund *= 1.05
        size = 1.0
        r_note = "risk_on: TA/FUND favorecidos"
    elif regime == "uncertain":
        w_macro = max(w_macro, 0.2)
        size = 0.7
        r_note = "uncertain: cobertura baja; size↓"

    # Renormalizar a suma 1
    total = w_ta + w_fund + w_macro + w_news
    if total <= 0:
        w_ta, w_fund, w_macro, w_news = 1.0, 0.0, 0.0, 0.0
    else:
        w_ta, w_fund, w_macro, w_news = (
            w_ta / total,
            w_fund / total,
            w_macro / total,
            w_news / total,
        )

    return WeightRuleResult(
        w_ta=round(w_ta, 4),
        w_fund=round(w_fund, 4),
        w_macro=round(w_macro, 4),
        w_news=round(w_news, 4),
        horizon=horizon,
        regime=regime,
        rationale=f"{h_note}; {r_note}",
        size_hint=size,
        veto_new_long=veto_long,
    )


def weight_rules_for_horizon(horizon: HorizonHint = "swing") -> WeightRuleResult:
    """Compat D5: horizonte con régimen neutral (incluye w_macro > 0)."""
    return resolve_weight_rules(horizon, "neutral")
