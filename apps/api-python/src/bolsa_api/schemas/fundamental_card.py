"""Schemas F1 — FundamentalCard (FIE contract freeze)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FundamentalPillarsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    value: float
    quality: float
    growth: float
    risk: float


class FundamentalCardMetadataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    provider: str
    source_version: str | None = Field(default=None, alias="sourceVersion")
    score_version: str = Field(alias="scoreVersion")
    fetched_at: str | None = Field(default=None, alias="fetchedAt")
    stale_days: int | None = Field(default=None, alias="staleDays")
    is_stale: bool = Field(alias="isStale")
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    coverage: float | None = None
    as_of_date: str | None = Field(default=None, alias="asOfDate")
    point_in_time: Literal["live", "snapshot", "blocked", "reconstructed"] | None = Field(
        default=None,
        alias="pointInTime",
    )


class FundamentalCardDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    schema_version: str = Field(alias="schemaVersion")
    instrument_id: str = Field(alias="instrumentId")
    ticker: str
    score_fund: float | None = Field(default=None, alias="scoreFund")
    score_display_100: int | None = Field(default=None, alias="scoreDisplay100")
    distress: bool = False
    pillars: FundamentalPillarsDto | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    derived: dict[str, Any] = Field(default_factory=dict)
    metadata: FundamentalCardMetadataDto
    assessment_id: str | None = Field(default=None, alias="assessmentId")
    narrative_facts: list[str] = Field(default_factory=list, alias="narrativeFacts")
    warnings: list[str] = Field(default_factory=list)


class FundamentalCardResponseDto(BaseModel):
    data: FundamentalCardDto


class FundamentalChipDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    ticker: str
    score_display_100: int | None = Field(default=None, alias="scoreDisplay100")
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    is_stale: bool = Field(alias="isStale")
    distress: bool = False
    roe: float | None = None
    debt_to_equity: float | None = Field(default=None, alias="debtToEquity")
    altman_z: float | None = Field(default=None, alias="altmanZ")


class QueryInstrumentFundamentalsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_ids: list[str] = Field(alias="instrumentIds", min_length=1, max_length=80)


class FundamentalChipListResponseDto(BaseModel):
    data: list[FundamentalChipDto]
