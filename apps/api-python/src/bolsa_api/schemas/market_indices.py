"""DTOs HTTP de índices y constitutivos."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IndexHitDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    code: str | None = None

    display_name: str = Field(alias="displayName")

    yahoo_symbol: str = Field(alias="yahooSymbol")

    region: str | None = None

    currency: str | None = None

    quote_type: str = Field(alias="quoteType")

    source: str

    constituent_ready: bool = Field(alias="constituentReady")

    score: float = 0





class MarketIndicesSearchResponseDto(BaseModel):

    data: list[IndexHitDto]





class CatalogIndexEntryDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    code: str

    display_name: str = Field(alias="displayName")

    yahoo_symbol: str = Field(alias="yahooSymbol")

    region: str

    currency: str

    constituent_ready: bool = Field(alias="constituentReady")

    expected_count_min: int = Field(alias="expectedCountMin")

    expected_count_max: int = Field(alias="expectedCountMax")

    list_id: str = Field(alias="listId")





class MarketIndexCatalogResponseDto(BaseModel):

    data: list[CatalogIndexEntryDto]





class IndexConstituentMemberDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    symbol: str

    yahoo_symbol: str = Field(alias="yahooSymbol")

    name: str | None = None





class IndexConstituentDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    index_code: str = Field(alias="indexCode")

    yahoo_index_symbol: str = Field(alias="yahooIndexSymbol")

    provider: str

    as_of: str = Field(alias="asOf")

    content_hash: str = Field(alias="contentHash")

    members: list[IndexConstituentMemberDto]





class IndexConstituentsResponseDto(BaseModel):

    data: IndexConstituentDto





class SubscribeMarketIndexRequestDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    index_key: str = Field(alias="indexKey", min_length=1, max_length=40)

    sync_bars: bool = Field(default=False, alias="syncBars")

    years_back: int = Field(default=2, alias="yearsBack", ge=1, le=25)





class SubscribeProgressDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    total: int

    already_present: int = Field(alias="alreadyPresent")

    imported: int

    failed: list[str] = Field(default_factory=list)

    joined: list[str] = Field(default_factory=list)

    left: list[str] = Field(default_factory=list)





class SubscribeMarketIndexResultDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    list_id: str = Field(alias="listId")

    index_code: str = Field(alias="indexCode")

    display_name: str = Field(alias="displayName")

    yahoo_index_symbol: str = Field(alias="yahooIndexSymbol")

    content_hash: str = Field(alias="contentHash")

    instrument_ids: list[str] = Field(alias="instrumentIds")

    progress: SubscribeProgressDto

    status: str





class SubscribeMarketIndexResponseDto(BaseModel):

    data: SubscribeMarketIndexResultDto





class IndexSubscribeJobDto(BaseModel):

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]



    id: str

    status: str

    payload: dict[str, Any]

    result: dict[str, Any] | None = None

    error: str | None = None

    created_at: str = Field(alias="createdAt")

    updated_at: str = Field(alias="updatedAt")

    completed_at: str | None = Field(alias="completedAt", default=None)





class IndexSubscribeJobResponseDto(BaseModel):

    data: IndexSubscribeJobDto


