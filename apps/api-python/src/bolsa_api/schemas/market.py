"""DTOs HTTP de mercado (OHLCV / quotes)."""

from pydantic import BaseModel, ConfigDict, Field


class SyncResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    bars_added: int = Field(alias="barsAdded")
    status: str
    error: str | None = None
    bars_inserted: int = Field(alias="barsInserted", default=0)
    bars_updated: int = Field(alias="barsUpdated", default=0)
    bars_skipped: int = Field(alias="barsSkipped", default=0)
    consolidation_notes: list[str] = Field(alias="consolidationNotes", default_factory=list)


class SyncResponseDto(BaseModel):
    data: SyncResultDto


class LiveQuoteSourceDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    price: float
    timestamp: str
    source: str


class XtbQuoteDto(BaseModel):
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: str


class LiveQuoteResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    reference: LiveQuoteSourceDto | None
    xtb: XtbQuoteDto | None
    spread_pct: float | None = Field(alias="spreadPct")
    xtb_available: bool = Field(alias="xtbAvailable")


class LiveQuoteEnvelopeDto(BaseModel):
    data: LiveQuoteResponseDto


class LiveQuoteListResponseDto(BaseModel):
    data: list[LiveQuoteResponseDto]


class MarketProviderStatusDto(BaseModel):
    id: str
    label: str
    enabled: bool
    healthy: bool
    message: str


class MarketProvidersResponseDto(BaseModel):
    data: list[MarketProviderStatusDto]


class FxRateDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    from_currency: str = Field(alias="from")
    to_currency: str = Field(alias="to")
    rate: float
    yahoo_symbol: str = Field(alias="yahooSymbol")
    timestamp: str
    source: str


class FxRateResponseDto(BaseModel):
    data: FxRateDto
