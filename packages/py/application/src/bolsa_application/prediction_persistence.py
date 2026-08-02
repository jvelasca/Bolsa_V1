"""Casos de uso — persistencia Prediction / ModelArtifact (F2)."""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_domain.entities.cognitive_artifacts import ModelArtifactRecord, PredictionRecord

from bolsa_application.prediction_mappers import model_artifact_to_record, prediction_to_record


class PredictionStore(Protocol):
    async def upsert_model(self, record: ModelArtifactRecord) -> ModelArtifactRecord: ...

    async def list_models(self, *, limit: int = 50) -> list[ModelArtifactRecord]: ...

    async def append_prediction(self, record: PredictionRecord) -> PredictionRecord: ...

    async def list_predictions(
        self,
        *,
        instrument_id: str | None = None,
        model_id: str | None = None,
        limit: int = 40,
    ) -> list[PredictionRecord]: ...


class PersistPredictionArtifacts:
    """Best-effort: escribe model + prediction en PG."""

    def __init__(self, store: PredictionStore) -> None:
        self._store = store

    async def persist_model(self, model: Any) -> ModelArtifactRecord:
        return await self._store.upsert_model(model_artifact_to_record(model))

    async def persist_prediction(
        self,
        prediction: Any,
        *,
        also_model: Any | None = None,
    ) -> PredictionRecord:
        if also_model is not None:
            try:
                await self.persist_model(also_model)
            except Exception:  # noqa: BLE001
                pass
        return await self._store.append_prediction(prediction_to_record(prediction))
