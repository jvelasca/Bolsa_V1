"""Pydantic DTOs — mandato operativo (ADR-020 M1b)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MandateTenureDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    account_id: str = Field(alias="accountId")
    instrument_id: str = Field(alias="instrumentId")
    timeframe: str | None = None
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    strategy_label_snapshot: str | None = Field(default=None, alias="strategyLabelSnapshot")
    effective_from: str = Field(alias="effectiveFrom")
    effective_to: str | None = Field(default=None, alias="effectiveTo")
    actor: str
    reason: str
    source_top_id: str | None = Field(default=None, alias="sourceTopId")
    source_top_version: int | None = Field(default=None, alias="sourceTopVersion")
    evidence_level: str | None = Field(default=None, alias="evidenceLevel")


class MandateTradeLinkDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    transaction_id: str = Field(alias="transactionId")
    mandate_tenure_id: str = Field(alias="mandateTenureId")
    instrument_id: str = Field(alias="instrumentId")
    account_id: str = Field(alias="accountId")
    linked_at: str = Field(alias="linkedAt")
    engine: str = "mandate-trade-links-v1"


class MandateBundleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    tenures: list[MandateTenureDto]
    links: list[MandateTradeLinkDto]


class MandateBundleResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    data: MandateBundleDto


class SyncMandateBundleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenures: list[MandateTenureDto] = Field(default_factory=list)
    links: list[MandateTradeLinkDto] = Field(default_factory=list)
