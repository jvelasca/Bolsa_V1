"""Schemas: InstrumentNarrative (evolución corta por valor)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InstrumentNarrativeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    instrument_id: str = Field(alias="instrumentId")
    scope: Literal["estudio", "global", "trading"]
    body: str
    source: Literal["user", "ai", "system"]
    version: int
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class InstrumentNarrativeResponseDto(BaseModel):
    data: InstrumentNarrativeDto | None


class UpsertInstrumentNarrativeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scope: Literal["estudio", "global", "trading"] = "estudio"
    body: str = Field(min_length=0, max_length=4000)
    source: Literal["user", "ai", "system"] = "user"
