"""Schemas: InstrumentDailyOpinion (dictamen diario Estudio)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

StanceLiteral = Literal[
    "buy",
    "hold_watch",
    "overbought",
    "reduce",
    "sell_exit",
    "no_trade",
    "review_strategy",
]
GateLiteral = Literal["PASS", "VETO", "WARNING"]
SourceLiteral = Literal["on_demand", "eod_batch", "manual"]


class InstrumentDailyOpinionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    account_id: str | None = Field(default=None, alias="accountId")
    as_of_bar_date: str = Field(alias="asOfBarDate")
    stance: StanceLiteral
    dictamen_stars: int = Field(alias="dictamenStars", ge=1, le=5)
    strategy_stars: int | None = Field(default=None, alias="strategyStars")
    io_score: float | None = Field(default=None, alias="ioScore")
    fa_score: float | None = Field(default=None, alias="faScore")
    ta_score: float | None = Field(default=None, alias="taScore")
    distress: bool = False
    reasons: list[str] = Field(default_factory=list)
    gate_status: GateLiteral | None = Field(default=None, alias="gateStatus")
    top_id: str | None = Field(default=None, alias="topId")
    top_version: int | None = Field(default=None, alias="topVersion")
    source: SourceLiteral
    engine_version: str = Field(alias="engineVersion")
    idempotency_key: str = Field(alias="idempotencyKey")
    computed_at: str = Field(alias="computedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class InstrumentDailyOpinionHintDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_id: str = Field(alias="instrumentId")
    io_score: float | None = Field(default=None, alias="ioScore")
    fa_score: float | None = Field(default=None, alias="faScore")
    ta_score: float | None = Field(default=None, alias="taScore")
    distress: bool = False
    position_open: bool = Field(default=False, alias="positionOpen")
    allow_trading: bool = Field(default=True, alias="allowTrading")
    has_eod_bar: bool | None = Field(default=None, alias="hasEodBar")


class QueryInstrumentDailyOpinionsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument_ids: list[str] = Field(alias="instrumentIds", min_length=1, max_length=200)
    as_of_bar_date: str | None = Field(default=None, alias="asOfBarDate")
    account_id: str | None = Field(default=None, alias="accountId")
    force_refresh: bool = Field(default=False, alias="forceRefresh")
    hints: list[InstrumentDailyOpinionHintDto] = Field(default_factory=list)

    @field_validator("instrument_ids")
    @classmethod
    def _non_empty_ids(cls, value: list[str]) -> list[str]:
        cleaned = [i.strip() for i in value if isinstance(i, str) and i.strip()]
        if not cleaned:
            raise ValueError("instrumentIds must not be empty")
        return cleaned


class InstrumentDailyOpinionsListResponseDto(BaseModel):
    data: list[InstrumentDailyOpinionDto]
