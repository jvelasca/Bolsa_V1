from dataclasses import dataclass
from typing import Any, Literal

KnowledgeStage = Literal[
    "CANDIDATE",
    "EMERGING",
    "ACCEPTED",
    "CANONICAL",
    "DEPRECATED",
]


@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    id: str
    hypothesis_id: str
    stage: KnowledgeStage
    statement: str
    knowledge_confidence: float
    validity_context: dict[str, Any]
    evidence_ids: list[str]
    belief_snapshot: dict[str, Any]
    consolidation_report: dict[str, Any]
    math_version: str
    consolidated_at: str
    created_at: str
    updated_at: str
    notes: str | None = None
