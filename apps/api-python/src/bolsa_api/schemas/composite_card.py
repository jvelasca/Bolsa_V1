"""Schemas F3 — Composite Investment Score (chips batch hub I2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompositeChipDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    ticker: str
    score_display_100: int | None = Field(default=None, alias="scoreDisplay100")
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    combined_score: float | None = Field(default=None, alias="combinedScore")
    regime: str = "neutral"
    paper_d_unlocked: bool = Field(default=False, alias="paperDUnlocked")
    technical_display_100: int | None = Field(default=None, alias="technicalDisplay100")


class QueryInstrumentCompositeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_ids: list[str] = Field(alias="instrumentIds", min_length=1, max_length=40)
    horizon: str = "swing"
    regime: str = "neutral"


class CompositeChipListResponseDto(BaseModel):
    data: list[CompositeChipDto]
