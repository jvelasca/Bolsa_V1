"""Mapeo Declared → plantilla TradingPolicy (RFC-008 D1)."""

from __future__ import annotations

from typing import Literal

SuggestablePolicyTemplateId = Literal["conservative", "moderate", "aggressive_swing"]


def suggest_policy_template_from_declared(
    *,
    risk_tolerance: str,
    horizon: str,
    experience: str = "intermediate",
) -> SuggestablePolicyTemplateId:
    if risk_tolerance == "low":
        return "conservative"
    if risk_tolerance == "high":
        if horizon == "long_term" and experience == "novice":
            return "moderate"
        return "aggressive_swing"
    if horizon == "intraday":
        return "aggressive_swing"
    if horizon == "long_term":
        return "conservative"
    return "moderate"
