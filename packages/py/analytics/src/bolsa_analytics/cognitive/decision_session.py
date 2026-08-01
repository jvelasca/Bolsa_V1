"""ART-DECISION-SESSION — fotografía completa del razonamiento (auditabilidad).

Session ≠ Memory: Memory = outcome del Gate; Session = caja negra del propose/ejecución.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Sequence
from uuid import uuid4

from bolsa_analytics.cognitive.weight_rules import WEIGHT_RULES_VERSION, WeightRuleResult

SessionKind = Literal["propose", "confirm", "paper_auto", "live_dry_run"]
SessionStatus = Literal["open", "closed"]


@dataclass(frozen=True, slots=True)
class WeightContext:
    """Pesos aplicados + por qué (reconstruible si cambia el algoritmo)."""

    horizon: str
    regime: str
    weights: dict[str, float]
    rationale: str
    rule_version: str = WEIGHT_RULES_VERSION
    size_hint: float = 1.0
    veto_new_long: bool = False
    missing_assessments: tuple[str, ...] = ()
    policy_id: str | None = None
    volatility_regime: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizon": self.horizon,
            "regime": self.regime,
            "volatilityRegime": self.volatility_regime,
            "policyId": self.policy_id,
            "ruleVersion": self.rule_version,
            "weights": dict(self.weights),
            "rationale": self.rationale,
            "sizeHint": self.size_hint,
            "vetoNewLong": self.veto_new_long,
            "missingAssessments": list(self.missing_assessments),
        }

    @classmethod
    def from_weight_rules(
        cls,
        rules: WeightRuleResult,
        *,
        missing: Sequence[str] | tuple[str, ...] = (),
        policy_id: str | None = None,
    ) -> WeightContext:
        return cls(
            horizon=rules.horizon,
            regime=rules.regime,
            weights={
                "ta": rules.w_ta,
                "fund": rules.w_fund,
                "macro": rules.w_macro,
                "news": rules.w_news,
            },
            rationale=rules.rationale,
            rule_version=WEIGHT_RULES_VERSION,
            size_hint=rules.size_hint,
            veto_new_long=rules.veto_new_long,
            missing_assessments=tuple(missing),
            policy_id=policy_id,
        )


@dataclass(frozen=True, slots=True)
class DecisionSession:
    """Fotografía auditable de una decisión (propose → gate → execution?)."""

    session_id: str
    kind: SessionKind
    status: SessionStatus
    instrument_id: str
    created_at: str
    account_id: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    horizon: str | None = None
    market_regime: str | None = None
    profile_snapshot_ref: str | None = None
    policy_snapshot: dict[str, Any] | None = None
    weight_context: WeightContext | None = None
    assessments: tuple[dict[str, Any], ...] = ()
    predictions: tuple[dict[str, Any], ...] = ()
    evidence: dict[str, Any] | None = None
    runtime: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    policy_gate: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    outcome: dict[str, Any] | None = None
    lineage: dict[str, Any] = field(default_factory=dict)
    decision_id: str | None = None
    recommendation_id: str | None = None
    artifact_type: str = "ART-DECISION-SESSION"
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "sessionId": self.session_id,
            "kind": self.kind,
            "status": self.status,
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "accountId": self.account_id,
            "createdAt": self.created_at,
            "timeframe": self.timeframe,
            "horizon": self.horizon,
            "marketRegime": self.market_regime,
            "profileSnapshotRef": self.profile_snapshot_ref,
            "policySnapshot": self.policy_snapshot,
            "weightContext": None if self.weight_context is None else self.weight_context.to_dict(),
            "assessments": list(self.assessments),
            "predictions": list(self.predictions),
            "evidence": self.evidence,
            "runtime": self.runtime,
            "recommendation": self.recommendation,
            "policyGate": self.policy_gate,
            "execution": self.execution,
            "outcome": self.outcome,
            "lineage": dict(self.lineage),
            "decisionId": self.decision_id,
            "recommendationId": self.recommendation_id,
        }


def new_session_id() -> str:
    return f"DSS-{uuid4().hex[:12]}"


def build_propose_session(
    *,
    instrument_id: str,
    symbol: str | None,
    account_id: str | None,
    timeframe: str,
    horizon: str,
    market_regime: str | None,
    profile_snapshot_ref: str | None,
    policy_version: str | None,
    weight_rules: WeightRuleResult | None,
    missing_assessments: Sequence[str],
    assessments: Sequence[dict[str, Any]],
    evidence: dict[str, Any] | None,
    runtime: dict[str, Any],
    recommendation: dict[str, Any],
    policy_gate: dict[str, Any] | None,
    lineage: dict[str, Any] | None = None,
    decision_id: str | None = None,
    predictions: Sequence[dict[str, Any]] | None = None,
) -> DecisionSession:
    wc = None
    if weight_rules is not None:
        wc = WeightContext.from_weight_rules(
            weight_rules,
            missing=missing_assessments,
            policy_id=policy_version,
        )
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rec_id = recommendation.get("recommendationId") or recommendation.get("id")
    return DecisionSession(
        session_id=new_session_id(),
        kind="propose",
        status="open",
        instrument_id=instrument_id,
        symbol=symbol,
        account_id=account_id,
        created_at=now,
        timeframe=timeframe,
        horizon=horizon,
        market_regime=market_regime,
        profile_snapshot_ref=profile_snapshot_ref,
        policy_snapshot={"policyVersion": policy_version} if policy_version else None,
        weight_context=wc,
        assessments=tuple(assessments),
        predictions=tuple(predictions or ()),
        evidence=evidence,
        runtime=runtime,
        recommendation=recommendation,
        policy_gate=policy_gate,
        lineage=dict(lineage or {}),
        decision_id=decision_id,
        recommendation_id=str(rec_id) if rec_id else None,
    )


def attach_execution_to_payload(
    payload: dict[str, Any],
    execution: dict[str, Any],
    *,
    kind: SessionKind | None = None,
    extra_lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Actualiza una Session existente con bloque execution (+ lineage)."""
    next_payload = dict(payload)
    next_payload["execution"] = execution
    if kind is not None:
        next_payload["kind"] = kind
    lineage = dict(next_payload.get("lineage") or {})
    if extra_lineage:
        lineage.update(extra_lineage)
    next_payload["lineage"] = lineage
    return next_payload


def build_auto_session(
    *,
    kind: Literal["paper_auto", "live_dry_run", "confirm"],
    instrument_id: str,
    account_id: str | None,
    symbol: str | None = None,
    policy_gate: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    recommendation: dict[str, Any] | None = None,
    lineage: dict[str, Any] | None = None,
    decision_id: str | None = None,
    parent_session_id: str | None = None,
    status: SessionStatus = "open",
) -> DecisionSession:
    """Session de follow-up (confirm / paper_auto / live_dry_run) — no re-ejecuta Runtime."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lin = dict(lineage or {})
    if parent_session_id:
        lin["parentSessionId"] = parent_session_id
    rec_id = None
    if recommendation:
        rec_id = recommendation.get("recommendationId") or recommendation.get("id")
    return DecisionSession(
        session_id=new_session_id(),
        kind=kind,
        status=status,
        instrument_id=instrument_id,
        symbol=symbol,
        account_id=account_id,
        created_at=now,
        policy_snapshot={"policyId": lin.get("policyId")} if lin.get("policyId") else None,
        recommendation=recommendation,
        policy_gate=policy_gate,
        execution=execution,
        lineage=lin,
        decision_id=decision_id,
        recommendation_id=str(rec_id) if rec_id else None,
    )
