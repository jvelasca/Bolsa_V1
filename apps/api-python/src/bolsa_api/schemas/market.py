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
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    label: str
    enabled: bool
    healthy: bool
    message: str
    # 059 — configuración efectiva y procedencia del estado (claves aditivas).
    priority: int = 0
    min_interval_seconds: int = Field(alias="minIntervalSeconds", default=0)
    base_url: str | None = Field(alias="baseUrl", default=None)
    capabilities: list[str] = Field(default_factory=list)
    description: str = ""
    verified: bool = False
    base_url_source: str | None = Field(alias="baseUrlSource", default=None)
    last_check_at: str | None = Field(alias="lastCheckAt", default=None)
    last_check_ok: bool | None = Field(alias="lastCheckOk", default=None)
    last_check_message: str | None = Field(alias="lastCheckMessage", default=None)


class MarketProvidersResponseDto(BaseModel):
    data: list[MarketProviderStatusDto]


class UpdateMarketProviderDto(BaseModel):
    """PATCH de un proveedor: solo se aplican los campos DECLARADOS.

    ``baseUrl`` se distingue de «no declarado» con ``model_fields_set``: enviar
    ``baseUrl: null`` borra la URL configurada, omitirla la deja como está.
    """

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    min_interval_seconds: int | None = Field(
        alias="minIntervalSeconds", default=None, ge=0, le=120
    )
    base_url: str | None = Field(alias="baseUrl", default=None, max_length=500)


class MarketProviderResponseDto(BaseModel):
    data: MarketProviderStatusDto


class ProviderTestResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    provider_id: str = Field(alias="providerId")
    ok: bool
    message: str
    checked_at: str = Field(alias="checkedAt")


class ProviderTestResponseDto(BaseModel):
    data: ProviderTestResultDto


class ProviderHealthEntryDto(BaseModel):
    """Estado de un proveedor dentro del veredicto agregado de la barra."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    label: str
    enabled: bool
    healthy: bool
    verified: bool
    message: str
    last_check_at: str | None = Field(alias="lastCheckAt", default=None)
    last_check_ok: bool | None = Field(alias="lastCheckOk", default=None)


class ProviderHealthSummaryDto(BaseModel):
    """Veredicto para el icono de servidores.

    ``ok`` | ``degraded`` | ``stale`` | ``unverified`` | ``none``. ``stale`` (060) es una
    medición correcta que ya no se refresca al ritmo declarado; ``unverified`` es no haber
    medido nunca. La política viaja con el veredicto para que la UI no la duplique.
    """

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: str
    ok: bool
    measured_at: str | None = Field(alias="measuredAt", default=None)
    probing: bool = False
    auto_check_enabled: bool = Field(alias="autoCheckEnabled", default=True)
    check_interval_seconds: int = Field(alias="checkIntervalSeconds", default=60)
    next_check_at: str | None = Field(alias="nextCheckAt", default=None)
    providers: list[ProviderHealthEntryDto] = Field(default_factory=list)


class ProviderHealthSummaryResponseDto(BaseModel):
    data: ProviderHealthSummaryDto


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
