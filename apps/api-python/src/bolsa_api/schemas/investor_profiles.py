"""DTOs HTTP de perfiles inversor (CORE-P)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeclaredProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    horizon: str
    objectives: list[str] = Field(default_factory=list)
    risk_tolerance: str = Field(alias="riskTolerance")
    experience: str
    max_acceptable_loss_pct: float | None = Field(default=None, alias="maxAcceptableLossPct")
    notes: str | None = None


class InvestorProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    profile_id: str = Field(alias="profileId")
    name: str
    version: str
    user_id: str | None = Field(default=None, alias="userId")
    declared: DeclaredProfileDto
    suggested_policy_template_id: str = Field(alias="suggestedPolicyTemplateId")
    selected_policy_template_id: str = Field(alias="selectedPolicyTemplateId")
    observed: dict[str, Any] | None = None
    updated_by: str = Field(alias="updatedBy")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class InvestorProfileListResponseDto(BaseModel):
    data: list[InvestorProfileDto]


class InvestorProfileResponseDto(BaseModel):
    data: InvestorProfileDto


class CreateInvestorProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    horizon: str
    objectives: list[str] = Field(default_factory=list)
    risk_tolerance: str = Field(alias="riskTolerance")
    experience: str
    max_acceptable_loss_pct: float | None = Field(default=None, alias="maxAcceptableLossPct")
    notes: str | None = None
    suggested_policy_template_id: str | None = Field(
        default=None,
        alias="suggestedPolicyTemplateId",
    )
    selected_policy_template_id: str | None = Field(
        default=None,
        alias="selectedPolicyTemplateId",
    )


class UpdateInvestorProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    horizon: str | None = None
    objectives: list[str] | None = None
    risk_tolerance: str | None = Field(default=None, alias="riskTolerance")
    experience: str | None = None
    max_acceptable_loss_pct: float | None = Field(default=None, alias="maxAcceptableLossPct")
    notes: str | None = None
    suggested_policy_template_id: str | None = Field(
        default=None,
        alias="suggestedPolicyTemplateId",
    )
    selected_policy_template_id: str | None = Field(
        default=None,
        alias="selectedPolicyTemplateId",
    )


class AssignProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    profile_id: str | None = Field(default=None, alias="profileId")


class AssignProfileResponseDto(BaseModel):
    data: dict[str, str | None]
