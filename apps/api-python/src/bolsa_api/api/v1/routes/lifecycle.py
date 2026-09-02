"""V1.86 — Lifecycle event store HTTP (append-only PG / domain validate).

POST /lifecycle/events — append validated event
GET  /lifecycle/positions/{position_id}/snapshot — reduce log → snapshot
Does NOT replace /portfolio or mock Playwright routes.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_db_session
from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    PostgresLifecycleEventStore,
    input_from_body,
)

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])

_HTTP_400 = frozenset({"invalid_timestamp", "invalid_kind", "invalid_json"})


class LifecycleEventRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    kind: str
    at: str | None = None
    event_id: str | None = Field(default=None, alias="eventId")
    position_id: str | None = Field(default=None, alias="positionId")
    account_id: str | None = Field(default=None, alias="accountId")
    instrument_id: str | None = Field(default=None, alias="instrumentId")
    decision_id: str | None = Field(default=None, alias="decisionId")
    trade_plan_id: str | None = Field(default=None, alias="tradePlanId")
    symbol: str | None = None
    side: str | None = None
    currency: str | None = None
    fill_id: str | None = Field(default=None, alias="fillId")
    quantity: float | None = None
    price: float | None = None
    fees: float | None = None
    venue: str | None = None
    venue_order_id: str | None = Field(default=None, alias="venueOrderId")
    previous_stop: float | None = Field(default=None, alias="previousStop")
    new_stop: float | None = Field(default=None, alias="newStop")
    reason: str | None = None
    revision_id: str | None = Field(default=None, alias="revisionId")
    causation_id: str | None = Field(default=None, alias="causationId")
    correlation_id: str | None = Field(default=None, alias="correlationId")


@router.post("/events")
async def post_lifecycle_event(
    body: LifecycleEventRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    store = PostgresLifecycleEventStore(session)
    uc = AppendLifecycleEvent(store)
    raw = body.model_dump(by_alias=True, exclude_none=False)
    try:
        input_event = input_from_body(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_kind", "message": str(exc)},
        ) from exc

    result = await uc.execute(input_event)
    if not result.ok:
        assert result.error is not None
        status = 400 if result.error.code in _HTTP_400 else 409
        raise HTTPException(
            status_code=status,
            detail={"code": result.error.code, "message": result.error.message},
        )
    await session.commit()
    return {"data": result.to_dict()}


@router.get("/positions/{position_id}/snapshot")
async def get_lifecycle_snapshot(
    position_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    store = PostgresLifecycleEventStore(session)
    uc = GetLifecycleSnapshot(store)
    snap = await uc.execute(position_id)
    return {"data": snap}
