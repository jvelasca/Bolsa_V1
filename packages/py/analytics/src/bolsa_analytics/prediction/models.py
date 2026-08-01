"""PredictionV1 + ModelArtifact (RFC-006) — Quant Runtime, sin LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

Framework = Literal["lightgbm", "heuristic", "numpy_fallback"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    model_id: str
    model_version: str
    framework: Framework
    feature_set_id: str
    composition_hash: str
    target_name: str
    target_type: Literal["continuous", "class", "rank"]
    model_checksum: str
    metrics: dict[str, float | None] = field(default_factory=dict)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    trained_at: str | None = None
    artifact_type: str = "ART-MODEL"
    # Bytes o pesos serializados (en memoria)
    binary: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "modelId": self.model_id,
            "modelVersion": self.model_version,
            "framework": self.framework,
            "featureSetId": self.feature_set_id,
            "compositionHash": self.composition_hash,
            "target": {"name": self.target_name, "type": self.target_type},
            "metrics": self.metrics,
            "modelChecksum": self.model_checksum,
            "hyperparameters": self.hyperparameters,
            "trainedAt": self.trained_at,
            "hasBinary": self.binary is not None,
        }


@dataclass(frozen=True, slots=True)
class Prediction:
    prediction_id: str
    instrument_id: str
    model_id: str
    model_version: str
    model_checksum: str
    feature_set_id: str
    composition_hash: str
    timestamp: str
    as_of: str
    horizon: str
    value: float
    confidence: float
    feature_snapshot_id: str | None = None
    probabilities: dict[str, float] | None = None
    data_version: str | None = None
    trace_id: str | None = None
    schema_version: str = "1.0.0"
    artifact_type: str = "ART-PREDICTION"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "predictionId": self.prediction_id,
            "instrumentId": self.instrument_id,
            "modelId": self.model_id,
            "modelVersion": self.model_version,
            "modelChecksum": self.model_checksum,
            "featureSetId": self.feature_set_id,
            "compositionHash": self.composition_hash,
            "featureSnapshotId": self.feature_snapshot_id,
            "timestamp": self.timestamp,
            "asOf": self.as_of,
            "horizon": self.horizon,
            "value": self.value,
            "confidence": self.confidence,
            "dataVersion": self.data_version,
            "traceId": self.trace_id,
        }
        if self.probabilities is not None:
            data["probabilities"] = self.probabilities
        return data


def new_prediction_id() -> str:
    return f"PRED-{uuid4().hex[:12]}"
