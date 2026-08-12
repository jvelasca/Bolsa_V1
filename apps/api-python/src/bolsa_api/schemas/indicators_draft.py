"""DTOs HTTP de borradores de indicadores."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DraftIndicatorFromPromptRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str
    chart_timeframe: str | None = Field(default=None, alias="chartTimeframe")


class DraftIndicatorFromPromptResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    definition_id: str = Field(alias="definitionId")
    suggested_preset_name: str = Field(alias="suggestedPresetName")
    confidence: float
    explanation: str
    preset: dict[str, Any]
    engine: str
    validated: bool
    feedback: dict[str, Any] | None = None


class DraftIndicatorFromPromptResponseDto(BaseModel):
    data: DraftIndicatorFromPromptResultDto
