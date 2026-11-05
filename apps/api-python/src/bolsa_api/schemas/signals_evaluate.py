"""DTOs HTTP de evaluación de señales / presets."""

from pydantic import BaseModel, ConfigDict, Field

from bolsa_analytics.signals.strategy import SignalEventV1
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
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    # S4 — contrato de tiempo explícito. Opcionales para clientes históricos; el
    # serializador siempre los publica resueltos (``signalBar = t``,
    # ``executionBar = t + 1``).
    signal_bar: int | None = Field(default=None, alias="signalBar")
    execution_bar: int | None = Field(default=None, alias="executionBar")


class EvaluateSignalsResponseDto(BaseModel):
    data: list[SignalEventV1Dto]


def to_signal_event_v1_dto(event: SignalEventV1) -> SignalEventV1Dto:
    return SignalEventV1Dto(
        id=event.id,
        instrument_id=event.instrument_id,
        timestamp=event.timestamp,
        kind=event.kind,
        strategy_definition_id=event.strategy_definition_id,
        strategy_version=event.strategy_version,
        bar_index=event.bar_index,
        price=event.price,
        data_version=event.data_version,
        indicator_snapshot_hash=event.indicator_snapshot_hash,
        preset_key=event.preset_key,
        signal_bar=event.resolved_signal_bar,
        execution_bar=event.resolved_execution_bar,
    )
