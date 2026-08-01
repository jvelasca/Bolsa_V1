"""ART-PROFILE — catálogo de perfiles de inversor (RFC-008)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InvestorProfileRecord:
    id: str
    name: str
    version: str
    horizon: str
    objectives: tuple[str, ...]
    risk_tolerance: str
    experience: str
    suggested_policy_template_id: str
    selected_policy_template_id: str
    updated_by: str
    created_at: str
    updated_at: str
    user_id: str | None = None
    max_acceptable_loss_pct: float | None = None
    notes: str | None = None
    observed: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": "ART-PROFILE",
            "schemaVersion": "1.0.0",
            "profileId": self.id,
            "name": self.name,
            "version": self.version,
            "userId": self.user_id,
            "declared": {
                "horizon": self.horizon,
                "objectives": list(self.objectives),
                "riskTolerance": self.risk_tolerance,
                "experience": self.experience,
                "maxAcceptableLossPct": self.max_acceptable_loss_pct,
                "notes": self.notes,
            },
            "suggestedPolicyTemplateId": self.suggested_policy_template_id,
            "selectedPolicyTemplateId": self.selected_policy_template_id,
            "observed": self.observed,
            "updatedBy": self.updated_by,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
