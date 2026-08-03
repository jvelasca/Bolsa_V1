"""API: SEMI Confirm F3 cola multi-dispositivo."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.schemas.supervised_f3 import (
    SupervisedF3BundleDto,
    SupervisedF3BundleResponseDto,
    SyncSupervisedF3BundleDto,
)
from bolsa_infrastructure.database.repositories.supervised_f3_repository import (
    SqlAlchemySupervisedF3Repository,
)

router = APIRouter()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


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
    repo = SqlAlchemySupervisedF3Repository(session)
    row = await repo.get(account_id)
    if row is None:
        return SupervisedF3BundleResponseDto(data=_empty(account_id))
    return SupervisedF3BundleResponseDto(
        data=SupervisedF3BundleDto(
            account_id=account_id,
            items=row.queue,
            active_id=row.active_id,
            updated_at=_iso(row.updated_at),
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
    repo = SqlAlchemySupervisedF3Repository(session)
    items: list[dict[str, Any]] = [q for q in body.items if isinstance(q, dict)][:40]
    active_id = body.active_id if isinstance(body.active_id, str) else None
    if active_id and not any(i.get("id") == active_id for i in items):
        active_id = items[0].get("id") if items else None
        if not isinstance(active_id, str):
            active_id = None
    row = await repo.upsert(account_id, queue=items, active_id=active_id)
    return SupervisedF3BundleResponseDto(
        data=SupervisedF3BundleDto(
            account_id=account_id,
            items=row.queue,
            active_id=row.active_id,
            updated_at=_iso(row.updated_at),
        )
    )
