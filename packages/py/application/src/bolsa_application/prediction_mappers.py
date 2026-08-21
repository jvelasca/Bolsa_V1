"""Mappers ART-MODEL / ART-PREDICTION → records de dominio."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_domain.entities.cognitive_artifacts import ModelArtifactRecord, PredictionRecord


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def model_artifact_to_record(model: Any) -> ModelArtifactRecord:
    """Acepta ModelArtifact analytics o dict."""
    if hasattr(model, "to_dict"):
        payload = model.to_dict()
        model_id = model.model_id
        version = model.model_version
        framework = model.framework
        feature_set_id = model.feature_set_id
        composition_hash = model.composition_hash
        checksum = model.model_checksum
        trained_at = model.trained_at
    else:
        payload = dict(model)
        model_id = str(payload.get("modelId") or payload.get("id") or "")
        version = str(payload.get("modelVersion") or "1.0.0")
        framework = str(payload.get("framework") or "heuristic")
        feature_set_id = str(payload.get("featureSetId") or "")
        composition_hash = payload.get("compositionHash")
        checksum = payload.get("modelChecksum")
        trained_at = payload.get("trainedAt")
    return ModelArtifactRecord(
        id=model_id,
        model_id=model_id,
        model_version=version,
        framework=framework,
        feature_set_id=feature_set_id,
        created_at=_now_iso(),
        composition_hash=str(composition_hash) if composition_hash else None,
        model_checksum=str(checksum) if checksum else None,
        trained_at=str(trained_at) if trained_at else None,
        updated_at=_now_iso(),
        payload=payload,
    )


def prediction_to_record(prediction: Any) -> PredictionRecord:
    if hasattr(prediction, "to_dict"):
        payload = prediction.to_dict()
        pred_id = prediction.prediction_id
        instrument_id = prediction.instrument_id
        model_id = prediction.model_id
        model_version = prediction.model_version
        horizon = prediction.horizon
        value: float | None = float(prediction.value)
        confidence: float | None = float(prediction.confidence)
        as_of = prediction.as_of
        created = prediction.timestamp
    else:
        payload = dict(prediction)
        pred_id = str(payload.get("predictionId") or "")
        instrument_id = str(payload.get("instrumentId") or "")
        model_id = str(payload.get("modelId") or "")
        model_version = str(payload.get("modelVersion") or "")
        horizon = payload.get("horizon")
        value = float(payload["value"]) if payload.get("value") is not None else None
        confidence = (
            float(payload["confidence"]) if payload.get("confidence") is not None else None
        )
        as_of = payload.get("asOf")
        created = payload.get("timestamp") or _now_iso()
    return PredictionRecord(
        id=pred_id,
        instrument_id=instrument_id,
        model_id=model_id,
        model_version=model_version,
        created_at=str(created) if created else _now_iso(),
        horizon=str(horizon) if horizon else None,
        value=value,
        confidence=confidence,
        as_of=str(as_of) if as_of else None,
        payload=payload,
    )
