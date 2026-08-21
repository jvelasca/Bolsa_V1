"""API: CORE-R cola/informe/scheduler multi-dispositivo (Q3.4)."""

from __future__ import annotations

from typing import Annotated, Any

from bolsa_application.run_core_r_server_cron import RunCoreRServerCron
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_core_r_state_use_case,
    get_db_session,
    get_sync_core_r_state_use_case,
    require_account_access,
)
from bolsa_api.schemas.core_r import CoreRBundleDto, CoreRBundleResponseDto, SyncCoreRBundleDto
from bolsa_api.schemas.mappers import to_iso

router = APIRouter()


def _empty_bundle(account_id: str) -> CoreRBundleDto:
    return CoreRBundleDto(
        account_id=account_id,
        queue=[],
        reports={},
        scheduler={},
        updated_at=None,
    )


@router.get(
    "/accounts/{account_id}/core-r",
    response_model=CoreRBundleResponseDto,
)
async def get_account_core_r(
    account_id: Annotated[str, Depends(require_account_access)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CoreRBundleResponseDto:
    row = await get_account_core_r_state_use_case(session).execute(account_id)
    if row is None:
        return CoreRBundleResponseDto(data=_empty_bundle(account_id))
    return CoreRBundleResponseDto(
        data=CoreRBundleDto(
            account_id=account_id,
            queue=row.queue,
            reports=row.reports,
            scheduler=row.scheduler,
            updated_at=to_iso(row.updated_at),
        )
    )


@router.put(
    "/accounts/{account_id}/core-r",
    response_model=CoreRBundleResponseDto,
)
async def sync_account_core_r(
    account_id: Annotated[str, Depends(require_account_access)],
    body: SyncCoreRBundleDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CoreRBundleResponseDto:
    """Push cliente → BD (localStorage = cache; BD = SoT)."""
    row = await get_sync_core_r_state_use_case(session).execute(
        account_id,
        queue=body.queue,
        reports=body.reports,
        scheduler=body.scheduler,
    )
    return CoreRBundleResponseDto(
        data=CoreRBundleDto(
            account_id=account_id,
            queue=row.queue,
            reports=row.reports,
            scheduler=row.scheduler,
            updated_at=to_iso(row.updated_at),
        )
    )


@router.post("/core-r/cron/tick")
async def run_core_r_cron_tick(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    force: bool = Query(default=False, description="Ignora intervalMinutes"),
    include_pnl: bool = Query(default=True, description="Incluye degradación PnL DEMO/paper"),
) -> dict[str, Any]:
    """
    Ops: un tick CORE-R servidor sobre todos los blobs.
    Re-encola desde ``reports_json`` + PnL DEMO (−5/−10) si scheduler.enabled + listId.
    No Lista AUTO · no TOP · no paper.
    """
    result = await RunCoreRServerCron(session).execute(force=force, include_pnl=include_pnl)
    return {"data": result}
