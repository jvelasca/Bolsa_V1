"""Schemas SEMI Confirm F3 queue multi-dispositivo.

SoT en BD; sessionStorage = cache.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SupervisedF3BundleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    account_id: str = Field(alias="accountId")
    items: list[dict[str, Any]] = Field(default_factory=list)
    active_id: str | None = Field(default=None, alias="activeId")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class SupervisedF3BundleResponseDto(BaseModel):
    data: SupervisedF3BundleDto


class SyncSupervisedF3BundleDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    items: list[dict[str, Any]] = Field(default_factory=list)
    active_id: str | None = Field(default=None, alias="activeId")
