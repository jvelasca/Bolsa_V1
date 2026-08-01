"""DecisionPackage (único) — construido por DecisionRuntime.

Compat: `build_decision_package_ta` / `DecisionPackageTa` se mantienen como alias
históricos; el flujo canónico es TechnicalAssessment → DecisionRuntime → Package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.knowledge.models import FactSet, TechnicalInputs
from bolsa_analytics.knowledge.score_ta import ScoreTaResult

DecisionAction = Literal[
    "recommend_long",
    "recommend_short",
    "wait",
    "reduce",
    "exit_hint",
]


@dataclass(frozen=True, slots=True)
class DecisionMetrics:
    confidence: float
    consensus: float
    evidence_strength: float
    stability: float
    conviction: float


@dataclass(frozen=True, slots=True)
class DecisionPackageTa:
    """
    ART-DECISION-PACKAGE — paquete de decisión global (único).

    Nombre histórico `DecisionPackageTa`; no implica «decisión solo técnica».
    La evidencia TA vive en TechnicalAssessment.
    """

    decision_id: str
    instrument_id: str
    timestamp: str
    action: DecisionAction
    overall_confidence: float
    metrics: DecisionMetrics
    score_ta: float
    evidence_breakdown: tuple[dict[str, Any], ...]
    fact_set_ref: str
    artifact_type: str = "ART-DECISION-PACKAGE"
    schema_version: str = "1.0.0"
    profile_snapshot_ref: str | None = None
    policy_version: str | None = None
    compliance_check: dict[str, Any] | None = None
    memory_ref: str | None = None
    execution_allowed: bool | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        m = self.metrics
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "overallConfidence": self.overall_confidence,
            "metrics": {
                "confidence": m.confidence,
                "consensus": m.consensus,
                "evidenceStrength": m.evidence_strength,
                "stability": m.stability,
                "conviction": m.conviction,
            },
            "scoreTa": self.score_ta,
            "evidenceBreakdown": list(self.evidence_breakdown),
            "factSetRef": self.fact_set_ref,
            "profileSnapshotRef": self.profile_snapshot_ref,
            "policyVersion": self.policy_version,
            "complianceCheck": self.compliance_check,
            "memoryRef": self.memory_ref,
            "executionAllowed": self.execution_allowed,
            "notes": list(self.notes),
        }


# Alias canónico
DecisionPackage = DecisionPackageTa


def build_decision_package_ta(
    instrument_id: str,
    inputs: TechnicalInputs | dict | FactSet,
    *,
    timestamp: str | None = None,
    profile_snapshot_ref: str | None = None,
    policy_version: str | None = None,
) -> tuple[DecisionPackageTa, FactSet, ScoreTaResult]:
    """
    Compat D2: Inputs → TechnicalAssessment → DecisionRuntime → DecisionPackage.

    Preferir `build_technical_assessment` + `run_decision_runtime` en código nuevo.
    """
    from bolsa_analytics.knowledge.decision_runtime import run_decision_runtime
    from bolsa_analytics.knowledge.technical_assessment import build_technical_assessment

    assessment, fact_set, score_result = build_technical_assessment(
        instrument_id,
        inputs,
        timestamp=timestamp,
    )
    runtime = run_decision_runtime(
        instrument_id=instrument_id,
        technical=assessment,
        profile_snapshot_ref=profile_snapshot_ref,
        policy_version=policy_version,
    )
    return runtime.package, fact_set, score_result
