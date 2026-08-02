"""Schemas CORE-R multi-dispositivo (Q3.4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CoreRBundleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    account_id: str = Field(alias="accountId")
    queue: list[dict[str, Any]] = Field(default_factory=list)
    reports: dict[str, Any] = Field(default_factory=dict)
    scheduler: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = Field(default=None, alias="updatedAt")


class CoreRBundleResponseDto(BaseModel):
    data: CoreRBundleDto


class SyncCoreRBundleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    queue: list[dict[str, Any]] = Field(default_factory=list)
    reports: dict[str, Any] = Field(default_factory=dict)
    scheduler: dict[str, Any] = Field(default_factory=dict)
