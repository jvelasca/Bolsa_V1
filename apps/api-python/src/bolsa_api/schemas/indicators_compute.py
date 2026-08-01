from pydantic import BaseModel, ConfigDict, Field


class IndicatorSpecDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    definition_id: str = Field(alias="definitionId")
    parameters: dict[str, int | float | bool | str] = Field(default_factory=dict)


class OhlcvBarInputDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None = Field(default=None, alias="adjClose")
    source: str = "yahoo"


class ComputeIndicatorsRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    bars: list[OhlcvBarInputDto]
    specs: list[IndicatorSpecDto]


class IndicatorLinePointDto(BaseModel):
    timestamp: str
    value: float


class IndicatorLineSeriesDto(BaseModel):
    key: str
    points: list[IndicatorLinePointDto]


class IndicatorSpecSeriesDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    definition_id: str = Field(alias="definitionId")
    parameters: dict[str, int | float | bool | str]
    spec_key: str = Field(alias="specKey")
    lines: list[IndicatorLineSeriesDto]


class ComputeIndicatorsResponseDto(BaseModel):
    data: list[IndicatorSpecSeriesDto]
