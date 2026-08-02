from pydantic import BaseModel, ConfigDict, Field


class SyncSettingsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    auto_sync_enabled: bool = Field(alias="autoSyncEnabled")
    scan_interval_minutes: int = Field(alias="scanIntervalMinutes")
    min_delay_seconds: int = Field(alias="minDelaySeconds")
    post_market_only: bool = Field(alias="postMarketOnly")
    max_retries: int = Field(alias="maxRetries")
    retry_backoff_minutes: int = Field(alias="retryBackoffMinutes")
    scope: str
    updated_at: str = Field(alias="updatedAt")


class UpdateSyncSettingsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    auto_sync_enabled: bool | None = Field(alias="autoSyncEnabled", default=None)
    scan_interval_minutes: int | None = Field(
        alias="scanIntervalMinutes",
        default=None,
        ge=5,
        le=1440,
    )
    min_delay_seconds: int | None = Field(alias="minDelaySeconds", default=None, ge=1, le=120)
    post_market_only: bool | None = Field(alias="postMarketOnly", default=None)
    max_retries: int | None = Field(alias="maxRetries", default=None, ge=1, le=20)
    retry_backoff_minutes: int | None = Field(
        alias="retryBackoffMinutes",
        default=None,
        ge=5,
        le=1440,
    )
    scope: str | None = None


class SyncSettingsResponseDto(BaseModel):
    data: SyncSettingsDto


class SyncQueueItemDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    status: str
    priority: int
    scheduled_at: str = Field(alias="scheduledAt")
    attempts: int
    last_error: str | None = Field(alias="lastError")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class SyncQueueResponseDto(BaseModel):
    data: list[SyncQueueItemDto]


class EnqueueStaleResponseDto(BaseModel):
    data: dict[str, int]
