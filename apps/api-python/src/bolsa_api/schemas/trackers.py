"""DTOs HTTP de trackers (Ayuda / Config)."""

from pydantic import BaseModel, ConfigDict, Field


class TrackerUniverseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    list_id: str | None = Field(default=None, alias="listId")
    instrument_ids: list[str] | None = Field(default=None, alias="instrumentIds")


class TrackerDefinitionSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    name: str
    strategy_definition_id: str = Field(alias="strategyDefinitionId")
    strategy_version: int | None = Field(default=None, alias="strategyVersion")
    timeframe: str
    evaluation_mode: str = Field(alias="evaluationMode")
    origin: str
    enabled: bool
    updated_at: str = Field(alias="updatedAt")
    created_at: str = Field(alias="createdAt")


class TrackerDefinitionDetailDto(TrackerDefinitionSummaryDto):
    definition: dict


class TrackerDefinitionsListResponseDto(BaseModel):
    data: list[TrackerDefinitionSummaryDto]


class TrackerDefinitionDetailsListResponseDto(BaseModel):
    data: list[TrackerDefinitionDetailDto]


class TrackerDefinitionResponseDto(BaseModel):
    data: TrackerDefinitionDetailDto


class CreateTrackerDefinitionRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    strategy_definition_id: str = Field(alias="strategyDefinitionId")
    universe: TrackerUniverseDto
    strategy_version: int | None = Field(default=None, alias="strategyVersion")
    timeframe: str = "1d"
    bar_limit: int = Field(default=500, alias="barLimit")
    max_results: int = Field(default=100, alias="maxResults")
    evaluation_mode: str = Field(default="bar_close", alias="evaluationMode")
    rank_by: dict | None = Field(default=None, alias="rankBy")
    default_execution_policy_id: str | None = Field(default=None, alias="defaultExecutionPolicyId")
    schedule: dict | None = None
    origin: str = "manual"
    source_prompt: str | None = Field(default=None, alias="sourcePrompt")
    enabled: bool = True


class UpdateTrackerDefinitionRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    universe: TrackerUniverseDto | None = None
    strategy_version: int | None = Field(default=None, alias="strategyVersion")
    timeframe: str | None = None
    bar_limit: int | None = Field(default=None, alias="barLimit")
    max_results: int | None = Field(default=None, alias="maxResults")
    evaluation_mode: str | None = Field(default=None, alias="evaluationMode")
    rank_by: dict | None = Field(default=None, alias="rankBy")
    default_execution_policy_id: str | None = Field(default=None, alias="defaultExecutionPolicyId")
    schedule: dict | None = None
    origin: str | None = None
    source_prompt: str | None = Field(default=None, alias="sourcePrompt")
    enabled: bool | None = None


class TrackerScheduleRunResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    tracker_id: str = Field(alias="trackerId")
    tracker_name: str = Field(alias="trackerName")
    status: str
    scan_job_id: str | None = Field(default=None, alias="scanJobId")
    latest_bar_timestamp: str | None = Field(default=None, alias="latestBarTimestamp")
    reason: str | None = None


class EvaluateTrackerSchedulesResponseDto(BaseModel):
    data: dict
