from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class HypothesisBelief:
    id: str
    hypothesis_id: str
    belief: float
    belief_ci_low: float
    belief_ci_high: float
    n_experiments: int
    evidence_weight: float
    contexts_ok: list[str]
    contexts_fail: list[str]
    evidence_ids: list[str]
    trial_ids: list[str]
    math_version: str
    last_reviewed_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class BeliefHistoryEntry:
    id: str
    hypothesis_id: str
    belief_id: str
    belief: float
    belief_ci_low: float
    belief_ci_high: float
    n_experiments: int
    evidence_weight: float
    math_version: str
    created_at: str
    trigger_evidence_id: str | None = None
    delta: dict[str, Any] | None = None
