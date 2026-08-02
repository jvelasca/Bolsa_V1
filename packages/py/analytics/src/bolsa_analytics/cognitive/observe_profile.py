"""Observed Profile — conducta medida; nunca muta Declared ni Policy (RFC-008 D7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_analytics.cognitive.investor_profile import (
    DeclaredInvestorProfile,
    ObservedInvestorProfile,
)

Side = Literal["buy", "sell"]


@dataclass(frozen=True, slots=True)
class BehaviorTradeSample:
    """Muestra mínima de conducta (paper/live) para observar perfil."""

    side: Side
    holding_hours: float
    risk_pct_of_equity: float
    followed_stop: bool
    policy_breach: bool = False
    impulsivity_flag: bool = False  # p.ej. reopen < 1h tras stop


@dataclass(frozen=True, slots=True)
class PolicyBehaviorLimits:
    """Límites de policy usados solo para detectar divergencia (lectura)."""

    max_risk_per_trade_pct: float = 1.0
    max_trades_per_week: int | None = None
    primary_horizon: Literal["intraday", "swing", "position", "long_term"] = "swing"


def _horizon_max_hours(horizon: str) -> float:
    if horizon == "intraday":
        return 24.0
    if horizon == "swing":
        return 24.0 * 21
    if horizon == "position":
        return 24.0 * 90
    return 24.0 * 365


def _horizon_min_hours(horizon: str) -> float:
    if horizon == "intraday":
        return 0.0
    if horizon == "swing":
        return 4.0
    if horizon == "position":
        return 24.0 * 5
    return 24.0 * 20


def observe_investor_profile(
    declared: DeclaredInvestorProfile,
    samples: list[BehaviorTradeSample] | tuple[BehaviorTradeSample, ...],
    *,
    policy_limits: PolicyBehaviorLimits | None = None,
    now: str | None = None,
) -> ObservedInvestorProfile:
    """
    Calcula Observed desde muestras de trades.
    Prohibido: reescribir declared / policy — solo scores + flags de divergencia.
    """
    ts = now or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    trades = list(samples)
    n = len(trades)
    if n == 0:
        return ObservedInvestorProfile(
            sample_trade_count=0,
            diverges_from_declared=False,
            diverges_from_policy=False,
            impulsivity_score=None,
            overtrading_score=None,
            discipline_score=None,
            last_observed_at=ts,
            notes=("Sin muestras de conducta aún",),
        )

    limits = policy_limits or PolicyBehaviorLimits(
        max_risk_per_trade_pct=declared.max_acceptable_loss_pct or 1.0,
        primary_horizon=declared.horizon,
    )

    impulse_hits = sum(1 for t in trades if t.impulsivity_flag)
    stop_ok = sum(1 for t in trades if t.followed_stop)
    breaches = sum(1 for t in trades if t.policy_breach)
    risk_over = sum(1 for t in trades if t.risk_pct_of_equity > limits.max_risk_per_trade_pct)

    # Holding vs horizonte declarado
    max_h = _horizon_max_hours(declared.horizon)
    min_h = _horizon_min_hours(declared.horizon)
    horizon_mismatch = sum(
        1 for t in trades if t.holding_hours > max_h * 1.5 or t.holding_hours < min_h * 0.25
    )

    impulsivity = round(min(1.0, impulse_hits / n), 3)
    # overtrading: muchos trades + risk alto + horizon mismatch corto
    short_churn = sum(1 for t in trades if t.holding_hours < max(1.0, min_h * 0.5))
    overtrading = round(min(1.0, (short_churn + risk_over) / (2 * n)), 3)
    discipline = round(max(0.0, (stop_ok / n) * (1.0 - breaches / n)), 3)

    notes: list[str] = []
    diverges_declared = False
    diverges_policy = False

    risk_map = {"low": 0.5, "moderate": 1.5, "high": 3.5}
    declared_cap = declared.max_acceptable_loss_pct or risk_map[declared.risk_tolerance]
    avg_risk = sum(t.risk_pct_of_equity for t in trades) / n
    if avg_risk > declared_cap * 1.25:
        diverges_declared = True
        notes.append(
            f"Riesgo medio {avg_risk:.2f}% > declarado≈{declared_cap:.2f}% (no se reescribe Declared)"
        )
    if impulsivity >= 0.35:
        diverges_declared = True
        notes.append(f"Impulsividad observada {impulsivity:.2f}")
    if horizon_mismatch / n >= 0.4:
        diverges_declared = True
        notes.append("Holding diverge del horizonte declarado")

    if breaches > 0 or risk_over / n >= 0.25:
        diverges_policy = True
        notes.append("Incumplimientos / riesgo sobre Policy (solo alerta)")
    if limits.max_trades_per_week is not None and n > limits.max_trades_per_week:
        diverges_policy = True
        notes.append("Posible overtrading vs límite semanal de Policy")

    if not notes:
        notes.append("Conducta alineada con Declared/Policy (muestra actual)")

    return ObservedInvestorProfile(
        sample_trade_count=n,
        impulsivity_score=impulsivity,
        overtrading_score=overtrading,
        discipline_score=discipline,
        diverges_from_declared=diverges_declared,
        diverges_from_policy=diverges_policy,
        last_observed_at=ts,
        notes=tuple(notes),
    )


def observed_to_dict(obs: ObservedInvestorProfile) -> dict[str, Any]:
    return {
        "sampleTradeCount": obs.sample_trade_count,
        "impulsivityScore": obs.impulsivity_score,
        "overtradingScore": obs.overtrading_score,
        "disciplineScore": obs.discipline_score,
        "divergesFromDeclared": obs.diverges_from_declared,
        "divergesFromPolicy": obs.diverges_from_policy,
        "lastObservedAt": obs.last_observed_at,
        "notes": list(obs.notes),
    }
