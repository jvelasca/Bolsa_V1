"""API: DÍA-D · VERIFICACIÓN ENLAZADA A UN CICLO AUTO (P2/v111 — resuelta por servidor).

Registra, de forma durable, que la verificación D→hoy del sandbox LAB se lanzó DESDE un ciclo AUTO
concreto. **La identidad del ciclo (instrumento, símbolo y estrategia EJECUTADA) la DERIVA el
servidor** de los hechos durables AUTO (nunca del navegador): ``cycleId`` inexistente ⇒ ``404``
``cycle_not_found``; un campo declarado que contradice el hecho durable ⇒ ``409``
``cycle_identity_conflict``. La fila sella un ``facts_hash`` del snapshot de hechos usado.

A DIFERENCIA del router read-only de feedback por artefacto
(:mod:`bolsa_api.api.v1.routes.auto_dia_d_feedback`, que solo LEE JSON precalculados), esta
superficie SÍ escribe: persiste el enlace ciclo ↔ verificación. Fail-closed por cuenta: sin
cuenta del principal, la escritura se rechaza (400) y la lectura devuelve vacío con
``no_account_scope``. Un ciclo sin identidad de estrategia se persiste con el hueco declarado
(«Sin dato todavía»), nunca fabricado.
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
from bolsa_application.auto_chain_durable_reader import resolve_dia_d_cycle_facts
from bolsa_application.dia_d_cycle_verification import (
    DiaDCycleFacts,
    DiaDCycleIdentityConflictError,
    DiaDCycleNotFoundError,
    ListDiaDCycleVerifications,
    ResolveDiaDCycleVerification,
)
from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification
from bolsa_infrastructure.database.repositories.dia_d_cycle_verification_repository import (
    DiaDCycleVerificationOwnershipConflictError,
)

router = APIRouter()


class _SessionCycleFactsResolver:
    """Resuelve la identidad durable del ciclo desde la sesión SQLAlchemy de la petición."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, *, account_id: str, cycle_id: str) -> DiaDCycleFacts | None:
        return await resolve_dia_d_cycle_facts(
            self._session, account_id, cycle_id=cycle_id
        )


class DiaDCycleVerificationPersistRequestDto(BaseModel):
    """Payload de la verificación D→hoy lanzada desde un ciclo. Huecos ⇒ campo ausente.

    Sólo ``cycleId``/``diaD``/``endDate``/``mode`` son indispensables. ``instrumentId``,
    ``symbol`` y las claves de estrategia son OPCIONALES y actúan como **contraste**: si se
    declaran y contradicen el hecho durable del ciclo, el servidor responde ``409`` (nunca se
    persiste lo declarado por el navegador).
    """

    model_config = ConfigDict(populate_by_name=True)

    cycle_id: str = Field(alias="cycleId")
    dia_d: str = Field(alias="diaD")
    end_date: str = Field(alias="endDate")
    mode: str
    instrument_id: str | None = Field(default=None, alias="instrumentId")
    symbol: str | None = None
    strategy_preset_key: str | None = Field(default=None, alias="strategyPresetKey")
    strategy_version: str | None = Field(default=None, alias="strategyVersion")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    band: str | None = None
    result: dict[str, Any] | None = None
    research_evidence_id: str | None = Field(default=None, alias="researchEvidenceId")
    verified_by: str | None = Field(default=None, alias="verifiedBy")


class DiaDCycleVerificationDto(BaseModel):
    """Verificación durable enlazada a un ciclo (una fila por cuenta + ciclo + ventana + modo)."""

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
    #: Identidad EXACTA derivada del ciclo; `None` = hueco (nunca cadena vacía).
    strategy_preset_key: str | None = Field(default=None, alias="strategyPresetKey")
    strategy_version: str | None = Field(default=None, alias="strategyVersion")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    band: str | None = None
    result: dict[str, Any] | None = None
    research_evidence_id: str | None = Field(default=None, alias="researchEvidenceId")
    #: v111 — hash del snapshot de hechos durables que respaldan la verificación (o hueco).
    facts_hash: str | None = Field(default=None, alias="factsHash")
    verified_by: str | None = Field(default=None, alias="verifiedBy")


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
        facts_hash=row.facts_hash,
        verified_by=row.verified_by,
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
    """Registra (idempotente) la verificación DÍA-D enlazada al ciclo del principal.

    El ciclo se RESUELVE en el servidor: inexistente ⇒ 404; identidad declarada en conflicto con
    el hecho durable ⇒ 409. Nunca se persiste la identidad declarada por el navegador.
    """
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        raise HTTPException(
            status_code=400,
            detail="La verificación DÍA-D requiere una cuenta operativa del principal",
        )
    repo = get_dia_d_cycle_verification_repository(session)
    use_case = ResolveDiaDCycleVerification(repo, _SessionCycleFactsResolver(session))
    try:
        row = await use_case.execute(body.model_dump(by_alias=True), account_id=scope)
    except DiaDCycleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="cycle_not_found") from exc
    except DiaDCycleIdentityConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "cycle_identity_conflict",
                "fields": {name: {"declared": pair[0], "durable": pair[1]} for name, pair in exc.conflicts.items()},
            },
        ) from exc
    except DiaDCycleVerificationOwnershipConflictError as exc:
        raise HTTPException(status_code=409, detail="cycle_identity_owned_by_another_account") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
