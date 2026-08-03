"""DTOs HTTP de definiciones de estrategia."""

from pydantic import BaseModel, ConfigDict, Field


class StrategyDefinitionSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    name: str
    preset_key: str | None = Field(default=None, alias="presetKey")
    origin: str
    timeframe: str
    kind: str
    instrument_ids: list[str] = Field(default_factory=list, alias="instrumentIds")
    updated_at: str = Field(alias="updatedAt")
    created_at: str = Field(alias="createdAt")


class StrategyDefinitionDetailDto(StrategyDefinitionSummaryDto):
    definition: dict


class StrategyDefinitionsListResponseDto(BaseModel):
    data: list[StrategyDefinitionSummaryDto]


class StrategyDefinitionResponseDto(BaseModel):
    data: StrategyDefinitionDetailDto


class CreateStrategyFromPresetRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    preset_key: str = Field(alias="presetKey")
    timeframe: str | None = None
    commission_bps: int | None = Field(default=None, alias="commissionBps")
    slippage_bps: int | None = Field(default=None, alias="slippageBps")


class UpsertStrategyDefinitionRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    definition: dict


class UpdateStrategyDefinitionRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    definition: dict | None = None


class DraftStrategyFromPromptRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str
    instrument_ids: list[str] | None = Field(default=None, alias="instrumentIds")


class DraftStrategyFromPromptResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    draft_kind: str = Field(alias="draftKind")
    preset_key: str = Field(alias="presetKey")
    timeframe: str
    suggested_name: str = Field(alias="suggestedName")
    confidence: float
    explanation: str
    definition: dict
    engine: str
    validated: bool
    gate_preset_key: str | None = Field(default=None, alias="gatePresetKey")
    min_score: float | None = Field(default=None, alias="minScore")
    feedback: dict | None = None


class DraftStrategyFromPromptResponseDto(BaseModel):
    data: DraftStrategyFromPromptResultDto
