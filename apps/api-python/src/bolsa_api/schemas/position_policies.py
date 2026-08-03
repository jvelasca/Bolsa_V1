"""DTOs HTTP de políticas de posición."""

from pydantic import BaseModel, ConfigDict, Field


class PositionPolicySummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    account_id: str = Field(alias="accountId")
    instrument_id: str = Field(alias="instrumentId")
    mode: str
    exit_strategy_definition_id: str | None = Field(default=None, alias="exitStrategyDefinitionId")
    execution_policy_id: str | None = Field(default=None, alias="executionPolicyId")
    updated_at: str = Field(alias="updatedAt")
    created_at: str = Field(alias="createdAt")


class PositionPolicyDetailDto(PositionPolicySummaryDto):
    definition: dict


class PositionPoliciesListResponseDto(BaseModel):
    data: list[PositionPolicySummaryDto]


class PositionPolicyResponseDto(BaseModel):
    data: PositionPolicyDetailDto


class CreatePositionPolicyRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_id: str = Field(alias="accountId")
    instrument_id: str = Field(alias="instrumentId")
    mode: str = "manual"
    exit_strategy_definition_id: str | None = Field(default=None, alias="exitStrategyDefinitionId")
    execution_policy_id: str | None = Field(default=None, alias="executionPolicyId")


class UpdatePositionPolicyRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: str | None = None
    exit_strategy_definition_id: str | None = Field(default=None, alias="exitStrategyDefinitionId")
    execution_policy_id: str | None = Field(default=None, alias="executionPolicyId")


class PositionExitEvalResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    account_id: str = Field(alias="accountId")
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    quantity: float
    policy_id: str | None = Field(default=None, alias="policyId")
    mode: str | None = None
    status: str
    signal: dict | None = None
    action: dict | None = None
    reason: str | None = None


class EvaluatePositionExitsResponseDto(BaseModel):
    data: dict
