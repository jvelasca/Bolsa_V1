"""Schemas CORE-R multi-dispositivo (Q3.4).

Bundle cola + informes + prefs scheduler; SoT en BD, localStorage = cache.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CoreRBundleDto(BaseModel):
    """Estado CORE-R de una cuenta (queue / reports / scheduler)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    account_id: str = Field(alias="accountId")
    queue: list[dict[str, Any]] = Field(default_factory=list)
    reports: dict[str, Any] = Field(default_factory=dict)
    scheduler: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = Field(default=None, alias="updatedAt")


class CoreRBundleResponseDto(BaseModel):
    """Respuesta GET envuelta en ``data``."""

    data: CoreRBundleDto


class SyncCoreRBundleDto(BaseModel):
    """Payload PUT para sincronizar bundle desde el cliente."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    queue: list[dict[str, Any]] = Field(default_factory=list)
    reports: dict[str, Any] = Field(default_factory=dict)
    scheduler: dict[str, Any] = Field(default_factory=dict)
