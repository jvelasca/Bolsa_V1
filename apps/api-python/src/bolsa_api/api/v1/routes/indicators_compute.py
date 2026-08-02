from bolsa_analytics.indicators.compute import IndicatorSpecInput, OhlcvBar, compute_specs
from fastapi import APIRouter, HTTPException

from bolsa_api.schemas.indicators_compute import (
    ComputeIndicatorsRequestDto,
    ComputeIndicatorsResponseDto,
    IndicatorLinePointDto,
    IndicatorLineSeriesDto,
    IndicatorSpecSeriesDto,
)

router = APIRouter()


@router.post("/indicators/compute", response_model=ComputeIndicatorsResponseDto)
async def compute_indicators(body: ComputeIndicatorsRequestDto) -> ComputeIndicatorsResponseDto:
    if not body.bars:
        raise HTTPException(status_code=400, detail="bars must not be empty")
    if not body.specs:
        raise HTTPException(status_code=400, detail="specs must not be empty")
    if len(body.bars) > 5000:
        raise HTTPException(status_code=400, detail="bars limit is 5000")

    bars = [
        OhlcvBar(
            timestamp=bar.timestamp,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )
        for bar in body.bars
    ]
    specs = [
        IndicatorSpecInput(definition_id=spec.definition_id, parameters=dict(spec.parameters))
        for spec in body.specs
    ]

    try:
        results = compute_specs(bars, specs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ComputeIndicatorsResponseDto(
        data=[
            IndicatorSpecSeriesDto(
                definition_id=result.definition_id,
                parameters=result.parameters,
                spec_key=result.spec_key,
                lines=[
                    IndicatorLineSeriesDto(
                        key=line.key,
                        points=[
                            IndicatorLinePointDto(timestamp=point.timestamp, value=point.value)
                            for point in line.points
                        ],
                    )
                    for line in result.lines
                ],
            )
            for result in results
        ],
    )
