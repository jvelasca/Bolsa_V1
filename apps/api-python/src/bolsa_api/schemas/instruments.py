"""DTOs HTTP de instrumentos / catálogo."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.schemas.market import SyncResultDto


class SyncMetaDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: str
    synced_at: str = Field(alias="syncedAt")
    error: str | None


class SyncDetailDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: str
    bars_added: int = Field(alias="barsAdded")
    synced_at: str = Field(alias="syncedAt")
    error: str | None


class InstrumentDataStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    timeframe: str
    last_bar_date: str | None = Field(alias="lastBarDate", default=None)
    expected_last_bar_date: str = Field(alias="expectedLastBarDate")
    freshness_status: str = Field(alias="freshnessStatus")
    bar_count: int = Field(alias="barCount")
    last_sync_status: str | None = Field(alias="lastSyncStatus", default=None)
    last_sync_at: str | None = Field(alias="lastSyncAt", default=None)
    last_sync_error: str | None = Field(alias="lastSyncError", default=None)
    sanity_warnings: list[str] = Field(alias="sanityWarnings", default_factory=list)
    gap_count: int = Field(alias="gapCount", default=0)
    xtb_vs_close_deviation_pct: float | None = Field(alias="xtbVsCloseDeviationPct", default=None)
    last_xtb_quote_at: str | None = Field(alias="lastXtbQuoteAt", default=None)


class InstrumentDataStatusResponseDto(BaseModel):
    data: InstrumentDataStatusDto


class InstrumentDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    symbol: str
    yahoo_symbol: str = Field(alias="yahooSymbol")
    name: str
    exchange: str
    country: str
    currency: str
    sector: str | None
    isin: str | None = None
    is_active: bool = Field(alias="isActive")


class PriceSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    last_close: float = Field(alias="lastClose")
    previous_close: float | None = Field(alias="previousClose")
    change_abs: float | None = Field(alias="changeAbs")
    change_pct: float | None = Field(alias="changePct")
    period_low: float = Field(alias="periodLow")
    period_high: float = Field(alias="periodHigh")
    bar_count: int = Field(alias="barCount")
    first_date: str = Field(alias="firstDate")
    last_date: str = Field(alias="lastDate")


class InstrumentDetailMetaDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    last_sync: SyncDetailDto | None = Field(alias="lastSync", default=None)
    price_summary: PriceSummaryDto | None = Field(alias="priceSummary", default=None)


class InstrumentDetailResponseDto(BaseModel):
    data: InstrumentDto
    meta: InstrumentDetailMetaDto


class OhlcvBarDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float | None = Field(alias="adjClose")
    source: str


class OhlcvMetaDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    timeframe: str
    count: int


class OhlcvResponseDto(BaseModel):
    data: list[OhlcvBarDto]
    meta: OhlcvMetaDto


class IndicatorPointDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    timestamp: str
    sma20: float | None
    sma50: float | None
    ema20: float | None
    rsi14: float | None


class IndicatorSignalsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    rsi_zone: str = Field(alias="rsiZone")
    sma_cross: str | None = Field(alias="smaCross")


class IndicatorsMetaDto(BaseModel):
    signals: IndicatorSignalsDto


class IndicatorsResponseDto(BaseModel):
    data: list[IndicatorPointDto]
    meta: IndicatorsMetaDto


class InstrumentListMetaDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    bar_count: int = Field(alias="barCount")
    last_sync: SyncMetaDto | None = Field(alias="lastSync", default=None)
    last_close: float | None = Field(alias="lastClose", default=None)
    change_pct: float | None = Field(alias="changePct", default=None)
    last_bar_date: str | None = Field(alias="lastBarDate", default=None)
    freshness_status: str = Field(alias="freshnessStatus", default="empty")
    expected_last_bar_date: str | None = Field(alias="expectedLastBarDate", default=None)


class InstrumentWithMetaDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    symbol: str
    yahoo_symbol: str = Field(alias="yahooSymbol")
    name: str
    exchange: str
    country: str
    currency: str
    sector: str | None
    isin: str | None = None
    is_active: bool = Field(alias="isActive")
    meta: InstrumentListMetaDto


class InstrumentQuotesRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    ids: list[str] = Field(min_length=1, max_length=200)


class InstrumentProfileResponseDto(BaseModel):
    data: dict[str, Any] | None = None


class InstrumentListResponseDto(BaseModel):
    data: list[InstrumentWithMetaDto]


class ExternalInstrumentSearchHitDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    symbol: str
    yahoo_symbol: str = Field(alias="yahooSymbol")
    name: str
    exchange: str
    currency: str
    isin: str | None = None


class InstrumentSearchResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    catalog: list[InstrumentWithMetaDto]
    external: list[ExternalInstrumentSearchHitDto]


class ImportInstrumentRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    yahoo_symbol: str = Field(alias="yahooSymbol", min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=256)
    exchange: str = Field(min_length=1, max_length=32)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    sync: bool = True
    years_back: int = Field(alias="yearsBack", default=5, ge=1, le=30)
    isin: str | None = Field(default=None, max_length=24)


class ImportInstrumentMetaDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    created: bool
    sync: SyncResultDto | None = None


class ImportInstrumentResponseDto(BaseModel):
    data: InstrumentWithMetaDto
    meta: ImportInstrumentMetaDto


class InstrumentOhlcvLayerDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    timeframe: str
    source: str
    bar_count: int = Field(alias="barCount")
    first_date: str | None = Field(alias="firstDate", default=None)
    last_date: str | None = Field(alias="lastDate", default=None)


class InstrumentSyncLogEntryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    provider: str
    status: str
    bars_added: int = Field(alias="barsAdded")
    synced_at: str = Field(alias="syncedAt")
    error: str | None = None


class InstrumentAppDataCountsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    positions: int
    transactions: int
    backtest_runs: int = Field(alias="backtestRuns")
    list_memberships: int = Field(alias="listMemberships")
    price_alerts: int = Field(alias="priceAlerts")
    pending_orders: int = Field(alias="pendingOrders")
    ledger_entries: int = Field(alias="ledgerEntries")


class InstrumentRecordDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    symbol: str
    yahoo_symbol: str = Field(alias="yahooSymbol")
    name: str
    exchange: str
    country: str
    currency: str
    sector: str | None
    isin: str | None = None
    is_active: bool = Field(alias="isActive")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    profile_fetched_at: str | None = Field(alias="profileFetchedAt", default=None)
    last_xtb_validation: dict[str, Any] | None = Field(alias="lastXtbValidation", default=None)


class InstrumentDbInventoryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument: InstrumentRecordDto
    ohlcv_layers: list[InstrumentOhlcvLayerDto] = Field(alias="ohlcvLayers")
    recent_sync_logs: list[InstrumentSyncLogEntryDto] = Field(alias="recentSyncLogs")
    app_data: InstrumentAppDataCountsDto = Field(alias="appData")
    derived_data_notes: list[str] = Field(alias="derivedDataNotes")


class InstrumentDbInventoryResponseDto(BaseModel):
    data: InstrumentDbInventoryDto


class InstrumentXtbValidationDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    available: bool
    message: str
    db_last_close: float | None = Field(alias="dbLastClose", default=None)
    db_last_date: str | None = Field(alias="dbLastDate", default=None)
    xtb_last: float | None = Field(alias="xtbLast", default=None)
    xtb_bid: float | None = Field(alias="xtbBid", default=None)
    xtb_ask: float | None = Field(alias="xtbAsk", default=None)
    xtb_timestamp: str | None = Field(alias="xtbTimestamp", default=None)
    deviation_pct: float | None = Field(alias="deviationPct", default=None)
    recommendation: str
    validated_at: str = Field(alias="validatedAt")
    wrote_to_db: bool = Field(alias="wroteToDb", default=False)


class InstrumentXtbValidationResponseDto(BaseModel):
    data: InstrumentXtbValidationDto
