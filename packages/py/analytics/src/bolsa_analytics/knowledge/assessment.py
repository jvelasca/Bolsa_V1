"""Assessment — contrato común de interpretación (RFC-008 Amendment-2).

Evidence = observación
Assessment = interpretación estructurada (no BUY)
Decision = acción (solo DecisionRuntime)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

AssessmentType = Literal[
    "technical",
    "fundamental",
    "macro",
    "news",
    "sentiment",
    "evidence",
]


@runtime_checkable
class AssessmentLike(Protocol):
    """Lo que el DecisionRuntime necesita — no conoce el motor concreto."""

    @property
    def assessment_id(self) -> str: ...

    @property
    def assessment_type(self) -> str: ...

    @property
    def instrument_id(self) -> str: ...

    @property
    def timestamp(self) -> str: ...

    @property
    def score(self) -> float: ...

    @property
    def confidence(self) -> float: ...

    @property
    def facts(self) -> tuple[str, ...]: ...

    @property
    def warnings(self) -> tuple[str, ...]: ...

    def to_assessment_dict(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class Assessment:
    """
    Envelope común. Fund/News/Macro emitirán el mismo shape.
    Campos específicos del motor van en `metadata` (bias, components, …).
    """

    assessment_id: str
    assessment_type: AssessmentType
    instrument_id: str
    timestamp: str
    score: float
    confidence: float
    facts: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifact_type: str = "ART-ASSESSMENT"
    schema_version: str = "1.0.0"

    def to_assessment_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "assessmentId": self.assessment_id,
            "type": self.assessment_type,
            "instrumentId": self.instrument_id,
            "timestamp": self.timestamp,
            "score": self.score,
            "confidence": self.confidence,
            "facts": list(self.facts),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    # Alias Protocol
    def to_dict(self) -> dict[str, Any]:
        return self.to_assessment_dict()
