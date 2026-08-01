"""Decision Runtime — único constructor de DecisionPackage + acción.

Habla Assessment[]. v1.1: fusiona TA+FUND+MACRO con WeightRules;
Evidence modula confianza (no dirección).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import uuid4

from bolsa_analytics.cognitive.weight_rules import (
    HorizonHint,
    MarketRegime,
    WeightRuleResult,
    resolve_weight_rules,
)
from bolsa_analytics.knowledge.assessment import Assessment, AssessmentLike
from bolsa_analytics.knowledge.decision_package_ta import (
    DecisionAction,
    DecisionMetrics,
    DecisionPackageTa,
)
from bolsa_analytics.knowledge.technical_assessment import (
    BEARISH_THRESHOLD,
    BULLISH_THRESHOLD,
    TechnicalAssessment,
)


@dataclass(frozen=True, slots=True)
class DecisionRuntimeResult:
    package: DecisionPackageTa
    assessments: tuple[Assessment, ...]
    technical_assessment: TechnicalAssessment | None
    policy_gate: dict[str, Any] | None
    combined_score: float
    weights: WeightRuleResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisionPackage": self.package.to_dict(),
            "assessments": [a.to_assessment_dict() for a in self.assessments],
            "technicalAssessment": None
            if self.technical_assessment is None
            else self.technical_assessment.to_dict(),
            "policyGate": self.policy_gate,
            "combinedScore": self.combined_score,
            "weights": None
            if self.weights is None
            else {
                "ta": self.weights.w_ta,
                "fund": self.weights.w_fund,
                "macro": self.weights.w_macro,
                "news": self.weights.w_news,
                "horizon": self.weights.horizon,
                "regime": self.weights.regime,
                "rationale": self.weights.rationale,
                "sizeHint": self.weights.size_hint,
                "vetoNewLong": self.weights.veto_new_long,
            },
        }


def _as_envelope(item: AssessmentLike) -> Assessment:
    if isinstance(item, Assessment):
        return item
    if hasattr(item, "as_assessment"):
        return item.as_assessment()  # type: ignore[no-any-return]
    return Assessment(
        assessment_id=item.assessment_id,
        assessment_type=item.assessment_type,  # type: ignore[arg-type]
        instrument_id=item.instrument_id,
        timestamp=item.timestamp,
        score=item.score,
        confidence=item.confidence,
        facts=tuple(item.facts),
        warnings=tuple(item.warnings),
        metadata={},
    )


def _normalize_assessments(
    *,
    assessments: Sequence[AssessmentLike] | None,
    technical: TechnicalAssessment | None,
) -> tuple[list[Assessment], TechnicalAssessment | None]:
    envelopes: list[Assessment] = []
    ta = technical

    if assessments:
        for item in assessments:
            if isinstance(item, TechnicalAssessment):
                ta = ta or item
            envelopes.append(_as_envelope(item))

    if ta is not None and not any(e.assessment_type == "technical" for e in envelopes):
        envelopes.append(ta.as_assessment())

    return envelopes, ta


def _action_from_combined(score: float) -> DecisionAction:
    if score >= BULLISH_THRESHOLD:
        return "recommend_long"
    if score <= BEARISH_THRESHOLD:
        return "recommend_short"
    return "wait"


def _fuse_directional(
    envelopes: Sequence[Assessment],
    *,
    horizon: HorizonHint,
    regime: MarketRegime,
) -> tuple[float, WeightRuleResult, dict[str, float]]:
    """Combina scores direccionales (excluye evidence). Incluye news vía w_news."""
    by_type = {a.assessment_type: a for a in envelopes}
    ta = by_type.get("technical")
    fund = by_type.get("fundamental")
    macro = by_type.get("macro")
    news = by_type.get("news") or by_type.get("sentiment")

    if ta is None:
        raise ValueError("DecisionRuntime requiere Assessment type=technical")

    base = resolve_weight_rules(horizon, regime)
    if macro is not None:
        meta_regime = macro.metadata.get("regime")
        if isinstance(meta_regime, str) and meta_regime in (
            "risk_on",
            "neutral",
            "risk_off",
            "crisis",
            "uncertain",
        ):
            base = resolve_weight_rules(horizon, meta_regime)  # type: ignore[arg-type]

    w_ta, w_fund, w_macro, w_news = base.normalized_with_news()
    parts: list[tuple[str, float, float]] = [("technical", ta.score, w_ta)]
    if fund is not None:
        parts.append(("fundamental", fund.score, w_fund))
    if macro is not None:
        parts.append(("macro", macro.score, w_macro))
    if news is not None:
        parts.append(("news", news.score, w_news))

    weight_sum = sum(w for _, _, w in parts)
    if weight_sum <= 0:
        parts = [("technical", ta.score, 1.0)]
        weight_sum = 1.0

    applied = {"technical": 0.0, "fundamental": 0.0, "macro": 0.0, "news": 0.0}
    combined = 0.0
    for role, score, w in parts:
        nw = w / weight_sum
        applied[role] = nw
        combined += nw * score

    used = WeightRuleResult(
        round(applied["technical"], 4),
        round(applied["fundamental"], 4),
        round(applied["macro"], 4),
        round(applied["news"], 4),
        horizon,
        base.regime,
        base.rationale
        + ("" if news is not None else " (news n/a)")
        + ("" if fund is not None else " (fund n/a)")
        + ("" if macro is not None else " (macro n/a)"),
        base.size_hint,
        base.veto_new_long,
    )

    if fund is not None and fund.metadata.get("distress") and combined > 0:
        combined = min(combined, -0.4)

    if macro is not None:
        if macro.metadata.get("tradability") == "wait" and combined > 0:
            combined = min(combined, 0.0)
        if used.veto_new_long and combined > 0:
            combined = min(combined, 0.0)

    combined = round(max(-1.0, min(1.0, combined)), 4)
    return combined, used, applied


def _metrics_from_fusion(
    envelopes: Sequence[Assessment],
    combined: float,
    applied_weights: dict[str, float],
) -> DecisionMetrics:
    directional = [a for a in envelopes if a.assessment_type != "evidence"]
    evidence = next((a for a in envelopes if a.assessment_type == "evidence"), None)

    if not directional:
        return DecisionMetrics(0.0, 0.5, 0.0, 0.5, 0.0)

    # Confianza ponderada por peso aplicado
    conf_num = 0.0
    conf_den = 0.0
    coverage_acc = 0.0
    for a in directional:
        w = applied_weights.get(a.assessment_type, 1.0 / len(directional))
        conf_num += a.confidence * w
        conf_den += w
        coverage_acc += float(a.metadata.get("coverage") or a.confidence) * w
    conf = conf_num / conf_den if conf_den else 0.5
    coverage = coverage_acc / conf_den if conf_den else 0.5

    if any(a.metadata.get("exhaustion") for a in directional if a.assessment_type == "technical"):
        conf *= 0.85
    if any(a.metadata.get("distress") for a in directional if a.assessment_type == "fundamental"):
        conf *= 0.7
    if any(
        a.metadata.get("tradability") not in (None, "tradable")
        for a in directional
        if a.assessment_type == "macro"
    ):
        conf *= 0.85

    # Evidence: band luck atenúa; skill refuerza ligeramente
    if evidence is not None:
        band = evidence.metadata.get("band")
        if band == "luck":
            conf *= 0.75
        elif band == "skill":
            conf = min(1.0, conf * 1.05)
        elif band == "uncertain":
            conf *= 0.9

    signs = [a.score for a in directional if abs(a.score) >= 0.05]
    if len(signs) < 2:
        consensus = 0.55
    else:
        pos = sum(1 for s in signs if s > 0)
        neg = sum(1 for s in signs if s < 0)
        consensus = 0.85 if (pos == len(signs) or neg == len(signs)) else 0.4

    magnitude = abs(combined)
    exhaustion = any(
        a.metadata.get("exhaustion") for a in directional if a.assessment_type == "technical"
    )
    return DecisionMetrics(
        confidence=round(min(1.0, conf), 3),
        consensus=round(consensus, 3),
        evidence_strength=round(min(1.0, coverage), 3),
        stability=round(max(0.25, coverage - (0.1 if exhaustion else 0)), 3),
        conviction=round(min(1.0, magnitude * 0.95), 3),
    )


def run_decision_runtime(
    *,
    instrument_id: str,
    assessments: Sequence[AssessmentLike] | None = None,
    technical: TechnicalAssessment | None = None,
    horizon: HorizonHint = "swing",
    regime: MarketRegime = "neutral",
    profile_snapshot_ref: str | None = None,
    policy_version: str | None = None,
    action_override: DecisionAction | None = None,
    evaluate_policy_gate: bool = False,
) -> DecisionRuntimeResult:
    """
    Integra Assessments → DecisionPackage único.

    Requiere type=technical. FUND/MACRO entran en fusión WeightRules.
    Evidence no vota dirección; modula confianza.
    Policy Gate en propose: pasivo (SKIPPED) salvo evaluate_policy_gate.
    """
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    envelopes, ta = _normalize_assessments(assessments=assessments, technical=technical)

    if not any(a.assessment_type == "technical" for a in envelopes):
        raise ValueError("DecisionRuntime requiere Assessment type=technical")

    combined, used_weights, applied = _fuse_directional(
        envelopes, horizon=horizon, regime=regime
    )
    action = action_override if action_override is not None else _action_from_combined(combined)
    metrics = _metrics_from_fusion(envelopes, combined, applied)

    technical_env = next(a for a in envelopes if a.assessment_type == "technical")
    refs = [
        str(a.metadata.get("factSetRef") or a.assessment_id)
        for a in envelopes
        if a.assessment_type != "evidence"
    ]

    breakdown = tuple(
        {
            "role": a.assessment_type,
            "evidenceKind": f"{a.assessment_type.capitalize()}Evidence",
            "score": a.score,
            "bias": a.metadata.get("bias"),
            "weight": applied.get(a.assessment_type, 0.0)
            if a.assessment_type != "evidence"
            else 0.0,
            "facts": list(a.facts),
            "warnings": list(a.warnings),
            "assessmentRef": a.assessment_id,
            "components": a.metadata.get("components"),
            "invalidators": [
                *(["distress"] if a.metadata.get("distress") else []),
                *(["exhaustion"] if a.metadata.get("exhaustion") else []),
                *(["crisis"] if a.metadata.get("regime") == "crisis" else []),
                *(["luck"] if a.metadata.get("band") == "luck" else []),
            ],
            "band": a.metadata.get("band"),
            "regime": a.metadata.get("regime"),
            "tradability": a.metadata.get("tradability"),
        }
        for a in envelopes
    )

    notes = [
        f"DecisionRuntime v1.1 — {len(envelopes)} assessment(s)",
        f"types={[a.assessment_type for a in envelopes]}",
        f"combined={combined} ({used_weights.rationale})",
    ]
    for a in envelopes:
        notes.extend(a.warnings)

    package = DecisionPackageTa(
        decision_id=f"DEC-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=ts,
        action=action,
        overall_confidence=metrics.confidence,
        metrics=metrics,
        score_ta=float(technical_env.score),
        evidence_breakdown=breakdown,
        fact_set_ref="+".join(refs) if refs else technical_env.assessment_id,
        profile_snapshot_ref=profile_snapshot_ref,
        policy_version=policy_version,
        compliance_check={
            "passed": True,
            "skipped": True,
            "reason": "policy_gate_passive_v1",
            "status": "SKIPPED",
        }
        if not evaluate_policy_gate
        else None,
        notes=tuple(notes),
    )

    gate = {
        "status": "SKIPPED",
        "mode": "passive_v1",
        "message": "Policy Gate pasivo en propose; hot path paper_auto evalúa PASS/VETO",
    }

    return DecisionRuntimeResult(
        package=package,
        assessments=tuple(envelopes),
        technical_assessment=ta,
        policy_gate=gate,
        combined_score=combined,
        weights=used_weights,
    )
