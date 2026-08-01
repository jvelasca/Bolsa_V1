"""Bloqueo auto-live sin Edge suficiente (RFC-008 D3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.evidence_engine import EvidenceEngineResult
from bolsa_analytics.cognitive.trading_policy import TradingPolicy


@dataclass(frozen=True, slots=True)
class AutoLiveCheck:
    allowed: bool
    reasons: tuple[str, ...]
    policy_id: str
    edge_report_id: str | None
    credibility: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "policyId": self.policy_id,
            "edgeReportId": self.edge_report_id,
            "credibility": self.credibility,
        }


def check_auto_live(
    policy: TradingPolicy,
    *,
    edge_report: EdgeReport | None = None,
    evidence_result: EvidenceEngineResult | None = None,
) -> AutoLiveCheck:
    """
    Auto-live solo si:
    - Policy.require_edge_report_for_auto_live ⇒ EdgeReport presente
    - credibility / WFE / MC / DSR cumplen umbrales de Policy
    - EvidenceEngineResult.auto_live_eligible si se aporta
    """
    reasons: list[str] = []
    report = edge_report
    if evidence_result is not None:
        report = evidence_result.edge_report
        if not evidence_result.auto_live_eligible:
            reasons.extend(evidence_result.block_reasons)

    ev = policy.evidence
    if ev.require_edge_report_for_auto_live and report is None:
        reasons.append("edge_report_missing")
        return AutoLiveCheck(
            allowed=False,
            reasons=tuple(reasons),
            policy_id=policy.policy_id,
            edge_report_id=None,
            credibility=None,
        )

    if report is None:
        return AutoLiveCheck(
            allowed=False,
            reasons=("edge_report_missing",),
            policy_id=policy.policy_id,
            edge_report_id=None,
            credibility=None,
        )

    if report.credibility < ev.minimum_required_credibility:
        reasons.append(
            f"credibility {report.credibility} < {ev.minimum_required_credibility}"
        )

    suite = report.suite
    if suite.walk_forward_efficiency is not None:
        if suite.walk_forward_efficiency < ev.minimum_walk_forward_efficiency:
            reasons.append(
                f"wfe {suite.walk_forward_efficiency} < {ev.minimum_walk_forward_efficiency}"
            )

    if suite.monte_carlo_p_value is not None:
        if suite.monte_carlo_p_value > ev.max_monte_carlo_p_value:
            reasons.append(
                f"mc_p {suite.monte_carlo_p_value} > {ev.max_monte_carlo_p_value}"
            )

    if ev.minimum_dsr is not None:
        if suite.trials_n < 1 or suite.dsr is None:
            reasons.append("dsr_unavailable_without_trials")
        elif suite.dsr < ev.minimum_dsr:
            reasons.append(f"dsr {suite.dsr} < {ev.minimum_dsr}")

    if report.band == "luck":
        reasons.append("edge_band_luck")

    return AutoLiveCheck(
        allowed=len(reasons) == 0,
        reasons=tuple(reasons),
        policy_id=policy.policy_id,
        edge_report_id=report.edge_report_id,
        credibility=report.credibility,
    )
