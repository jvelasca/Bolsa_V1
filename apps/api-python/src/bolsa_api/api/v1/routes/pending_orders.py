"""API: órdenes pendientes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_account_id_header,
    get_create_pending_order_use_case,
    get_db_session,
    get_delete_pending_order_use_case,
    get_list_pending_orders_use_case,
)
from bolsa_api.schemas.pending_orders import (
    CreatePendingOrderDto,
    PendingOrderDto,
    PendingOrdersResponseDto,
)
from bolsa_infrastructure.database.repositories.pending_order_repository import PendingOrderRecord

router = APIRouter()


def _to_dto(record: PendingOrderRecord) -> PendingOrderDto:
    return PendingOrderDto(
        id=record.id,
        instrument_id=record.instrument_id,
        symbol=record.symbol,
        side=record.side,
        order_type=record.order_type,
        quantity=record.quantity,
        limit_price=record.limit_price,
        expiry_at=record.expiry_at,
        created_at=record.created_at,
    )


@router.get("/pending-orders", response_model=PendingOrdersResponseDto)
async def list_pending_orders(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)],
) -> PendingOrdersResponseDto:
    items = await get_list_pending_orders_use_case(session).execute(account_id=account_id)
    return PendingOrdersResponseDto(data=[_to_dto(item) for item in items])


@router.post("/pending-orders", response_model=PendingOrdersResponseDto, status_code=201)
async def create_pending_order(
    body: CreatePendingOrderDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)],
) -> PendingOrdersResponseDto:
    expiry = (
        datetime.fromisoformat(body.expiry_at.replace("Z", "+00:00"))
        if body.expiry_at
        else None
    )
    created = await get_create_pending_order_use_case(session).execute(
        instrument_id=body.instrument_id,
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        quantity=body.quantity,
        limit_price=body.limit_price,
        expiry_at=expiry,
        account_id=account_id,
    )
    return PendingOrdersResponseDto(data=[_to_dto(created)])


@router.delete("/pending-orders/{order_id}", status_code=204)
async def delete_pending_order(
    order_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: Annotated[str | None, Depends(get_account_id_header)],
) -> None:
    try:
        await get_delete_pending_order_use_case(session).execute(order_id, account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
