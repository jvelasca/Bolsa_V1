from bolsa_analytics.signals.strategy import StrategyBarInput, evaluate_strategy
from fastapi import APIRouter, HTTPException

from bolsa_api.schemas.signals_evaluate import (
    EvaluateSignalsRequestDto,
    EvaluateSignalsResponseDto,
    SignalEventV1Dto,
)

router = APIRouter()


@router.post("/signals/evaluate", response_model=EvaluateSignalsResponseDto)
async def evaluate_signals(body: EvaluateSignalsRequestDto) -> EvaluateSignalsResponseDto:
    if not body.bars:
        raise HTTPException(status_code=400, detail="bars must not be empty")
    if len(body.bars) > 5000:
        raise HTTPException(status_code=400, detail="bars limit is 5000")
    if body.mode not in {"raw", "gated"}:
        raise HTTPException(status_code=400, detail="mode must be raw or gated")

    bars = [StrategyBarInput(timestamp=bar.timestamp, close=bar.close) for bar in body.bars]

    try:
        events = evaluate_strategy(
            body.definition,
            bars,
            instrument_id=body.instrument_id,
            mode=body.mode,  # type: ignore[arg-type]
            data_version=body.data_version,
            indicator_snapshot_hash=body.indicator_snapshot_hash,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EvaluateSignalsResponseDto(
        data=[
            SignalEventV1Dto(
                id=event.id,
                instrument_id=event.instrument_id,
                timestamp=event.timestamp,
                kind=event.kind,
                strategy_definition_id=event.strategy_definition_id,
                strategy_version=event.strategy_version,
                bar_index=event.bar_index,
                price=event.price,
                data_version=event.data_version,
                indicator_snapshot_hash=event.indicator_snapshot_hash,
                preset_key=event.preset_key,
            )
            for event in events
        ],
    )
