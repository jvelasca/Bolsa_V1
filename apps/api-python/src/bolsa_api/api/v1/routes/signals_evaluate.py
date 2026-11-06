"""API: evaluación de señales / presets."""

from fastapi import APIRouter, HTTPException

from bolsa_analytics.signals.strategy import (
    SignalEventV1,
    StrategyBarInput,
    evaluate_strategy,
)
from bolsa_api.schemas.signals_evaluate import (
    EvaluateSignalsRequestDto,
    EvaluateSignalsResponseDto,
    to_signal_event_v1_dto,
)

router = APIRouter()


def _assert_timing_contract(events: list[SignalEventV1]) -> None:
    """S4 — la ejecución debe ser posterior a la señal; lo contrario es lookahead.

    Los eventos los produce este mismo motor, así que una violación es un fallo de
    contrato interno: se responde 500 en vez de publicar una señal no ejecutable.
    """
    for event in events:
        if event.has_lookahead():
            raise HTTPException(
                status_code=500,
                detail=(
                    "signal timing contract violated: "
                    f"executionBar={event.resolved_execution_bar} must be > "
                    f"signalBar={event.resolved_signal_bar} (signal {event.id})"
                ),
            )


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

    _assert_timing_contract(events)

    return EvaluateSignalsResponseDto(
        data=[to_signal_event_v1_dto(event) for event in events],
    )
