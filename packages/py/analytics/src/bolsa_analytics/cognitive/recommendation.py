"""ART-RECOMMENDATION — Portfolio domain (F3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from bolsa_analytics.knowledge.decision_package_ta import DecisionPackageTa

RecommendationStatus = Literal[
    "proposed",
    "awaiting_human",
    "approved",
    "rejected",
    "expired",
    "superseded",
]


@dataclass(frozen=True, slots=True)
class Recommendation:
    recommendation_id: str
    decision_id: str
    instrument_id: str
    action: str
    suggested_quantity: float
    metrics: dict[str, float]
    status: RecommendationStatus
    created_at: str
    artifact_type: str = "ART-RECOMMENDATION"
    schema_version: str = "1.0.0"
    symbol: str | None = None
    account_id: str | None = None
    suggested_price: float | None = None
    notional: float | None = None
    score_ta: float | None = None
    profile_snapshot_ref: str | None = None
    policy_version: str | None = None
    decision_package_ref: str | None = None
    edge_report_ref: str | None = None
    expires_at: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "recommendationId": self.recommendation_id,
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "accountId": self.account_id,
            "action": self.action,
            "suggestedQuantity": self.suggested_quantity,
            "suggestedPrice": self.suggested_price,
            "notional": self.notional,
            "metrics": self.metrics,
            "scoreTa": self.score_ta,
            "profileSnapshotRef": self.profile_snapshot_ref,
            "policyVersion": self.policy_version,
            "decisionPackageRef": self.decision_package_ref,
            "edgeReportRef": self.edge_report_ref,
            "status": self.status,
            "createdAt": self.created_at,
            "expiresAt": self.expires_at,
            "notes": list(self.notes),
        }


def recommendation_from_decision_package(
    package: DecisionPackageTa,
    *,
    suggested_quantity: float,
    suggested_price: float | None = None,
    account_id: str | None = None,
    symbol: str | None = None,
    status: RecommendationStatus = "awaiting_human",
    edge_report_ref: str | None = None,
) -> Recommendation:
    """Mapea DecisionPackage → Recommendation (sizing inyectado; no ejecuta)."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    notional = None
    if suggested_price is not None:
        notional = abs(suggested_quantity * suggested_price)
    m = package.metrics
    return Recommendation(
        recommendation_id=f"REC-{uuid4().hex[:12]}",
        decision_id=package.decision_id,
        instrument_id=package.instrument_id,
        action=package.action,
        suggested_quantity=suggested_quantity,
        metrics={
            "confidence": m.confidence,
            "consensus": m.consensus,
            "evidenceStrength": m.evidence_strength,
            "stability": m.stability,
            "conviction": m.conviction,
        },
        status=status,
        created_at=now,
        symbol=symbol,
        account_id=account_id,
        suggested_price=suggested_price,
        notional=notional,
        score_ta=package.score_ta,
        profile_snapshot_ref=package.profile_snapshot_ref,
        policy_version=package.policy_version,
        decision_package_ref=package.decision_id,
        edge_report_ref=edge_report_ref,
        notes=tuple(package.notes),
    )
