"""EvidenceAssessment — credibilidad estadística (EdgeReport), no dirección."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from bolsa_analytics.cognitive.edge_report import EdgeBand, EdgeReport
from bolsa_analytics.knowledge.assessment import Assessment

# Evidence no es direccional: score ∈ [-1,1] refleja calidad del edge
# (skill→positivo, luck→negativo), no BUY/SELL.


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    """
    Interpretación del EdgeReport como Assessment type=evidence.
    No emite acción. El Runtime usa band/credibility para confianza / warnings.
    """

    assessment_id: str
    instrument_id: str
    timestamp: str
    score: float
    confidence: float
    band: EdgeBand
    credibility: float
    edge_score: float
    auto_live_eligible: bool
    narrative_facts: tuple[str, ...]
    warnings: tuple[str, ...]
    edge_report_ref: str
    assessment_type: str = "evidence"
    artifact_type: str = "ART-EVIDENCE-ASSESSMENT"
    schema_version: str = "1.0.0"

    @property
    def facts(self) -> tuple[str, ...]:
        return self.narrative_facts

    def as_assessment(self) -> Assessment:
        return Assessment(
            assessment_id=self.assessment_id,
            assessment_type="evidence",
            instrument_id=self.instrument_id,
            timestamp=self.timestamp,
            score=self.score,
            confidence=self.confidence,
            facts=self.narrative_facts,
            warnings=self.warnings,
            metadata={
                "band": self.band,
                "credibility": self.credibility,
                "edgeScore": self.edge_score,
                "autoLiveEligible": self.auto_live_eligible,
                "edgeReportRef": self.edge_report_ref,
                "directional": False,
                "specializedArtifactType": self.artifact_type,
            },
        )

    def to_assessment_dict(self) -> dict[str, Any]:
        return self.as_assessment().to_assessment_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "type": self.assessment_type,
            "assessmentId": self.assessment_id,
            "instrumentId": self.instrument_id,
            "timestamp": self.timestamp,
            "score": self.score,
            "confidence": self.confidence,
            "band": self.band,
            "credibility": self.credibility,
            "edgeScore": self.edge_score,
            "autoLiveEligible": self.auto_live_eligible,
            "narrativeFacts": list(self.narrative_facts),
            "facts": list(self.narrative_facts),
            "warnings": list(self.warnings),
            "edgeReportRef": self.edge_report_ref,
        }


def _score_from_band(band: EdgeBand, credibility: float) -> float:
    """Mapea calidad de edge a score no-direccional [-1, 1]."""
    # credibility 0–100 → [-1, 1] centrado en 65 (umbral uncertain)
    raw = (credibility - 65.0) / 35.0
    return round(max(-1.0, min(1.0, raw)), 4)


def build_evidence_assessment(
    instrument_id: str,
    edge_report: EdgeReport,
    *,
    auto_live_eligible: bool | None = None,
    block_reasons: tuple[str, ...] = (),
    assessment_id: str | None = None,
) -> EvidenceAssessment:
    eligible = (
        auto_live_eligible
        if auto_live_eligible is not None
        else edge_report.band == "skill"
    )
    conf = round(min(1.0, edge_report.credibility / 100.0), 3)
    score = _score_from_band(edge_report.band, edge_report.credibility)

    facts = [
        f"Edge band={edge_report.band}",
        f"Credibility={edge_report.credibility}",
        f"EdgeScore={edge_report.edge_score}",
        *edge_report.notes,
    ]
    warnings: list[str] = list(block_reasons)
    if edge_report.band == "luck":
        warnings.append("Edge band=luck — señal estadísticamente débil")
    elif edge_report.band == "uncertain":
        warnings.append("Edge band=uncertain — credibilidad intermedia")
    if not eligible:
        warnings.append("No elegible para auto-live")

    return EvidenceAssessment(
        assessment_id=assessment_id or f"EA-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=edge_report.created_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        score=score,
        confidence=conf,
        band=edge_report.band,
        credibility=edge_report.credibility,
        edge_score=edge_report.edge_score,
        auto_live_eligible=eligible,
        narrative_facts=tuple(facts),
        warnings=tuple(warnings),
        edge_report_ref=edge_report.edge_report_id,
    )
