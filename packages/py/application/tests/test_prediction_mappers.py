"""Mappers Prediction / ModelArtifact → records."""

from datetime import UTC

from bolsa_analytics.prediction import PredictionService
from bolsa_analytics.prediction.heuristic import heuristic_model_artifact
from bolsa_application.prediction_mappers import model_artifact_to_record, prediction_to_record


def test_model_artifact_to_record():
    model = heuristic_model_artifact()
    rec = model_artifact_to_record(model)
    assert rec.id == model.model_id
    assert rec.payload is not None
    assert rec.payload["modelId"] == model.model_id


def test_prediction_to_record():
    from datetime import datetime

    # Minimal via service heuristic needs bars — build Prediction manually
    from bolsa_analytics.prediction.models import Prediction

    pred = Prediction(
        prediction_id="P-1",
        instrument_id="inst-1",
        model_id="technical_rating_v1",
        model_version="1.0.0",
        model_checksum="x",
        feature_set_id="fset_core_v1",
        composition_hash="h",
        timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        as_of=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        horizon="1d",
        value=0.4,
        confidence=0.7,
    )
    rec = prediction_to_record(pred)
    assert rec.id == "P-1"
    assert rec.value == 0.4
    assert rec.payload["modelId"] == "technical_rating_v1"


def test_prediction_service_still_works():
    svc = PredictionService()
    assert any(m.model_id == "technical_rating_v1" for m in svc.list_models())
