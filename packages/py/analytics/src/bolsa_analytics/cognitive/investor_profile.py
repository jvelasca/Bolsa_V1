"""ART-PROFILE — Declared ≠ Observed (RFC-008 D1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ProfileHorizon = Literal["intraday", "swing", "position", "long_term"]
RiskTolerance = Literal["low", "moderate", "high"]
ExperienceLevel = Literal["novice", "intermediate", "advanced", "professional"]
ProfileUpdatedBy = Literal["user", "system_observation", "hybrid"]


@dataclass(frozen=True, slots=True)
class DeclaredInvestorProfile:
    horizon: ProfileHorizon
    objectives: tuple[str, ...]
    risk_tolerance: RiskTolerance
    experience: ExperienceLevel
    max_acceptable_loss_pct: float | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ObservedInvestorProfile:
    sample_trade_count: int
    diverges_from_declared: bool
    diverges_from_policy: bool
    impulsivity_score: float | None = None
    overtrading_score: float | None = None
    discipline_score: float | None = None
    last_observed_at: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InvestorProfile:
    profile_id: str
    version: str
    name: str
    declared: DeclaredInvestorProfile
    updated_by: ProfileUpdatedBy
    updated_at: str
    created_at: str
    artifact_type: str = "ART-PROFILE"
    schema_version: str = "1.0.0"
    account_id: str | None = None
    observed: ObservedInvestorProfile | None = None
    suggested_policy_template_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self.declared
        obs = self.observed
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "profileId": self.profile_id,
            "version": self.version,
            "accountId": self.account_id,
            "name": self.name,
            "declared": {
                "horizon": d.horizon,
                "objectives": list(d.objectives),
                "riskTolerance": d.risk_tolerance,
                "experience": d.experience,
                "maxAcceptableLossPct": d.max_acceptable_loss_pct,
                "notes": d.notes,
            },
            "observed": None
            if obs is None
            else {
                "sampleTradeCount": obs.sample_trade_count,
                "impulsivityScore": obs.impulsivity_score,
                "overtradingScore": obs.overtrading_score,
                "disciplineScore": obs.discipline_score,
                "divergesFromDeclared": obs.diverges_from_declared,
                "divergesFromPolicy": obs.diverges_from_policy,
                "lastObservedAt": obs.last_observed_at,
                "notes": list(obs.notes),
            },
            "suggestedPolicyTemplateId": self.suggested_policy_template_id,
            "updatedBy": self.updated_by,
            "updatedAt": self.updated_at,
            "createdAt": self.created_at,
        }
