"""IPredictionPort — RUNTIME (RFC-004 / RFC-006)."""

from __future__ import annotations

from typing import Protocol

from bolsa_analytics.features.models import FeatureSnapshot
from bolsa_analytics.prediction.models import ModelArtifact, Prediction


class IPredictionPort(Protocol):
    def predict(
        self,
        *,
        instrument_id: str,
        snapshot: FeatureSnapshot,
        model_id: str | None = None,
        horizon: str = "1d",
    ) -> Prediction: ...

    def get_model(self, model_id: str) -> ModelArtifact | None: ...

    def list_models(self) -> list[ModelArtifact]: ...
