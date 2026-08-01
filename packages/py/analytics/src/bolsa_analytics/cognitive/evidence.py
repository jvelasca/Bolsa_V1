"""ART-EVIDENCE-BUNDLE — evidencias tipadas (RFC-008)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EvidenceDirection = Literal["supports", "contradicts", "neutral"]
EvidenceKind = Literal[
    "data_quality",
    "market_regime",
    "technical",
    "fundamental",
    "opportunity",
    "news_event",
    "macro",
    "risk",
    "policy",
    "statistical",
]


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    evidence_kind: EvidenceKind
    claim: str
    direction: EvidenceDirection
    weight: float
    confidence: float
    valid_from: str | None = None
    valid_to: str | None = None
    decay_half_life_hours: float | None = None
    refs: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidenceId": self.evidence_id,
            "evidenceKind": self.evidence_kind,
            "claim": self.claim,
            "direction": self.direction,
            "weight": self.weight,
            "confidence": self.confidence,
            "validFrom": self.valid_from,
            "validTo": self.valid_to,
            "decayHalfLifeHours": self.decay_half_life_hours,
            "refs": self.refs,
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    bundle_id: str
    instrument_id: str
    timestamp: str
    evidences: tuple[Evidence, ...]
    artifact_type: str = "ART-EVIDENCE-BUNDLE"
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "bundleId": self.bundle_id,
            "instrumentId": self.instrument_id,
            "timestamp": self.timestamp,
            "evidences": [e.to_dict() for e in self.evidences],
        }
