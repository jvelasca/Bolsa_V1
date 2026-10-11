"""API: DÍA-D · VERIFICACIÓN ENLAZADA A UN CICLO AUTO (P2).

Registra, de forma durable, que la verificación D→hoy del sandbox LAB se lanzó DESDE
un ciclo AUTO concreto, con la identidad EXACTA de estrategia que declara el ciclo
(`presetKey`/`version`/`definitionId`) y el resultado declarado (banda + métricas).

A DIFERENCIA del router read-only de feedback por artefacto
(:mod:`bolsa_api.api.v1.routes.auto_dia_d_feedback`, que solo LEE JSON precalculados),
esta superficie SÍ escribe: persiste el enlace ciclo ↔ verificación. Fail-closed por
cuenta: sin cuenta del principal, la escritura se rechaza (400) y la lectura devuelve
vacío con `no_account_scope`. Un ciclo sin identidad de estrategia se persiste con el
hueco declarado («Sin dato todavía»), nunca fabricado.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    get_dia_d_cycle_verification_repository,
    resolve_account_scope_or_default,
)
from bolsa_application.dia_d_cycle_verification import (
    ListDiaDCycleVerifications,
    PersistDiaDCycleVerification,
)
from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification

router = APIRouter()


class DiaDCycleVerificationPersistRequestDto(BaseModel):
    """Payload de la verificación D→hoy lanzada desde un ciclo. Huecos ⇒ campo ausente."""

    model_config = ConfigDict(populate_by_name=True)

    cycle_id: str = Field(alias="cycleId")
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    dia_d: str = Field(alias="diaD")
    end_date: str = Field(alias="endDate")
    mode: str
    strategy_preset_key: str | None = Field(default=None, alias="strategyPresetKey")
    strategy_version: str | None = Field(default=None, alias="strategyVersion")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    band: str | None = None
    result: dict[str, Any] | None = None
    research_evidence_id: str | None = Field(default=None, alias="researchEvidenceId")


class DiaDCycleVerificationDto(BaseModel):
    """Verificación durable enlazada a un ciclo (una fila por ciclo + ventana + modo)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    cycle_id: str = Field(alias="cycleId")
    account_id: str | None = Field(default=None, alias="accountId")
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    dia_d: str = Field(alias="diaD")
    end_date: str = Field(alias="endDate")
    mode: str
    created_at: str = Field(alias="createdAt")
    #: Identidad EXACTA declarada por el ciclo; `None` = hueco (nunca cadena vacía).
    strategy_preset_key: str | None = Field(default=None, alias="strategyPresetKey")
    strategy_version: str | None = Field(default=None, alias="strategyVersion")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    band: str | None = None
    result: dict[str, Any] | None = None
    research_evidence_id: str | None = Field(default=None, alias="researchEvidenceId")


class DiaDCycleVerificationResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data: DiaDCycleVerificationDto


class DiaDCycleVerificationListResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data: list[DiaDCycleVerificationDto]
    total: int
    notes: list[str] = Field(default_factory=list)


def _to_dto(row: DiaDCycleVerification) -> DiaDCycleVerificationDto:
    return DiaDCycleVerificationDto(
        id=row.id,
        cycle_id=row.cycle_id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        dia_d=row.dia_d,
        end_date=row.end_date,
        mode=row.mode,
        created_at=row.created_at,
        strategy_preset_key=row.strategy_preset_key,
        strategy_version=row.strategy_version,
        strategy_definition_id=row.strategy_definition_id,
        band=row.band,
        result=row.result,
        research_evidence_id=row.research_evidence_id,
    )


@router.post(
    "/auto/dia-d-verifications",
    response_model=DiaDCycleVerificationResponseDto,
)
async def persist_auto_dia_d_verification(
    request: Request,
    body: DiaDCycleVerificationPersistRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDCycleVerificationResponseDto:
    """Registra (idempotente) la verificación DÍA-D enlazada al ciclo del principal."""
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        raise HTTPException(
            status_code=400,
            detail="La verificación DÍA-D requiere una cuenta operativa del principal",
        )
    repo = get_dia_d_cycle_verification_repository(session)
    row = await PersistDiaDCycleVerification(repo).execute(
        body.model_dump(by_alias=True), account_id=scope
    )
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid DÍA-D verification payload")
    return DiaDCycleVerificationResponseDto(data=_to_dto(row))


@router.get(
    "/auto/dia-d-verifications",
    response_model=DiaDCycleVerificationListResponseDto,
)
async def list_auto_dia_d_verifications(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cycle_id: Annotated[str | None, Query(alias="cycleId")] = None,
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> DiaDCycleVerificationListResponseDto:
    """Verificaciones del principal; con ``cycleId`` acota a un ciclo.

    Fail-closed por cuenta: sin cuenta del principal se devuelve vacío (`no_account_scope`),
    nunca datos globales.
    """
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        return DiaDCycleVerificationListResponseDto(
            data=[], total=0, notes=["no_account_scope"]
        )
    repo = get_dia_d_cycle_verification_repository(session)
    rows = await ListDiaDCycleVerifications(repo).execute(
        account_id=scope, cycle_id=cycle_id
    )
    return DiaDCycleVerificationListResponseDto(
        data=[_to_dto(r) for r in rows], total=len(rows), notes=[]
    )
