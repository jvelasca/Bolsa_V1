"""Registro en memoria de ModelArtifact + últimas Predictions."""

from __future__ import annotations

from bolsa_analytics.prediction.models import ModelArtifact, Prediction


class InMemoryPredictionRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ModelArtifact] = {}
        self._latest: dict[tuple[str, str], Prediction] = {}  # (instrument, model) → pred

    def register_model(self, model: ModelArtifact) -> None:
        self._models[model.model_id] = model

    def get_model(self, model_id: str) -> ModelArtifact | None:
        return self._models.get(model_id)

    def list_models(self) -> list[ModelArtifact]:
        return list(self._models.values())

    def put_prediction(self, prediction: Prediction) -> None:
        self._latest[(prediction.instrument_id, prediction.model_id)] = prediction

    def get_latest(self, instrument_id: str, model_id: str) -> Prediction | None:
        return self._latest.get((instrument_id, model_id))


# Proceso compartido (API + tests)
GLOBAL_PREDICTION_REGISTRY = InMemoryPredictionRegistry()
