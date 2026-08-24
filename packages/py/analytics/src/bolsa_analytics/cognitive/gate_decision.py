"""D2.4 — Policy Gate sobre DecisionPackage (Opportunity ≠ Permission)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from bolsa_analytics.cognitive.auto_live import check_auto_live
from bolsa_analytics.cognitive.decision_memory import DecisionMemoryEntry, build_memory_entry
from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.policy_gate import PolicyGateResult, evaluate_policy_gate
from bolsa_analytics.cognitive.trading_policy import TradingPolicy
from bolsa_analytics.knowledge.decision_package_ta import DecisionPackageTa


@dataclass(frozen=True, slots=True)
class ProposedTradeContext:
    """Contexto de la operación candidata (sizing / R:R / exposición)."""

    symbol: str
    asset_class: str = "equities"
    market_cap_usd: float | None = None
    average_daily_volume_usd: float | None = None
    sector: str | None = None
    spread_bps: float | None = None
    risk_pct_of_account: float = 0.5
    reward_to_risk_ratio: float = 2.0
    leverage: float = 1.0
    has_stop_loss: bool = True
    open_positions_count: int = 0
    portfolio_concentration_pct: float = 5.0
    hours_to_earnings: float | None = None
    hours_since_earnings: float | None = None
    high_impact_macro_active: bool = False
    fed_fomc_active: bool = False
    ecb_active: bool = False
    credibility: float | None = None
    walk_forward_efficiency: float | None = None
    monte_carlo_p_value: float | None = None
    edge_report_present: bool = False
    edge_report: EdgeReport | None = None
    auto_live: bool = False
    account_daily_drawdown_pct: float | None = None
    account_weekly_drawdown_pct: float | None = None
    account_max_drawdown_pct: float | None = None
    basket_max_asset_weight_pct: float | None = None
    basket_max_sector_weight_pct: float | None = None
    basket_violating_asset: str | None = None
    basket_violating_sector: str | None = None


@dataclass(frozen=True, slots=True)
class GatedDecision:
    """DecisionPackage + resultado del Gate + memoria. La tesis no se borra en VETO."""

    package: DecisionPackageTa
    gate: PolicyGateResult | None
    memory: DecisionMemoryEntry
    execution_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package.to_dict(),
            "gate": None if self.gate is None else self.gate.to_dict(),
            "memory": self.memory.to_dict(),
            "executionAllowed": self.execution_allowed,
        }


def _reevaluate_triggers(gate: PolicyGateResult | None, trade: ProposedTradeContext) -> tuple[str, ...]:
    triggers: list[str] = []
    if gate is None:
        return ()
    failed = {r.rule for r in gate.evaluated_rules if r.status == "FAILED"}
    if "PreEarningsBlackout" in failed and trade.hours_to_earnings is not None:
        triggers.append("after_earnings_blackout_clears")
    if "PostEarningsBlackout" in failed:
        triggers.append("after_post_earnings_window")
    if "FedFomcBlackout" in failed or "EcbBlackout" in failed or "HighImpactMacroBlackout" in failed:
        triggers.append("after_macro_event_window")
    if "MinADV" in failed or "MaxSpreadBps" in failed:
        triggers.append("when_liquidity_improves")
    if "EdgeReportRequired" in failed or "MinCredibility" in failed:
        triggers.append("when_edge_report_available")
    return tuple(triggers)


def gate_decision_package(
    package: DecisionPackageTa,
    policy: TradingPolicy,
    trade: ProposedTradeContext,
) -> GatedDecision:
    """
    Aplica TradingPolicy al DecisionPackage.

    - `wait` / `reduce` / `exit_hint`: no abren posición → deferred, execution_allowed=False
      (no es VETO de oportunidad; no hay permiso que conceder).
    - `recommend_long` / `recommend_short`: evalúa Policy Gate completo.
      VETO ⇒ execution_allowed=False; la `action` del package **no** se reescribe
      (Opportunity ≠ Permission).
    """
    opening = package.action in {"recommend_long", "recommend_short"}

    if not opening:
        memory = build_memory_entry(
            decision_id=package.decision_id,
            instrument_id=package.instrument_id,
            outcome="deferred",
            reasons=[f"action={package.action}: sin apertura de posición"],
            policy_id=policy.policy_id,
            policy_version=policy.version,
            opportunity_intact=True,
        )
        gated_pkg = replace(
            package,
            policy_version=policy.version,
            compliance_check={
                "passed": True,
                "skipped": True,
                "reason": "no_opening_action",
                "policyId": policy.policy_id,
                "policyVersion": policy.version,
            },
            memory_ref=memory.memory_id,
            execution_allowed=False,
            notes=tuple([*package.notes, "Gate: sin apertura — deferred"]),
        )
        return GatedDecision(
            package=gated_pkg,
            gate=None,
            memory=memory,
            execution_allowed=False,
        )

    # Hidratar métricas de evidencia desde ART-EDGE-REPORT si viene adjunto
    credibility = trade.credibility
    wfe = trade.walk_forward_efficiency
    mc_p = trade.monte_carlo_p_value
    edge_present = trade.edge_report_present or trade.edge_report is not None
    if trade.edge_report is not None:
        credibility = trade.edge_report.credibility
        wfe = trade.edge_report.suite.walk_forward_efficiency
        mc_p = trade.edge_report.suite.monte_carlo_p_value
        edge_present = True

    gate = evaluate_policy_gate(
        policy,
        symbol=trade.symbol,
        asset_class=trade.asset_class,
        market_cap_usd=trade.market_cap_usd,
        average_daily_volume_usd=trade.average_daily_volume_usd,
        sector=trade.sector,
        spread_bps=trade.spread_bps,
        risk_pct_of_account=trade.risk_pct_of_account,
        reward_to_risk_ratio=trade.reward_to_risk_ratio,
        leverage=trade.leverage,
        has_stop_loss=trade.has_stop_loss,
        open_positions_count=trade.open_positions_count,
        portfolio_concentration_pct=trade.portfolio_concentration_pct,
        hours_to_earnings=trade.hours_to_earnings,
        hours_since_earnings=trade.hours_since_earnings,
        high_impact_macro_active=trade.high_impact_macro_active,
        fed_fomc_active=trade.fed_fomc_active,
        ecb_active=trade.ecb_active,
        credibility=credibility,
        walk_forward_efficiency=wfe,
        monte_carlo_p_value=mc_p,
        edge_report_present=edge_present,
        auto_live=trade.auto_live,
        account_daily_drawdown_pct=trade.account_daily_drawdown_pct,
        account_weekly_drawdown_pct=trade.account_weekly_drawdown_pct,
        account_max_drawdown_pct=trade.account_max_drawdown_pct,
        basket_max_asset_weight_pct=trade.basket_max_asset_weight_pct,
        basket_max_sector_weight_pct=trade.basket_max_sector_weight_pct,
        basket_violating_asset=trade.basket_violating_asset,
        basket_violating_sector=trade.basket_violating_sector,
    )

    if package.action == "recommend_short" and not policy.universe.allow_shorting:
        from bolsa_analytics.cognitive.policy_gate import PolicyRuleResult

        short_rule = PolicyRuleResult(
            rule="AllowShorting",
            limit="false",
            actual="recommend_short",
            status="FAILED",
            message="Shorting no permitido por TradingPolicy",
        )
        gate = PolicyGateResult(
            passed=False,
            policy_id=gate.policy_id,
            policy_version=gate.policy_version,
            evaluated_rules=tuple([*gate.evaluated_rules, short_rule]),
            veto_reasons=tuple(
                [*gate.veto_reasons, short_rule.message or short_rule.rule]
            ),
        )

    # D3: bloqueo auto-live explícito vía EdgeReport / umbrales Policy
    if trade.auto_live:
        al = check_auto_live(policy, edge_report=trade.edge_report)
        if not al.allowed:
            from bolsa_analytics.cognitive.policy_gate import PolicyRuleResult

            al_rule = PolicyRuleResult(
                rule="AutoLiveEvidence",
                limit="eligible",
                actual="blocked",
                status="FAILED",
                message="; ".join(al.reasons) or "auto-live bloqueado",
            )
            gate = PolicyGateResult(
                passed=False,
                policy_id=gate.policy_id,
                policy_version=gate.policy_version,
                evaluated_rules=tuple([*gate.evaluated_rules, al_rule]),
                veto_reasons=tuple([*gate.veto_reasons, al_rule.message or al_rule.rule]),
            )

    if gate.passed:
        memory = build_memory_entry(
            decision_id=package.decision_id,
            instrument_id=package.instrument_id,
            outcome="accepted",
            reasons=[f"Policy PASS — action={package.action}"],
            policy_rule_ids=tuple(r.rule for r in gate.evaluated_rules if r.status == "PASSED"),
            policy_id=policy.policy_id,
            policy_version=policy.version,
            opportunity_intact=True,
        )
        note = "Gate: PASS — execution_allowed"
    else:
        failed_rules = tuple(r.rule for r in gate.evaluated_rules if r.status == "FAILED")
        memory = build_memory_entry(
            decision_id=package.decision_id,
            instrument_id=package.instrument_id,
            outcome="rejected",
            reasons=list(gate.veto_reasons),
            policy_rule_ids=failed_rules,
            reevaluate_when=_reevaluate_triggers(gate, trade),
            opportunity_intact=True,
            policy_id=policy.policy_id,
            policy_version=policy.version,
        )
        note = f"Gate: VETO — {'; '.join(gate.veto_reasons)}"

    gated_pkg = replace(
        package,
        policy_version=policy.version,
        compliance_check=gate.to_dict(),
        memory_ref=memory.memory_id,
        execution_allowed=gate.passed,
        notes=tuple([*package.notes, note]),
    )

    return GatedDecision(
        package=gated_pkg,
        gate=gate,
        memory=memory,
        execution_allowed=gate.passed,
    )
