"""DTOs HTTP de replay de dibujos sobre OHLCV."""

from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.schemas.indicators_compute import OhlcvBarInputDto


class DrawingReplayRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    bars: list[OhlcvBarInputDto]
    drawings: list[dict[str, object]]
    alert_drawings_only: bool = Field(default=True, alias="alertDrawingsOnly")


class DrawingReplayMarkerDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    drawing_id: str = Field(alias="drawingId")
    timestamp: str
    price: float
    level: float
    direction: str
    drawing_type: str = Field(alias="drawingType")
    label: str | None = None


class DrawingReplayResponseDto(BaseModel):
    data: list[DrawingReplayMarkerDto]
