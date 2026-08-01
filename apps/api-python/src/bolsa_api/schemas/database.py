from pydantic import BaseModel, ConfigDict, Field


class DatabaseTableCountDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    table: str
    label: str
    count: int


class InstrumentOhlcvBreakdownDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    timeframe: str
    bar_count: int = Field(alias="barCount")


class DatabaseSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    connected: bool
    message: str
    tables: list[DatabaseTableCountDto]
    instrument_ohlcv: list[InstrumentOhlcvBreakdownDto] = Field(alias="instrumentOhlcv")


class DatabaseSummaryResponseDto(BaseModel):
    data: DatabaseSummaryDto
