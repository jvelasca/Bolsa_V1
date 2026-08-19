"""API: SEMI Confirm F3 cola multi-dispositivo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_supervised_f3_state_use_case,
    get_db_session,
    get_sync_supervised_f3_state_use_case,
)
from bolsa_api.schemas.mappers import to_iso
from bolsa_api.schemas.supervised_f3 import (
    SupervisedF3BundleDto,
    SupervisedF3BundleResponseDto,
    SyncSupervisedF3BundleDto,
)

router = APIRouter()


def _empty(account_id: str) -> SupervisedF3BundleDto:
    return SupervisedF3BundleDto(
        account_id=account_id,
        items=[],
        active_id=None,
        updated_at=None,
    )


@router.get(
    "/accounts/{account_id}/supervised-f3-queue",
    response_model=SupervisedF3BundleResponseDto,
)
async def get_account_supervised_f3(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SupervisedF3BundleResponseDto:
    row = await get_account_supervised_f3_state_use_case(session).execute(account_id)
    if row is None:
        return SupervisedF3BundleResponseDto(data=_empty(account_id))
    return SupervisedF3BundleResponseDto(
        data=SupervisedF3BundleDto(
            account_id=account_id,
            items=row.queue,
            active_id=row.active_id,
            updated_at=to_iso(row.updated_at),
        )
    )


@router.put(
    "/accounts/{account_id}/supervised-f3-queue",
    response_model=SupervisedF3BundleResponseDto,
)
async def sync_account_supervised_f3(
    account_id: str,
    body: SyncSupervisedF3BundleDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SupervisedF3BundleResponseDto:
    """Push cliente → BD (sessionStorage = cache; BD = SoT)."""
    row = await get_sync_supervised_f3_state_use_case(session).execute(
        account_id,
        items=body.items,
        active_id=body.active_id,
    )
    return SupervisedF3BundleResponseDto(
        data=SupervisedF3BundleDto(
            account_id=account_id,
            items=row.queue,
            active_id=row.active_id,
            updated_at=to_iso(row.updated_at),
        )
    )
