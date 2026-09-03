"""V1.87 — Lifecycle event store HTTP (JWT + ownership + append-only PG).

POST /lifecycle/events — append validated event
GET  /lifecycle/positions/{position_id}/snapshot — reduce log → snapshot
Does NOT replace /portfolio or mock Playwright routes.
accountId in the body is a claim to verify, never authority.

V1.90 — typed response DTOs for OpenAPI / contract:check.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import get_account_repository, get_db_session
from bolsa_api.auth.request_principal import require_jwt_principal
from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    PostgresLifecycleEventStore,
    input_from_body,
)

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])

_HTTP_400 = frozenset({"invalid_timestamp", "invalid_kind", "invalid_json"})


class LifecycleEventRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

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
    quantity: Decimal | None = None
    price: Decimal | None = None
    fees: Decimal | None = None
    venue: str | None = None
    venue_order_id: str | None = Field(default=None, alias="venueOrderId")
    previous_stop: Decimal | None = Field(default=None, alias="previousStop")
    new_stop: Decimal | None = Field(default=None, alias="newStop")
    reason: str | None = None
    revision_id: str | None = Field(default=None, alias="revisionId")
    causation_id: str | None = Field(default=None, alias="causationId")
    correlation_id: str | None = Field(default=None, alias="correlationId")


class LifecycleAccountingDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    cash: float | int
    remaining: float | int
    realized_pnl: float | int = Field(alias="realizedPnl")
    unrealized_pnl: float | int = Field(alias="unrealizedPnl")
    total_pnl: float | int = Field(alias="totalPnl")
    last_price: float | int = Field(alias="lastPrice")
    market_value: float | int = Field(alias="marketValue")
    total_equity: float | int = Field(alias="totalEquity")
    avg_cost: float | int = Field(alias="avgCost")
    initial_equity: float | int = Field(alias="initialEquity")


class LifecycleStoreEventDto(BaseModel):
    """Canonical event shape from to_canonical_dict (strict known fields)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

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
    sequence_no: int | None = Field(default=None, alias="sequenceNo")
    fill_id: str | None = Field(default=None, alias="fillId")
    quantity: float | int | None = None
    price: float | int | None = None
    fees: float | int | None = None
    venue: str | None = None
    venue_order_id: str | None = Field(default=None, alias="venueOrderId")
    previous_stop: float | int | None = Field(default=None, alias="previousStop")
    new_stop: float | int | None = Field(default=None, alias="newStop")
    reason: str | None = None
    revision_id: str | None = Field(default=None, alias="revisionId")
    payload_hash: str | None = Field(default=None, alias="payloadHash")
    schema_version: int | None = Field(default=None, alias="schemaVersion")
    causation_id: str | None = Field(default=None, alias="causationId")
    correlation_id: str | None = Field(default=None, alias="correlationId")


class LifecycleSnapshotDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    position_id: str = Field(alias="positionId")
    stage: str
    lineage_path: str = Field(alias="lineagePath")
    events: list[LifecycleStoreEventDto]
    accounting: LifecycleAccountingDto | None = None


class LifecycleSnapshotResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    data: LifecycleSnapshotDataDto


class LifecycleAppendErrorDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class LifecycleAppendDataDto(BaseModel):
    """Typed append success/error payload (replaces dict[str, Any])."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ok: bool
    idempotent: bool | None = None
    count: int | None = None
    stage: str | None = None
    lineage_path: str | None = Field(default=None, alias="lineagePath")
    event: LifecycleStoreEventDto | None = None
    accounting: LifecycleAccountingDto | None = None
    error: LifecycleAppendErrorDto | None = None


class LifecycleAppendResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    data: LifecycleAppendDataDto


class LifecycleOutboxRequeueDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    status: str
    attempts: int
    transaction_id: str = Field(alias="transactionId")
    account_id: str = Field(alias="accountId")
    position_id: str = Field(alias="positionId")


class LifecycleOutboxRequeueResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    data: LifecycleOutboxRequeueDataDto


async def _assert_account_owned(
    session: AsyncSession, principal: str, account_id: str
) -> None:
    try:
        await get_account_repository(session).get_account(
            account_id, owner_user_id=principal
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "account not owned by principal"},
        ) from exc


@router.post("/events", response_model=LifecycleAppendResponseDto)
async def post_lifecycle_event(
    body: LifecycleEventRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[str, Depends(require_jwt_principal)],
) -> dict[str, Any]:
    store = PostgresLifecycleEventStore(session)
    pos = body.position_id or "pos-e2e-lifecycle-1"
    persisted_account = await store.get_account_id(pos)
    if persisted_account:
        await _assert_account_owned(session, principal, persisted_account)
        if body.account_id and body.account_id != persisted_account:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "forbidden",
                    "message": "accountId does not match persisted position",
                },
            )
    else:
        if not body.account_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_kind", "message": "accountId required"},
            )
        await _assert_account_owned(session, principal, body.account_id)

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


@router.get(
    "/positions/{position_id}/snapshot",
    response_model=LifecycleSnapshotResponseDto,
)
async def get_lifecycle_snapshot(
    position_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[str, Depends(require_jwt_principal)],
) -> dict[str, Any]:
    store = PostgresLifecycleEventStore(session)
    uc = GetLifecycleSnapshot(store)
    snap = await uc.execute(position_id)
    if not snap["events"]:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "position not found"},
        )
    account_id = await store.get_account_id(position_id)
    if not account_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "position not found"},
        )
    await _assert_account_owned(session, principal, account_id)
    return {"data": snap}


@router.post(
    "/outbox/{outbox_id}/requeue",
    response_model=LifecycleOutboxRequeueResponseDto,
)
async def requeue_lifecycle_outbox(
    outbox_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[str, Depends(require_jwt_principal)],
) -> dict[str, Any]:
    """V1.91 P2 — operator requeue: dead → pending (audited)."""
    import logging

    from bolsa_application.lifecycle_outbox import PostgresLifecycleOutboxStore
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    row = await session.get(LifecycleOutboxRow, outbox_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "outbox row not found"},
        )
    await _assert_account_owned(session, principal, row.account_id)
    if row.status != "dead":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "not_dead",
                "message": f"outbox status is {row.status}, expected dead",
            },
        )
    store = PostgresLifecycleOutboxStore(session)
    revived = await store.requeue(outbox_id)
    if revived is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "requeue_failed", "message": "could not requeue"},
        )
    logging.getLogger(__name__).info(
        "lifecycle_outbox requeue operator=%s outbox_id=%s tx=%s account=%s",
        principal,
        revived.id,
        revived.transaction_id,
        revived.account_id,
    )
    return {
        "data": {
            "id": revived.id,
            "status": revived.status,
            "attempts": revived.attempts,
            "transactionId": revived.transaction_id,
            "accountId": revived.account_id,
            "positionId": revived.position_id,
        }
    }
