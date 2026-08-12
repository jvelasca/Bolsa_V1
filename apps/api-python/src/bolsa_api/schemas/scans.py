"""DTOs HTTP de escáneres / jobs."""

from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.schemas.signals_evaluate import SignalEventV1Dto


class ScanUniverseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    list_id: str | None = Field(default=None, alias="listId")
    instrument_ids: list[str] | None = Field(default=None, alias="instrumentIds")


class ScanRunRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    tracker_definition_id: str | None = Field(default=None, alias="trackerDefinitionId")
    definition: dict[str, object] | None = None
    preset_key: str | None = Field(default=None, alias="presetKey")
    universe: ScanUniverseDto
    timeframe: str = "1d"
    bar_limit: int = Field(default=500, alias="barLimit")
    max_results: int = Field(default=100, alias="maxResults")


class ScanSkippedInstrumentDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    reason: str


class ScanHitDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    name: str
    signal: SignalEventV1Dto


class ScanRunResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    scan_id: str = Field(alias="scanId")
    scanned_count: int = Field(alias="scannedCount")
    hit_count: int = Field(alias="hitCount")
    hits: list[ScanHitDto]
    skipped: list[ScanSkippedInstrumentDto]
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    list_id: str | None = Field(default=None, alias="listId")
    timeframe: str
    # Auto-ruta B1 (inform/alert) tras scan de rastreador.
    alarm_route: dict[str, object] | None = Field(default=None, alias="alarmRoute")


class ScanRunResponseDto(BaseModel):
    data: ScanRunResultDto


class ScanJobDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    status: str
    payload: dict[str, object]
    result: ScanRunResultDto | None = None
    error: str | None = None
    cache_hits: int | None = Field(default=None, alias="cacheHits")
    cache_misses: int | None = Field(default=None, alias="cacheMisses")
    tracker_definition_id: str | None = Field(default=None, alias="trackerDefinitionId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")


class ScanJobResponseDto(BaseModel):
    data: ScanJobDto


class ScanJobsListResponseDto(BaseModel):
    data: list[ScanJobDto]
