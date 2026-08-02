"""ART-DECISION-MEMORY stub (RFC-008 D2.4 / D7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

MemoryOutcome = Literal["accepted", "rejected", "deferred"]


@dataclass(frozen=True, slots=True)
class DecisionMemoryEntry:
    memory_id: str
    decision_id: str
    instrument_id: str
    outcome: MemoryOutcome
    reasons: tuple[str, ...]
    policy_rule_ids: tuple[str, ...]
    reevaluate_when: tuple[str, ...]
    opportunity_intact: bool
    created_at: str
    artifact_type: str = "ART-DECISION-MEMORY"
    schema_version: str = "1.0.0"
    policy_id: str | None = None
    policy_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "memoryId": self.memory_id,
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "outcome": self.outcome,
            "reasons": list(self.reasons),
            "policyRuleIds": list(self.policy_rule_ids),
            "reevaluateWhen": list(self.reevaluate_when),
            "opportunityIntact": self.opportunity_intact,
            "policyId": self.policy_id,
            "policyVersion": self.policy_version,
            "createdAt": self.created_at,
        }


def build_memory_entry(
    *,
    decision_id: str,
    instrument_id: str,
    outcome: MemoryOutcome,
    reasons: list[str] | tuple[str, ...],
    policy_rule_ids: list[str] | tuple[str, ...] = (),
    reevaluate_when: list[str] | tuple[str, ...] = (),
    opportunity_intact: bool = True,
    policy_id: str | None = None,
    policy_version: str | None = None,
) -> DecisionMemoryEntry:
    return DecisionMemoryEntry(
        memory_id=f"MEM-{uuid4().hex[:12]}",
        decision_id=decision_id,
        instrument_id=instrument_id,
        outcome=outcome,
        reasons=tuple(reasons),
        policy_rule_ids=tuple(policy_rule_ids),
        reevaluate_when=tuple(reevaluate_when),
        opportunity_intact=opportunity_intact,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        policy_id=policy_id,
        policy_version=policy_version,
    )
