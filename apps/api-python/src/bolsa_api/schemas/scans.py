"""DTOs HTTP de escáneres / jobs."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.schemas.signals_evaluate import SignalEventV1Dto, to_signal_event_v1_dto
from bolsa_application.scans import ScanRunResult
from bolsa_infrastructure.database.repositories.scan_job_repository import ScanJobRecord


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


def to_scan_run_result_dto(
    result: ScanRunResult, *, alarm_route: dict[str, Any] | None = None
) -> ScanRunResultDto:
    return ScanRunResultDto(
        scan_id=result.scan_id,
        scanned_count=result.scanned_count,
        hit_count=result.hit_count,
        hits=[
            ScanHitDto(
                instrument_id=hit.instrument_id,
                symbol=hit.symbol,
                name=hit.name,
                signal=to_signal_event_v1_dto(hit.signal),
            )
            for hit in result.hits
        ],
        skipped=[
            ScanSkippedInstrumentDto(instrument_id=item.instrument_id, reason=item.reason)
            for item in result.skipped
        ],
        strategy_definition_id=result.strategy_definition_id,
        list_id=result.list_id,
        timeframe=result.timeframe,
        alarm_route=alarm_route,
    )


def _result_from_dict(raw: dict[str, Any]) -> ScanRunResultDto:
    return ScanRunResultDto.model_validate(raw)


def to_scan_job_dto(job: ScanJobRecord) -> ScanJobDto:
    result = _result_from_dict(job.result) if job.result is not None else None
    return ScanJobDto(
        id=job.id,
        status=job.status,
        payload=job.payload,
        result=result,
        error=job.error,
        cache_hits=job.cache_hits,
        cache_misses=job.cache_misses,
        tracker_definition_id=job.tracker_definition_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )
