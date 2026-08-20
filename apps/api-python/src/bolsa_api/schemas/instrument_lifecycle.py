"""DTOs de ciclo de vida de instrumentos (preview / remove / orphans)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ListMembershipRefDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    list_id: str = Field(alias="listId")
    list_name: str = Field(alias="listName")
    source: str


class NamedRefDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    name: str
    detail: str | None = None


class InstrumentRemovalPreviewDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    name: str
    list_memberships: list[ListMembershipRefDto] = Field(alias="listMemberships")
    remaining_list_count: int = Field(alias="remainingListCount")
    trackers_by_instrument: list[NamedRefDto] = Field(alias="trackersByInstrument")
    trackers_by_list: list[NamedRefDto] = Field(alias="trackersByList")
    price_alerts_active: int = Field(alias="priceAlertsActive")
    price_alerts_total: int = Field(alias="priceAlertsTotal")
    signal_alerts_active: int = Field(alias="signalAlertsActive")
    signal_alerts_total: int = Field(alias="signalAlertsTotal")
    positions: int
    pending_orders: int = Field(alias="pendingOrders")
    transactions: int
    backtest_runs: int = Field(alias="backtestRuns")
    ledger_entries: int = Field(alias="ledgerEntries")
    ohlcv_bar_count: int = Field(alias="ohlcvBarCount")
    would_be_orphan: bool = Field(alias="wouldBeOrphan")
    can_purge: bool = Field(alias="canPurge")
    purge_blocked_reasons: list[str] = Field(alias="purgeBlockedReasons")
    purge_warnings: list[str] = Field(alias="purgeWarnings")


class InstrumentRemovalPreviewResponseDto(BaseModel):
    data: InstrumentRemovalPreviewDto


class RemoveInstrumentFromListRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    purge_if_orphan: bool = Field(alias="purgeIfOrphan", default=False)


class RemoveInstrumentFromListResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    list_id: str = Field(alias="listId")
    instrument_id: str = Field(alias="instrumentId")
    removed_from_list: bool = Field(alias="removedFromList")
    became_orphan: bool = Field(alias="becameOrphan")
    purged: bool
    purge_skipped_reasons: list[str] = Field(alias="purgeSkippedReasons")
    preview: InstrumentRemovalPreviewDto | None = None


class RemoveInstrumentFromListResponseDto(BaseModel):
    data: RemoveInstrumentFromListResultDto


class OrphanInstrumentDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    symbol: str
    name: str
    ohlcv_bar_count: int = Field(alias="ohlcvBarCount")


class OrphanInstrumentsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    orphans: list[OrphanInstrumentDto]
    total_ohlcv_bars: int = Field(alias="totalOhlcvBars")


class OrphanInstrumentsResponseDto(BaseModel):
    data: OrphanInstrumentsDto


class PurgeOrphansRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    limit: int = Field(default=50, ge=1, le=200)


class PurgeOrphanSkippedDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    reasons: list[str]


class PurgeOrphansResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    purged_ids: list[str] = Field(alias="purgedIds")
    skipped: list[PurgeOrphanSkippedDto]
    scanned: int


class PurgeOrphansResponseDto(BaseModel):
    data: PurgeOrphansResultDto
