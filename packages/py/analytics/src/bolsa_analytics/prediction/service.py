"""Servicio Prediction — registry + heuristic / LightGBM."""

from __future__ import annotations

from bolsa_analytics.features.models import FeatureSnapshot
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.prediction.heuristic import (
    heuristic_model_artifact,
    prediction_from_technical_rating,
)
from bolsa_analytics.prediction.lightgbm_direction import (
    MODEL_ID as LGBM_MODEL_ID,
)
from bolsa_analytics.prediction.lightgbm_direction import (
    predict_direction,
    train_direction_model,
)
from bolsa_analytics.prediction.models import ModelArtifact, Prediction
from bolsa_analytics.prediction.registry import (
    GLOBAL_PREDICTION_REGISTRY,
    InMemoryPredictionRegistry,
)
from bolsa_analytics.signals.technical_rating_v1 import MODEL_ID as HEURISTIC_MODEL_ID


class PredictionService:
    def __init__(self, registry: InMemoryPredictionRegistry | None = None) -> None:
        self._registry = registry or GLOBAL_PREDICTION_REGISTRY
        # Asegurar modelo heurístico siempre registrado
        if self._registry.get_model(HEURISTIC_MODEL_ID) is None:
            self._registry.register_model(heuristic_model_artifact())

    def list_models(self) -> list[ModelArtifact]:
        return self._registry.list_models()

    def get_model(self, model_id: str) -> ModelArtifact | None:
        return self._registry.get_model(model_id)

    def train_direction(self, bars: list[OhlcvBar]) -> ModelArtifact:
        model = train_direction_model(bars)
        self._registry.register_model(model)
        return model

    def predict(
        self,
        *,
        instrument_id: str,
        bars: list[OhlcvBar],
        model_id: str | None = None,
        snapshot: FeatureSnapshot | None = None,
        horizon: str = "1d",
    ) -> Prediction:
        mid = model_id or HEURISTIC_MODEL_ID
        if mid == HEURISTIC_MODEL_ID:
            pred = prediction_from_technical_rating(
                bars, instrument_id=instrument_id, snapshot=snapshot, horizon=horizon
            )
            if pred is None:
                raise ValueError("No se pudo calcular technical_rating_v1")
            self._registry.put_prediction(pred)
            return pred

        model = self._registry.get_model(mid)
        if model is None:
            raise ValueError(f"Modelo no registrado: {mid}")
        if mid == LGBM_MODEL_ID or model.framework in {"lightgbm", "numpy_fallback"}:
            pred = predict_direction(
                model, bars, instrument_id=instrument_id, snapshot=snapshot, horizon=horizon
            )
            self._registry.put_prediction(pred)
            return pred
        raise ValueError(f"Framework no soportado para predict: {model.framework}")
