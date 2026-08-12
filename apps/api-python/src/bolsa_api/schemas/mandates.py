"""Pydantic DTOs — mandato operativo (ADR-020 M1b).

Tenures y links de trades por cuenta; hydrate/push multi-dispositivo.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MandateTenureDto(BaseModel):
    """Tramo de mandato (estrategia×instrumento×cuenta) abierto o cerrado."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    """Vínculo fill/transacción → tenure (flujo enlazado, no MTM)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    transaction_id: str = Field(alias="transactionId")
    mandate_tenure_id: str = Field(alias="mandateTenureId")
    instrument_id: str = Field(alias="instrumentId")
    account_id: str = Field(alias="accountId")
    linked_at: str = Field(alias="linkedAt")
    engine: str = "mandate-trade-links-v1"


class MandateBundleDto(BaseModel):
    """Bundle tenures + links de una cuenta."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    tenures: list[MandateTenureDto]
    links: list[MandateTradeLinkDto]


class MandateBundleResponseDto(BaseModel):
    """Respuesta GET envuelta en ``data``."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    data: MandateBundleDto


class SyncMandateBundleDto(BaseModel):
    """Payload PUT de sincronización cliente → BD."""

    model_config = ConfigDict(populate_by_name=True)

    tenures: list[MandateTenureDto] = Field(default_factory=list)
    links: list[MandateTradeLinkDto] = Field(default_factory=list)
