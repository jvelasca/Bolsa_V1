"""DTOs HTTP de alertas por señal (no precio)."""

from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.schemas.signals_evaluate import SignalEventV1Dto


class SignalAlertSubscriptionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    preset_key: str | None = Field(default=None, alias="presetKey")
    timeframe: str
    signal_kinds: list[str] = Field(alias="signalKinds")
    channels: list[str] = Field(default_factory=lambda: ["toast"])
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    email_to: str | None = Field(default=None, alias="emailTo")
    is_active: bool = Field(alias="isActive")
    last_triggered_at: str | None = Field(default=None, alias="lastTriggeredAt")
    last_bar_timestamp: str | None = Field(default=None, alias="lastBarTimestamp")
    last_signal_kind: str | None = Field(default=None, alias="lastSignalKind")
    last_signal_price: float | None = Field(default=None, alias="lastSignalPrice")
    note: str | None = None
    created_at: str = Field(alias="createdAt")


class SignalAlertSubscriptionsResponseDto(BaseModel):
    data: list[SignalAlertSubscriptionDto]


class SignalAlertSubscriptionResponseDto(BaseModel):
    data: SignalAlertSubscriptionDto


class CreateSignalAlertSubscriptionRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    preset_key: str | None = Field(default=None, alias="presetKey")
    timeframe: str = "1d"
    signal_kinds: list[str] | None = Field(default=None, alias="signalKinds")
    channels: list[str] | None = None
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    email_to: str | None = Field(default=None, alias="emailTo")
    note: str | None = None


class AlertChannelDispatchDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    subscription_id: str = Field(alias="subscriptionId")
    channel: str
    ok: bool
    error: str | None = None


class TriggeredSignalAlertDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    subscription: SignalAlertSubscriptionDto
    signal: SignalEventV1Dto
    dispatches: list[AlertChannelDispatchDto] = Field(default_factory=list)


class EvaluateSignalAlertsResponseDto(BaseModel):
    data: list[TriggeredSignalAlertDto]
    dispatches: list[AlertChannelDispatchDto] = Field(default_factory=list)
