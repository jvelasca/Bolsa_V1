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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
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


class LifecycleOutboxStatsDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    pending: int
    processing: int
    dead: int
    oldest_pending_age_seconds: float | None = Field(
        default=None, alias="oldestPendingAgeSeconds"
    )
    oldest_processing_age_seconds: float | None = Field(
        default=None, alias="oldestProcessingAgeSeconds"
    )
    oldest_dead_age_seconds: float | None = Field(
        default=None, alias="oldestDeadAgeSeconds"
    )
    sla_breached: bool = Field(default=False, alias="slaBreached")


class LifecycleOutboxStatsResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    data: LifecycleOutboxStatsDataDto


class LifecycleReconIssueDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code: str
    position_id: str = Field(alias="positionId")
    detail: str


class LifecycleReconciliationDataDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    account_id: str = Field(alias="accountId")
    status: str
    checked: int
    drift_count: int = Field(alias="driftCount")
    lag_count: int = Field(alias="lagCount")
    blocked_count: int = Field(alias="blockedCount")
    issues: list[LifecycleReconIssueDto]


class LifecycleReconciliationResponseDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    data: LifecycleReconciliationDataDto


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


@router.get(
    "/outbox/stats",
    response_model=LifecycleOutboxStatsResponseDto,
)
async def get_lifecycle_outbox_stats(
    account_id: Annotated[str, Query(alias="accountId")],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[str, Depends(require_jwt_principal)],
) -> dict[str, Any]:
    """V1.92/V1.93 — outbox queue depth + SLA ages for Consola Operativa."""
    from datetime import UTC, datetime

    from bolsa_application.lifecycle_outbox import (
        OUTBOX_SLA_PENDING_SECONDS,
        OUTBOX_SLA_PROCESSING_SECONDS,
    )
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    await _assert_account_owned(session, principal, account_id)
    counts = (
        await session.execute(
            select(LifecycleOutboxRow.status, func.count())
            .where(LifecycleOutboxRow.account_id == account_id)
            .group_by(LifecycleOutboxRow.status)
        )
    ).all()
    by_status = {str(status): int(n) for status, n in counts}
    now = datetime.now(UTC)

    def _age_seconds(value: Any) -> float | None:
        if value is None:
            return None
        created = value
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return max(0.0, (now - created).total_seconds())

    oldest_pending = (
        await session.execute(
            select(func.min(LifecycleOutboxRow.created_at)).where(
                LifecycleOutboxRow.account_id == account_id,
                LifecycleOutboxRow.status == "pending",
            )
        )
    ).scalar_one_or_none()
    oldest_processing = (
        await session.execute(
            select(func.min(LifecycleOutboxRow.claimed_at)).where(
                LifecycleOutboxRow.account_id == account_id,
                LifecycleOutboxRow.status == "processing",
            )
        )
    ).scalar_one_or_none()
    oldest_dead = (
        await session.execute(
            select(func.min(LifecycleOutboxRow.created_at)).where(
                LifecycleOutboxRow.account_id == account_id,
                LifecycleOutboxRow.status == "dead",
            )
        )
    ).scalar_one_or_none()
    pending_age = _age_seconds(oldest_pending)
    processing_age = _age_seconds(oldest_processing)
    dead_age = _age_seconds(oldest_dead)
    sla_breached = (
        (pending_age is not None and pending_age > OUTBOX_SLA_PENDING_SECONDS)
        or (
            processing_age is not None
            and processing_age > OUTBOX_SLA_PROCESSING_SECONDS
        )
    )
    return {
        "data": {
            "pending": by_status.get("pending", 0),
            "processing": by_status.get("processing", 0),
            "dead": by_status.get("dead", 0),
            "oldestPendingAgeSeconds": pending_age,
            "oldestProcessingAgeSeconds": processing_age,
            "oldestDeadAgeSeconds": dead_age,
            "slaBreached": sla_breached,
        }
    }


@router.get(
    "/reconciliation",
    response_model=LifecycleReconciliationResponseDto,
)
async def get_lifecycle_reconciliation(
    account_id: Annotated[str, Query(alias="accountId")],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[str, Depends(require_jwt_principal)],
) -> dict[str, Any]:
    """V1.93 — PositionState ↔ Lifecycle detect/report (no auto-heal)."""
    from bolsa_application.lifecycle_event_store import (
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_application.reconcile_lifecycle_integrity import (
        OutboxSnap,
        ReconcileLifecycleIntegrity,
        ReconcileLifecycleIntegrityInput,
    )
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow
    from bolsa_infrastructure.database.repositories.position_state_repository import (
        SqlAlchemyPositionStateRepository,
    )

    await _assert_account_owned(session, principal, account_id)

    class _OutboxAdapter:
        async def list_for_account(self, acc: str) -> list[OutboxSnap]:
            rows = (
                await session.execute(
                    select(LifecycleOutboxRow).where(
                        LifecycleOutboxRow.account_id == acc,
                        LifecycleOutboxRow.status.in_(
                            ("pending", "processing", "dead")
                        ),
                    )
                )
            ).scalars().all()
            return [
                OutboxSnap(
                    position_id=r.position_id,
                    kind=r.kind,
                    status=r.status,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    report = await ReconcileLifecycleIntegrity(
        positions=SqlAlchemyPositionStateRepository(session),
        snapshots=GetLifecycleSnapshot(PostgresLifecycleEventStore(session)),
        outbox=_OutboxAdapter(),
    ).reconcile(ReconcileLifecycleIntegrityInput(account_id=account_id))
    assert report is not None
    return {"data": report.to_dict()}


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
