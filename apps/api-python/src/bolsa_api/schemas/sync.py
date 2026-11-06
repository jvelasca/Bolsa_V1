"""DTOs HTTP de sync Yahoo/XTB / cola."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Universo de sincronización. Enum CERRADO: un valor fuera de contrato es 422, no una
#: cadena que el worker interpreta como quiera. ``all`` (alias histórico de la UI) queda
#: retirado; la UI usa ``stale``.
SyncScope = Literal["lists", "stale"]


class SyncSettingsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    auto_sync_enabled: bool = Field(alias="autoSyncEnabled")
    scan_interval_minutes: int = Field(alias="scanIntervalMinutes")
    min_delay_seconds: int = Field(alias="minDelaySeconds")
    post_market_only: bool = Field(alias="postMarketOnly")
    max_retries: int = Field(alias="maxRetries")
    retry_backoff_minutes: int = Field(alias="retryBackoffMinutes")
    scope: str
    # 060 — automatización de servidores (distinta de la de velas): solo mide conectividad.
    provider_check_enabled: bool = Field(alias="providerCheckEnabled")
    provider_check_interval_seconds: int = Field(alias="providerCheckIntervalSeconds")
    updated_at: str = Field(alias="updatedAt")


class UpdateSyncSettingsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    scope: SyncScope | None = None
    # 060 — política de comprobación de servidores. El rango es el del dominio
    # (``MIN/MAX_PROVIDER_CHECK_INTERVAL_SECONDS``); fuera de rango ⇒ 422, no se acota
    # en silencio desde la API.
    provider_check_enabled: bool | None = Field(alias="providerCheckEnabled", default=None)
    provider_check_interval_seconds: int | None = Field(
        alias="providerCheckIntervalSeconds",
        default=None,
        ge=15,
        le=3600,
    )


class SyncSettingsResponseDto(BaseModel):
    data: SyncSettingsDto


class SyncQueueItemDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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


class EnqueueStaleDataDto(BaseModel):
    """Resultado de encolar desactualizados, con el motivo declarado si no se encoló."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    scanned: int
    enqueued: int
    skipped_reason: str | None = Field(alias="skippedReason", default=None)


class EnqueueStaleResponseDto(BaseModel):
    data: EnqueueStaleDataDto
