"""DTOs HTTP de eventos de plataforma."""

from pydantic import BaseModel, ConfigDict, Field


class PlatformEventDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    type: str
    timestamp: str
    payload: dict
    correlation_id: str | None = Field(default=None, alias="correlationId")


class PlatformEventsListResponseDto(BaseModel):
    data: list[PlatformEventDto]
