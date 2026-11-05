"""API: política de EVIDENCIA de rentabilidad por cuenta.

``GET``/``PUT /api/account-evidence-policy`` (cuenta por cabecera ``X-Account-Id``).

Sin fila, ``GET`` devuelve los defaults estrictos con ``isDefault=true``; ``PUT`` valida rangos
y responde 422 con la lista de violaciones (nunca corrige un valor en silencio).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from bolsa_application.account_evidence_policy import (
    PostgresAccountEvidencePolicyStore,
    policy_from_dict,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_db_session,
    resolve_account_scope_or_default,
)

router = APIRouter()


class EvidencePolicyBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    minWindows: int | None = None
    minTradesTotal: int | None = None
    minPositiveWindowPct: float | None = None
    minNetReturnPct: float | None = None
    maxDrawdownPct: float | None = None
    minExcessVsBuyHoldPct: float | None = None
    holdoutPct: float | None = None
    minCommissionBps: float | None = None
    minSlippageBps: float | None = None
    minSpreadBps: float | None = None
    actor: str | None = Field(default=None, max_length=200)


class EvidencePolicyDto(BaseModel):
    accountId: str
    minWindows: int
    minTradesTotal: int
    minPositiveWindowPct: float
    minNetReturnPct: float
    maxDrawdownPct: float
    minExcessVsBuyHoldPct: float
    holdoutPct: float
    minCommissionBps: float
    minSlippageBps: float
    minSpreadBps: float
    minRoundTripCostBps: float
    updatedAt: str | None = None
    actor: str | None = None
    version: int
    isDefault: bool


async def _scope(request: Request, account_id: str | None) -> str:
    scope = await resolve_account_scope_or_default(request, account_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="no_account_scope")
    return str(scope)


@router.get("/account-evidence-policy", response_model=EvidencePolicyDto)
async def get_account_evidence_policy(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> EvidencePolicyDto:
    account = await _scope(request, account_id)
    policy = await PostgresAccountEvidencePolicyStore(session).load(account)
    return EvidencePolicyDto(**policy.to_dict())


@router.put("/account-evidence-policy", response_model=EvidencePolicyDto)
async def put_account_evidence_policy(
    body: EvidencePolicyBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)] = None,
) -> EvidencePolicyDto:
    account = await _scope(request, account_id)
    store = PostgresAccountEvidencePolicyStore(session)
    current = await store.load(account)
    merged = {**current.to_dict(), **body.model_dump(exclude_none=True, exclude={"actor"})}
    try:
        policy = policy_from_dict(account, merged)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    from dataclasses import replace

    await store.save(replace(policy, actor=body.actor, updated_at=datetime.now(UTC).isoformat()))
    return EvidencePolicyDto(**(await store.load(account)).to_dict())


__all__ = ["router"]
