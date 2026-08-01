"""Interceptor RFC-008 — Policy Gate + eventos en hot path auto (D2.4 / D4 / D7+)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.decision_memory import DecisionMemoryEntry
from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.gate_decision import ProposedTradeContext, gate_decision_package
from bolsa_analytics.cognitive.market_events import MarketEventCalendar
from bolsa_analytics.cognitive.trading_policy import TradingPolicy
from bolsa_analytics.cognitive.trading_policy_templates import get_policy_template
from bolsa_analytics.knowledge.decision_package_ta import DecisionPackageTa, build_decision_package_ta
from bolsa_analytics.knowledge.models import TechnicalInputs
from bolsa_domain.entities.investor_profile import InvestorProfileRecord


@dataclass(frozen=True, slots=True)
class CognitiveGuardResult:
    allowed: bool
    reasons: tuple[str, ...]
    policy_id: str | None
    policy_version: str | None
    memory_id: str | None
    decision_id: str | None
    gate: dict[str, Any] | None
    # Entrada lista para persistir en PG (None en exit bypass).
    memory: DecisionMemoryEntry | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "policyId": self.policy_id,
            "policyVersion": self.policy_version,
            "memoryId": self.memory_id,
            "decisionId": self.decision_id,
            "gate": self.gate,
            "memoryOutcome": None if self.memory is None else self.memory.outcome,
        }


def resolve_trading_policy(profile: InvestorProfileRecord | None) -> TradingPolicy:
    """ART-TRADING-POLICY desde perfil de catálogo activo; fallback moderate."""
    template_id = "moderate"
    if profile is not None:
        raw = profile.selected_policy_template_id or "moderate"
        if raw in {"conservative", "moderate", "aggressive_swing"}:
            template_id = raw
    return get_policy_template(template_id)


def _action_from_trade(
    trade_type: str,
    signal_kind: str | None,
) -> Literal["recommend_long", "recommend_short", "wait", "exit_hint"]:
    kind = (signal_kind or "").lower()
    if kind == "exit" or (trade_type == "sell" and kind not in {"entry_short"}):
        return "exit_hint"
    if kind == "entry_short" or (trade_type == "sell" and kind == "entry_short"):
        return "recommend_short"
    if trade_type == "buy" or kind == "entry_long":
        return "recommend_long"
    return "wait"


def enforce_cognitive_policy_for_opening(
    *,
    profile: InvestorProfileRecord | None,
    instrument_id: str,
    symbol: str,
    trade_type: str,
    quantity: float,
    price: float,
    signal_kind: str | None = None,
    equity: float | None = None,
    open_positions_count: int = 0,
    event_calendar: MarketEventCalendar | None = None,
    auto_live: bool = False,
    edge_report: EdgeReport | None = None,
    technical_inputs: TechnicalInputs | dict | None = None,
    sector: str | None = None,
    market_cap_usd: float | None = None,
    average_daily_volume_usd: float | None = None,
    account_daily_drawdown_pct: float | None = None,
    account_weekly_drawdown_pct: float | None = None,
    account_max_drawdown_pct: float | None = None,
) -> CognitiveGuardResult:
    """
    Evalúa apertura automática. Los `exit` no pasan por veto de universo/blackout
    (cerrar siempre debe ser posible salvo errores de ejecución).
    """
    action = _action_from_trade(trade_type, signal_kind)
    if action == "exit_hint":
        return CognitiveGuardResult(
            allowed=True,
            reasons=("exit_bypass_opening_gate",),
            policy_id=None,
            policy_version=None,
            memory_id=None,
            decision_id=None,
            gate=None,
            memory=None,
        )

    policy = resolve_trading_policy(profile)
    profile_ref = None if profile is None else profile.id

    if technical_inputs is not None:
        package, _, _ = build_decision_package_ta(
            instrument_id,
            technical_inputs,
            profile_snapshot_ref=profile_ref,
            policy_version=policy.version,
        )
        if package.action == "wait" and action in {"recommend_long", "recommend_short"}:
            from dataclasses import replace

            package = replace(package, action=action)
    else:
        from datetime import datetime, timezone
        from uuid import uuid4

        from bolsa_analytics.knowledge.decision_package_ta import DecisionMetrics

        package = DecisionPackageTa(
            decision_id=f"DEC-{uuid4().hex[:12]}",
            instrument_id=instrument_id,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            action=action,
            overall_confidence=0.5,
            metrics=DecisionMetrics(
                confidence=0.5,
                consensus=0.5,
                evidence_strength=0.3,
                stability=0.5,
                conviction=0.4,
            ),
            score_ta=0.0,
            evidence_breakdown=(
                {
                    "role": "technical",
                    "score": 0.0,
                    "weight": 1.0,
                    "facts": ["hot_path_without_ta_snapshot"],
                },
            ),
            fact_set_ref="FS-HOTPATH-NONE",
            profile_snapshot_ref=profile_ref,
            policy_version=policy.version,
            notes=("DecisionPackage stub — Policy Gate only",),
        )

    notional = abs(quantity * price)
    equity_v = equity if equity and equity > 0 else max(notional, 1.0)
    concentration = (notional / equity_v) * 100.0
    risk_pct = concentration * 0.5

    ctx = (
        event_calendar.blackout_context(symbol)
        if event_calendar is not None
        else None
    )

    trade = ProposedTradeContext(
        symbol=symbol.upper(),
        asset_class="equities",
        market_cap_usd=market_cap_usd,
        average_daily_volume_usd=average_daily_volume_usd,
        sector=sector,
        risk_pct_of_account=risk_pct,
        reward_to_risk_ratio=policy.risk.min_reward_to_risk_ratio,
        leverage=1.0,
        has_stop_loss=policy.risk.stop_loss_required,
        open_positions_count=open_positions_count,
        portfolio_concentration_pct=concentration,
        hours_to_earnings=None if ctx is None else ctx.hours_to_earnings,
        hours_since_earnings=None if ctx is None else ctx.hours_since_earnings,
        high_impact_macro_active=False if ctx is None else ctx.high_impact_macro_active,
        fed_fomc_active=False if ctx is None else ctx.fed_fomc_active,
        ecb_active=False if ctx is None else ctx.ecb_active,
        edge_report=edge_report,
        edge_report_present=edge_report is not None,
        auto_live=auto_live,
        account_daily_drawdown_pct=account_daily_drawdown_pct,
        account_weekly_drawdown_pct=account_weekly_drawdown_pct,
        account_max_drawdown_pct=account_max_drawdown_pct,
    )

    gated = gate_decision_package(package, policy, trade)
    return CognitiveGuardResult(
        allowed=gated.execution_allowed,
        reasons=gated.memory.reasons,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        memory_id=gated.memory.memory_id,
        decision_id=gated.package.decision_id,
        gate=None if gated.gate is None else gated.gate.to_dict(),
        memory=gated.memory,
    )
