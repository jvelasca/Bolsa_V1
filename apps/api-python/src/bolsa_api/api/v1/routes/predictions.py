"""Prediction Registry HTTP (F2 / RFC-006) — Quant Runtime + PG."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.prediction import PredictionService, lightgbm_available
from bolsa_analytics.signals.technical_rating_v1 import MODEL_ID as HEURISTIC_MODEL_ID
from bolsa_api.api.dependencies import (
    get_db_session,
    get_ohlcv_repository,
    get_prediction_repository,
)
from bolsa_application.prediction_persistence import PersistPredictionArtifacts
from bolsa_domain.value_objects.timeframe import TimeFrame

router = APIRouter()


def get_prediction_service() -> PredictionService:
    return PredictionService()


class PredictRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    model_id: str | None = Field(default=None, alias="modelId")
    timeframe: str = "1d"
    bar_limit: int = Field(default=120, alias="barLimit", ge=40, le=2000)
    horizon: str = "1d"


class TrainRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    timeframe: str = "1d"
    bar_limit: int = Field(default=250, alias="barLimit", ge=80, le=2000)


async def _load_bars(
    session: AsyncSession, instrument_id: str, timeframe: str, bar_limit: int
) -> list[OhlcvBar]:
    try:
        tf = TimeFrame(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"timeframe inválido: {timeframe}") from exc
    ohlcv = get_ohlcv_repository(session)
    bars = await ohlcv.get_bars(instrument_id, timeframe=tf, limit=bar_limit)
    if not bars:
        raise HTTPException(status_code=404, detail="Sin OHLCV para el instrumento")
    return [
        OhlcvBar(
            timestamp=bar.timestamp,
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=float(bar.volume or 0),
        )
        for bar in bars
    ]


@router.get("/predictions/models")
async def list_prediction_models(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    svc: Annotated[PredictionService, Depends(get_prediction_service)],
) -> dict[str, Any]:
    # Memoria + PG (payloads PG ganan si hay colisión de modelId)
    by_id: dict[str, dict[str, Any]] = {m.model_id: m.to_dict() for m in svc.list_models()}
    try:
        store = get_prediction_repository(session)
        for rec in await store.list_models(limit=50):
            if rec.payload:
                by_id[rec.model_id] = rec.payload
            else:
                by_id[rec.model_id] = {
                    "modelId": rec.model_id,
                    "modelVersion": rec.model_version,
                    "framework": rec.framework,
                    "featureSetId": rec.feature_set_id,
                }
    except Exception:  # noqa: BLE001 — list no tumba si falta migración
        pass
    return {
        "data": {
            "models": list(by_id.values()),
            "lightgbmAvailable": lightgbm_available(),
            "defaultModelId": HEURISTIC_MODEL_ID,
            "persistence": "postgres+memory",
        }
    }


@router.get("/predictions")
async def list_predictions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
    model_id: Annotated[str | None, Query(alias="modelId")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 40,
) -> dict[str, Any]:
    store = get_prediction_repository(session)
    rows = await store.list_predictions(
        instrument_id=instrument_id, model_id=model_id, limit=limit
    )
    return {
        "data": [
            r.payload
            or {
                "predictionId": r.id,
                "instrumentId": r.instrument_id,
                "modelId": r.model_id,
                "value": r.value,
                "confidence": r.confidence,
            }
            for r in rows
        ]
    }


@router.post("/predictions/predict")
async def predict(
    body: PredictRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    svc: Annotated[PredictionService, Depends(get_prediction_service)],
) -> dict[str, Any]:
    bars = await _load_bars(session, body.instrument_id, body.timeframe, body.bar_limit)
    try:
        pred = svc.predict(
            instrument_id=body.instrument_id,
            bars=bars,
            model_id=body.model_id,
            horizon=body.horizon,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        model = svc.get_model(pred.model_id)
        await PersistPredictionArtifacts(get_prediction_repository(session)).persist_prediction(
            pred, also_model=model
        )
    except Exception:  # noqa: BLE001 — predict no tumba por PG
        pass
    return {"data": pred.to_dict()}


@router.post("/predictions/models/train")
async def train_direction_model_route(
    body: TrainRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    svc: Annotated[PredictionService, Depends(get_prediction_service)],
) -> dict[str, Any]:
    """Entrena lgbm_direction_v1 (o numpy_fallback) sobre OHLCV del instrumento."""
    bars = await _load_bars(session, body.instrument_id, body.timeframe, body.bar_limit)
    try:
        model = svc.train_direction(bars)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        await PersistPredictionArtifacts(get_prediction_repository(session)).persist_model(model)
    except Exception:  # noqa: BLE001
        pass
    return {"data": model.to_dict()}
