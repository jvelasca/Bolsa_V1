"""Entidad de dominio de evidencia de investigación — sin dependencias externas."""
from dataclasses import dataclass
from typing import Any, Literal

EvidenceLevel = Literal["A", "B", "C", "D"]
EvidenceSource = Literal[
    "trial_is",
    "holdout",
    "walkforward",
    "cpcv",
    "narrative",
    "dia_d_session",
]


@dataclass(frozen=True, slots=True)
class ResearchEvidence:
    id: str
    instrument_id: str
    level: EvidenceLevel
    source: EvidenceSource
    evidence_weight: float
    summary: dict[str, Any]
    created_at: str
    trial_id: str | None = None
    hypothesis_id: str | None = None
    edge_report_id: str | None = None
    math_version: str | None = None
