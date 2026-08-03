"""API: replay de dibujos sobre series OHLCV."""

from fastapi import APIRouter, HTTPException

from bolsa_analytics.drawing_replay import OhlcvBar, evaluate_drawing_replay
from bolsa_api.schemas.drawing_replay import (
    DrawingReplayMarkerDto,
    DrawingReplayRequestDto,
    DrawingReplayResponseDto,
)

router = APIRouter()


@router.post("/drawings/replay", response_model=DrawingReplayResponseDto)
async def replay_drawings(body: DrawingReplayRequestDto) -> DrawingReplayResponseDto:
    if not body.bars:
        raise HTTPException(status_code=400, detail="bars must not be empty")
    if not body.drawings:
        raise HTTPException(status_code=400, detail="drawings must not be empty")
    if len(body.bars) > 5000:
        raise HTTPException(status_code=400, detail="bars limit is 5000")

    bars = [OhlcvBar(timestamp=bar.timestamp, close=bar.close) for bar in body.bars]
    markers = evaluate_drawing_replay(
        bars,
        body.drawings,
        alert_drawings_only=body.alert_drawings_only,
    )

    return DrawingReplayResponseDto(
        data=[
            DrawingReplayMarkerDto(
                id=marker.id,
                drawing_id=marker.drawing_id,
                timestamp=marker.timestamp,
                price=marker.price,
                level=marker.level,
                direction=marker.direction,
                drawing_type=marker.drawing_type,
                label=marker.label,
            )
            for marker in markers
        ],
    )
