"""Feature Registry HTTP (RFC-005) — lectura vía IFeaturePort / catálogo."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.features import bootstrap_catalog, materialize_feature_snapshot
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_api.api.dependencies import get_db_session, get_feature_port, get_ohlcv_repository
from bolsa_domain.value_objects.timeframe import TimeFrame

router = APIRouter()


class FeatureDefDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    feature_id: str = Field(alias="featureId")
    feature_key: str = Field(alias="featureKey")
    version: str
    compute_key: str = Field(alias="computeKey")
    parity_ref: str | None = Field(default=None, alias="parityRef")
    params: dict[str, Any]


class FeatureSetDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    feature_set_id: str = Field(alias="featureSetId")
    version: str
    name: str
    composition_hash: str = Field(alias="compositionHash")
    member_count: int = Field(alias="memberCount")


class FeatureSnapshotDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    feature_set_id: str = Field(alias="featureSetId")
    composition_hash: str = Field(alias="compositionHash")
    timestamp: str
    values: dict[str, float | None]


@router.get("/features/catalog")
async def list_feature_catalog() -> dict[str, Any]:
    catalog = bootstrap_catalog()
    feature_set = catalog.get_set("fset_core_v1")
    return {
        "data": {
            "defs": [
                FeatureDefDto(
                    feature_id=d.feature_id,
                    feature_key=d.feature_key,
                    version=d.version,
                    compute_key=d.compute_key,
                    parity_ref=d.parity_ref,
                    params=dict(d.params),
                ).model_dump(by_alias=True)
                for d in catalog.list_defs()
            ],
            "sets": [
                FeatureSetDto(
                    feature_set_id=feature_set.feature_set_id,
                    version=feature_set.version,
                    name=feature_set.name,
                    composition_hash=feature_set.composition_hash,
                    member_count=len(feature_set.members),
                ).model_dump(by_alias=True)
            ],
        }
    }


@router.get("/features/latest")
async def get_feature_latest(
    instrument_id: Annotated[str, Query(alias="instrumentId")],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    feature_set_id: Annotated[str, Query(alias="featureSetId")] = "fset_core_v1",
    timeframe: str = "1d",
    bar_limit: Annotated[int, Query(alias="barLimit", ge=30, le=2000)] = 120,
) -> dict[str, Any]:
    """Materializa ART-FEATURE-SNAP latest y lo sirve vía IFeaturePort."""
    try:
        tf = TimeFrame(timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"timeframe inválido: {timeframe}") from exc

    ohlcv = get_ohlcv_repository(session)
    feature_port = get_feature_port()
    bars = await ohlcv.get_bars(instrument_id, timeframe=tf, limit=bar_limit)
    if not bars:
        raise HTTPException(status_code=404, detail="Sin OHLCV para el instrumento")

    ohlcv_bars = [
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
    snap = materialize_feature_snapshot(
        feature_port,
        instrument_id=instrument_id,
        bars=ohlcv_bars,
        feature_set_id=feature_set_id,
    )
    if snap is None:
        raise HTTPException(status_code=422, detail="No se pudo materializar el FeatureSet")

    latest = feature_port.get_latest(instrument_id, feature_set_id)
    assert latest is not None
    return {
        "data": FeatureSnapshotDto(
            instrument_id=latest.instrument_id,
            feature_set_id=latest.feature_set_id,
            composition_hash=latest.composition_hash,
            timestamp=latest.timestamp.isoformat(),
            values={k: (float(v) if v is not None else None) for k, v in latest.values.items()},
        ).model_dump(by_alias=True)
    }
