"""R2 — disparador HTTP gobernado del embudo AUTO (auditoría LAB 2026-11-16).

``POST /api/auto/orchestrator/run`` hace alcanzable el embudo (ESTUDIO → LAB → TOP3 →
COACH → FINALISTA) sin abrir una puerta trasera: la ruta **valida y delega** en
``OrchestratorTrigger``; no reimplementa ninguna fase.

Reglas del contrato (todas obligatorias, ver ADR-053):

* ``dryRun`` por defecto **``true``**: omitirlo no escribe nada del lifecycle.
* ``toPhase`` máximo ``finalista``. ``active`` se rechaza (400): ACTIVE solo por
  ``decide_promotion`` en el worker.
* El cuerpo es ``extra='forbid'``: no se acepta evidencia del cliente (ni ``gates``, ni
  ``metrics``, ni ``runId``) — un campo desconocido es 422.
* Ámbito: ``instrumentId`` debe estar en el universo ESTUDIO → si no, **409**.
  Cuenta cerrada → **409**; cuenta ajena/inexistente → 404 (indistinguibles).
* Idempotencia durable por ``(instrumentId, accountId, snapshot, cycle, dryRun)``: el
  mismo POST devuelve el mismo ``runId`` con ``replayed=true``.
* Fail-closed: un ciclo que no llega a FINALISTA devuelve ``status=INCOMPLETE`` con
  motivos y gates; nunca un 200 optimista.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from bolsa_application.orchestrator_trigger import (
    TRIGGER_MAX_PHASE,
    OrchestratorTrigger,
    TriggerRequest,
    TriggerRequestError,
    TriggerScopeError,
)
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_repository,
    get_db_session,
    get_session_factory,
    resolve_account_scope_or_default,
)
from bolsa_api.auth.request_principal import get_request_principal

router = APIRouter()
logger = logging.getLogger(__name__)

_ACCOUNT_CLOSED = "closed"


class OrchestratorRunRequestDto(BaseModel):
    """Cuerpo del disparador. ``extra='forbid'``: el cliente no aporta evidencia."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    instrument_id: str = Field(default="", alias="instrumentId")
    account_id: str | None = Field(default=None, alias="accountId")
    #: ``true`` por defecto EN SERVIDOR: omitirlo no escribe nada del lifecycle.
    dry_run: bool = Field(default=True, alias="dryRun")
    #: Techo de fase. Solo ``finalista``; ``active`` se rechaza con 400.
    to_phase: str = Field(default=TRIGGER_MAX_PHASE, alias="toPhase")
    data_snapshot_id: str | None = Field(default=None, alias="dataSnapshotId")


class OrchestratorRunGateDto(BaseModel):
    """Gate evaluado en el recibo (``status`` conserva ``not_evaluated``)."""

    gate: str
    status: str | None = None
    detail: str | None = None


class OrchestratorRunReceiptDto(BaseModel):
    """Recibo verificable de la ejecución (fase + gates + escrituras suprimidas)."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    instrument_id: str = Field(alias="instrumentId")
    account_id: str | None = Field(default=None, alias="accountId")
    dry_run: bool = Field(alias="dryRun")
    status: str
    phase_reached: str | None = Field(default=None, alias="phaseReached")
    cycle: str
    idempotency_key: str = Field(alias="idempotencyKey")
    gates: list[OrchestratorRunGateDto] = Field(default_factory=list)
    candidates: int = 0
    evaluated: int = 0
    #: Siempre ``false``: esta ruta no puede escribir ACTIVE.
    promoted: bool = False
    active_version_id: str | None = Field(default=None, alias="activeVersionId")
    reasons: list[str] = Field(default_factory=list)
    #: Escrituras que el ``dryRun`` suprimió (declaradas, no silenciadas).
    writes: list[str] = Field(default_factory=list)
    #: ``true`` si el recibo se reprodujo desde el ledger (idempotencia).
    replayed: bool = False
    audit_event_id: str | None = Field(default=None, alias="auditEventId")
    computed_at: str = Field(default="", alias="computedAt")
    notes: list[str] = Field(default_factory=list)


def get_trigger_ledger(session: AsyncSession) -> Any:
    """Ledger durable del recibo (``platform_events``). Parchable en tests."""
    from bolsa_infrastructure.database.repositories.orchestrator_trigger_ledger import (
        SqlAlchemyTriggerLedger,
    )

    return SqlAlchemyTriggerLedger(session)


def build_orchestrator(session_factory: Any) -> Any:
    """Composición del orquestador real. Parchable en tests.

    Es la MISMA composición del worker de fondo: el disparador no tiene un segundo
    embudo. La diferencia es el techo de fase y la ausencia de vigilancia.
    """
    from bolsa_api.background.auto_orchestrator_worker import (
        build_orchestrator as _build,
    )

    return _build(session_factory)


async def _require_open_account(
    session: AsyncSession, account_id: str, principal: str | None
) -> None:
    """409 si la cuenta está cerrada; 404 si no es visible (indistinguible)."""
    try:
        account = await get_account_repository(session).get_account(
            account_id, owner_user_id=principal
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="account_not_found") from exc
    if str(getattr(account, "status", "") or "") == _ACCOUNT_CLOSED:
        raise HTTPException(
            status_code=409,
            detail=(
                "account_closed: la cuenta está cerrada; el embudo LAB no se ejecuta "
                "sobre una cuenta cerrada."
            ),
        )


def _to_dto(receipt: Any) -> OrchestratorRunReceiptDto:
    return OrchestratorRunReceiptDto(
        run_id=receipt.run_id,
        instrument_id=receipt.instrument_id,
        account_id=receipt.account_id,
        dry_run=receipt.dry_run,
        status=receipt.status,
        phase_reached=receipt.phase_reached,
        cycle=receipt.cycle,
        idempotency_key=receipt.idempotency_key,
        gates=[
            OrchestratorRunGateDto(
                gate=str(gate.get("gate") or ""),
                status=gate.get("status"),
                detail=gate.get("detail"),
            )
            for gate in receipt.gates
        ],
        candidates=receipt.candidates,
        evaluated=receipt.evaluated,
        promoted=receipt.promoted,
        active_version_id=receipt.active_version_id,
        reasons=list(receipt.reasons),
        writes=list(receipt.writes),
        replayed=receipt.replayed,
        audit_event_id=receipt.audit_event_id,
        computed_at=receipt.computed_at,
        notes=list(receipt.notes),
    )


@router.post("/auto/orchestrator/run", response_model=OrchestratorRunReceiptDto)
async def run_auto_orchestrator(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    body: Annotated[OrchestratorRunRequestDto | None, Body()] = None,
) -> OrchestratorRunReceiptDto:
    """Ejecuta (o reproduce) una pasada del embudo con techo FINALISTA."""
    if body is None or not body.instrument_id.strip():
        # Sin instrumento no hay ciclo: y desde luego no hay escritura alguna.
        raise HTTPException(
            status_code=400,
            detail="instrument_required: instrumentId es obligatorio.",
        )
    if body.to_phase != TRIGGER_MAX_PHASE:
        raise HTTPException(
            status_code=400,
            detail=(
                "phase_not_allowed: toPhase máximo admitido es "
                f"{TRIGGER_MAX_PHASE!r}; ACTIVE solo por decide_promotion."
            ),
        )

    principal = get_request_principal(request)
    # F7c: cuenta ajena/inexistente ⇒ 404; ausente ⇒ cuenta por defecto (o ninguna).
    account_id = await resolve_account_scope_or_default(request, body.account_id)
    if body.account_id is not None and account_id is not None:
        await _require_open_account(session, account_id, principal)

    trigger = OrchestratorTrigger(
        orchestrator=build_orchestrator(get_session_factory(request)),
        ledger=get_trigger_ledger(session),
    )
    try:
        receipt = await trigger.execute(
            TriggerRequest(
                instrument_id=body.instrument_id,
                account_id=account_id,
                dry_run=body.dry_run,
                to_phase=body.to_phase,
                data_snapshot_id=body.data_snapshot_id,
                actor=principal or "anonymous",
            )
        )
    except TriggerRequestError as exc:
        raise HTTPException(status_code=400, detail=f"{exc.code}: {exc.detail}") from exc
    except TriggerScopeError as exc:
        raise HTTPException(status_code=409, detail=f"{exc.code}: {exc.detail}") from exc
    # El recibo de auditoría es la ÚNICA escritura de esta ruta (también en dryRun).
    await session.commit()
    return _to_dto(receipt)
