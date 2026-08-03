"""DTOs HTTP de políticas de ejecución."""

from pydantic import BaseModel, ConfigDict, Field


class ExecutionPolicySummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    name: str
    mode: str
    account_id: str | None = Field(default=None, alias="accountId")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    signal_kinds: list[str] = Field(alias="signalKinds")
    require_validated_backtest: bool = Field(alias="requireValidatedBacktest")
    enabled: bool
    updated_at: str = Field(alias="updatedAt")
    created_at: str = Field(alias="createdAt")


class ExecutionPolicyDetailDto(ExecutionPolicySummaryDto):
    definition: dict


class ExecutionPoliciesListResponseDto(BaseModel):
    data: list[ExecutionPolicySummaryDto]


class ExecutionPolicyResponseDto(BaseModel):
    data: ExecutionPolicyDetailDto


class CreateExecutionPolicyRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    mode: str
    account_id: str | None = Field(default=None, alias="accountId")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    signal_kinds: list[str] | None = Field(default=None, alias="signalKinds")
    channels: list[str] | None = None
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    email_to: str | None = Field(default=None, alias="emailTo")
    require_validated_backtest: bool = Field(default=False, alias="requireValidatedBacktest")
    origin: str = "manual"
    enabled: bool = True


class UpdateExecutionPolicyRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    mode: str | None = None
    account_id: str | None = Field(default=None, alias="accountId")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    signal_kinds: list[str] | None = Field(default=None, alias="signalKinds")
    channels: list[str] | None = None
    webhook_url: str | None = Field(default=None, alias="webhookUrl")
    email_to: str | None = Field(default=None, alias="emailTo")
    require_validated_backtest: bool | None = Field(default=None, alias="requireValidatedBacktest")
    enabled: bool | None = None


class ExecutionActionResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    signal_kind: str = Field(alias="signalKind")
    status: str
    reason: str | None = None
    transaction_id: str | None = Field(default=None, alias="transactionId")
    dispatches: list[dict] | None = None


class RouteSignalsRequestDto(BaseModel):
    hits: list[dict]


class RouteSignalsResponseDto(BaseModel):
    data: dict


class ExecuteScanJobRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    policy_id: str = Field(alias="policyId")
