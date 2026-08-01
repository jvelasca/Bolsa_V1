from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.schemas.indicators_compute import OhlcvBarInputDto


class EvaluateSignalsRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    definition: dict[str, object]
    instrument_id: str | None = Field(default=None, alias="instrumentId")
    bars: list[OhlcvBarInputDto]
    mode: str = "raw"
    data_version: str | None = Field(default=None, alias="dataVersion")
    indicator_snapshot_hash: str | None = Field(default=None, alias="indicatorSnapshotHash")


class SignalEventV1Dto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    timestamp: str
    kind: str
    strategy_definition_id: str = Field(alias="strategyDefinitionId")
    strategy_version: int = Field(alias="strategyVersion")
    bar_index: int = Field(alias="barIndex")
    price: float
    data_version: str | None = Field(default=None, alias="dataVersion")
    indicator_snapshot_hash: str | None = Field(default=None, alias="indicatorSnapshotHash")
    preset_key: str | None = Field(default=None, alias="presetKey")


class EvaluateSignalsResponseDto(BaseModel):
    data: list[SignalEventV1Dto]
