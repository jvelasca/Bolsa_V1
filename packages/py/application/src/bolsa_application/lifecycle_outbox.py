"""V1.90–V1.92 — Lifecycle outbox: durable pending appends (fail-soft without loss).

PositionSync / AUTO persist principal state + enqueue outbox in the same TX,
then drain post-COMMIT (HTTP kick and/or LifecycleOutboxWorker). Crash between
persist and append leaves a pending row that worker / lifespan drain recovers.

V1.92: claim_batch is FIFO per position_id (at most one claimable head).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow
from sqlalchemy import and_, exists, not_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from bolsa_application.lifecycle_event_store import AppendLifecycleEvent
from bolsa_application.lifecycle_from_fill import append_lifecycle_from_confirm_fill

logger = logging.getLogger(__name__)

OUTBOX_MAX_ATTEMPTS = 5
OUTBOX_STALE_PROCESSING_SECONDS = 120
# V1.93 — Consola SLA thresholds (observability only; not a pager).
OUTBOX_SLA_PENDING_SECONDS = 60
OUTBOX_SLA_PROCESSING_SECONDS = 120
SESSION_OUTBOX_ENQUEUED = "lifecycle_outbox_enqueued"
OutboxStatus = str  # pending | processing | applied | dead
_ACTIVE_STATUSES = ("pending", "processing", "dead")


def _now() -> datetime:
    return datetime.now(UTC)


def _backoff_seconds(attempts: int) -> int:
    """Exponential backoff: 2^attempts seconds (capped)."""
    return int(min(2 ** max(attempts, 1), 300))


@dataclass(frozen=True, slots=True)
class LifecycleOutboxRecord:
    id: str
    position_id: str
    account_id: str
    transaction_id: str
    kind: str
    payload: dict[str, Any]
    status: str
    attempts: int
    last_error: str | None
    next_attempt_at: datetime | None = None
    claimed_at: datetime | None = None
    created_at: datetime | None = None


class LifecycleOutboxStore(Protocol):
    async def enqueue(
        self,
        *,
        position_id: str,
        account_id: str,
        transaction_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> LifecycleOutboxRecord: ...

    async def list_pending(
        self, *, limit: int = 50
    ) -> list[LifecycleOutboxRecord]: ...

    async def claim_batch(
        self, *, limit: int = 50
    ) -> list[LifecycleOutboxRecord]: ...

    async def mark_applied(self, outbox_id: str) -> None: ...

    async def mark_attempt(
        self,
        outbox_id: str,
        *,
        error: str,
        dead: bool = False,
    ) -> None: ...

    async def requeue(
        self,
        outbox_id: str,
        *,
        reset_attempts: bool = True,
    ) -> LifecycleOutboxRecord | None: ...


class InMemoryLifecycleOutboxStore:
    def __init__(self) -> None:
        self._by_id: dict[str, LifecycleOutboxRecord] = {}
        self._by_tx: dict[str, str] = {}
        self._seq = 0

    async def enqueue(
        self,
        *,
        position_id: str,
        account_id: str,
        transaction_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> LifecycleOutboxRecord:
        existing_id = self._by_tx.get(transaction_id)
        if existing_id:
            return self._by_id[existing_id]
        self._seq += 1
        # Monotonic created_at so FIFO is stable even within the same wall-clock ms.
        created = datetime.fromtimestamp(self._seq, tz=UTC)
        row = LifecycleOutboxRecord(
            id=f"lox-{uuid4().hex[:16]}",
            position_id=position_id,
            account_id=account_id,
            transaction_id=transaction_id,
            kind=kind,
            payload=dict(payload),
            status="pending",
            attempts=0,
            last_error=None,
            next_attempt_at=None,
            claimed_at=None,
            created_at=created,
        )
        self._by_id[row.id] = row
        self._by_tx[transaction_id] = row.id
        return row

    async def list_pending(
        self, *, limit: int = 50
    ) -> list[LifecycleOutboxRecord]:
        now = _now()
        pending = [
            r
            for r in self._by_id.values()
            if r.status == "pending"
            and (r.next_attempt_at is None or r.next_attempt_at <= now)
        ]
        return pending[:limit]

    async def claim_batch(
        self, *, limit: int = 50
    ) -> list[LifecycleOutboxRecord]:
        """V1.92: claim at most one event per position (FIFO head of queue)."""
        now = _now()
        stale_before = now - timedelta(seconds=OUTBOX_STALE_PROCESSING_SECONDS)
        active = [
            r for r in self._by_id.values() if r.status in _ACTIVE_STATUSES
        ]
        heads: dict[str, LifecycleOutboxRecord] = {}
        for row in sorted(
            active,
            key=lambda r: (
                r.position_id,
                r.created_at or datetime.min.replace(tzinfo=UTC),
                r.id,
            ),
        ):
            if row.position_id not in heads:
                heads[row.position_id] = row

        claimed: list[LifecycleOutboxRecord] = []
        for row in sorted(
            heads.values(),
            key=lambda r: (r.created_at or datetime.min.replace(tzinfo=UTC), r.id),
        ):
            if len(claimed) >= limit:
                break
            due = row.next_attempt_at is None or row.next_attempt_at <= now
            stale = (
                row.status == "processing"
                and row.claimed_at is not None
                and row.claimed_at <= stale_before
            )
            if not ((row.status == "pending" and due) or stale):
                continue
            updated = replace(row, status="processing", claimed_at=now)
            self._by_id[row.id] = updated
            claimed.append(updated)
        return claimed

    async def mark_applied(self, outbox_id: str) -> None:
        row = self._by_id.get(outbox_id)
        if row is None:
            return
        self._by_id[outbox_id] = replace(
            row,
            status="applied",
            last_error=None,
            next_attempt_at=None,
            claimed_at=None,
        )

    async def mark_attempt(
        self,
        outbox_id: str,
        *,
        error: str,
        dead: bool = False,
    ) -> None:
        row = self._by_id.get(outbox_id)
        if row is None:
            return
        attempts = row.attempts + 1
        next_at = None if dead else _now() + timedelta(seconds=_backoff_seconds(attempts))
        self._by_id[outbox_id] = replace(
            row,
            status="dead" if dead else "pending",
            attempts=attempts,
            last_error=error,
            next_attempt_at=next_at,
            claimed_at=None,
        )

    async def requeue(
        self,
        outbox_id: str,
        *,
        reset_attempts: bool = True,
    ) -> LifecycleOutboxRecord | None:
        row = self._by_id.get(outbox_id)
        if row is None or row.status != "dead":
            return None
        updated = replace(
            row,
            status="pending",
            attempts=0 if reset_attempts else row.attempts,
            last_error=None,
            next_attempt_at=None,
            claimed_at=None,
        )
        self._by_id[outbox_id] = updated
        return updated


def _row_to_record(row: LifecycleOutboxRow) -> LifecycleOutboxRecord:
    return LifecycleOutboxRecord(
        id=row.id,
        position_id=row.position_id,
        account_id=row.account_id,
        transaction_id=row.transaction_id,
        kind=row.kind,
        payload=dict(row.payload or {}),
        status=row.status,
        attempts=int(row.attempts or 0),
        last_error=row.last_error,
        next_attempt_at=getattr(row, "next_attempt_at", None),
        claimed_at=getattr(row, "claimed_at", None),
        created_at=getattr(row, "created_at", None),
    )


class PostgresLifecycleOutboxStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _mark_session_enqueued(self) -> None:
        self._session.info[SESSION_OUTBOX_ENQUEUED] = True

    async def enqueue(
        self,
        *,
        position_id: str,
        account_id: str,
        transaction_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> LifecycleOutboxRecord:
        now = _now()
        oid = f"lox-{uuid4().hex[:16]}"
        stmt = (
            pg_insert(LifecycleOutboxRow)
            .values(
                id=oid,
                position_id=position_id,
                account_id=account_id,
                transaction_id=transaction_id,
                kind=kind,
                payload=payload,
                status="pending",
                attempts=0,
                last_error=None,
                next_attempt_at=None,
                claimed_at=None,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["transaction_id"])
            .returning(LifecycleOutboxRow.id)
        )
        result = await self._session.execute(stmt)
        inserted = result.scalar_one_or_none()
        await self._session.flush()
        self._mark_session_enqueued()
        if inserted:
            row = await self._session.get(LifecycleOutboxRow, inserted)
            assert row is not None
            return _row_to_record(row)
        existing = (
            await self._session.execute(
                select(LifecycleOutboxRow).where(
                    LifecycleOutboxRow.transaction_id == transaction_id
                )
            )
        ).scalar_one()
        return _row_to_record(existing)

    async def list_pending(
        self, *, limit: int = 50
    ) -> list[LifecycleOutboxRecord]:
        now = _now()
        stmt = (
            select(LifecycleOutboxRow)
            .where(
                LifecycleOutboxRow.status == "pending",
                or_(
                    LifecycleOutboxRow.next_attempt_at.is_(None),
                    LifecycleOutboxRow.next_attempt_at <= now,
                ),
            )
            .order_by(LifecycleOutboxRow.created_at.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_row_to_record(r) for r in rows]

    async def claim_batch(
        self, *, limit: int = 50
    ) -> list[LifecycleOutboxRecord]:
        """V1.92: claim FIFO head per position_id (SKIP LOCKED)."""
        now = _now()
        stale_before = now - timedelta(seconds=OUTBOX_STALE_PROCESSING_SECONDS)
        earlier = aliased(LifecycleOutboxRow)
        is_head = not_(
            exists(
                select(1)
                .select_from(earlier)
                .where(
                    earlier.position_id == LifecycleOutboxRow.position_id,
                    earlier.status.in_(_ACTIVE_STATUSES),
                    or_(
                        earlier.created_at < LifecycleOutboxRow.created_at,
                        and_(
                            earlier.created_at == LifecycleOutboxRow.created_at,
                            earlier.id < LifecycleOutboxRow.id,
                        ),
                    ),
                )
            )
        )
        stmt = (
            select(LifecycleOutboxRow)
            .where(
                is_head,
                or_(
                    and_(
                        LifecycleOutboxRow.status == "pending",
                        or_(
                            LifecycleOutboxRow.next_attempt_at.is_(None),
                            LifecycleOutboxRow.next_attempt_at <= now,
                        ),
                    ),
                    and_(
                        LifecycleOutboxRow.status == "processing",
                        LifecycleOutboxRow.claimed_at.is_not(None),
                        LifecycleOutboxRow.claimed_at <= stale_before,
                    ),
                ),
            )
            .order_by(LifecycleOutboxRow.created_at.asc(), LifecycleOutboxRow.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        claimed: list[LifecycleOutboxRecord] = []
        for row in rows:
            row.status = "processing"
            row.claimed_at = now
            row.updated_at = now
            claimed.append(_row_to_record(row))
        if claimed:
            await self._session.flush()
        return claimed

    async def mark_applied(self, outbox_id: str) -> None:
        row = await self._session.get(LifecycleOutboxRow, outbox_id)
        if row is None:
            return
        row.status = "applied"
        row.last_error = None
        row.next_attempt_at = None
        row.claimed_at = None
        row.updated_at = _now()
        await self._session.flush()

    async def mark_attempt(
        self,
        outbox_id: str,
        *,
        error: str,
        dead: bool = False,
    ) -> None:
        row = await self._session.get(LifecycleOutboxRow, outbox_id)
        if row is None:
            return
        row.attempts = int(row.attempts or 0) + 1
        row.last_error = error[:2000] if error else None
        if dead:
            row.status = "dead"
            row.next_attempt_at = None
        else:
            row.status = "pending"
            row.next_attempt_at = _now() + timedelta(
                seconds=_backoff_seconds(row.attempts)
            )
        row.claimed_at = None
        row.updated_at = _now()
        await self._session.flush()

    async def requeue(
        self,
        outbox_id: str,
        *,
        reset_attempts: bool = True,
    ) -> LifecycleOutboxRecord | None:
        row = await self._session.get(LifecycleOutboxRow, outbox_id)
        if row is None or row.status != "dead":
            return None
        row.status = "pending"
        if reset_attempts:
            row.attempts = 0
        row.last_error = None
        row.next_attempt_at = None
        row.claimed_at = None
        row.updated_at = _now()
        await self._session.flush()
        return _row_to_record(row)


async def apply_lifecycle_outbox_row(
    outbox: LifecycleOutboxStore,
    append: AppendLifecycleEvent,
    row: LifecycleOutboxRecord,
    *,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
) -> dict[str, int]:
    """Apply one already-claimed outbox row (mark applied|attempt).

    Domain / mapped failures call ``mark_attempt``. Unexpected exceptions
    propagate so a worker TX can rollback and leave ``processing`` durable.
    """
    payload = row.payload
    direct = payload.get("direct_input")
    if isinstance(direct, dict):
        from bolsa_application.lifecycle_event_store import input_from_body

        result = await append.execute(input_from_body(direct))
        if result.ok:
            await outbox.mark_applied(row.id)
            return {"applied": 1, "errors": 0}
        code = result.error.code if result.error else "append_failed"
        dead = row.attempts + 1 >= max_attempts
        await outbox.mark_attempt(row.id, error=code, dead=dead)
        if dead:
            logger.warning(
                "lifecycle_outbox dead id=%s tx=%s code=%s",
                row.id,
                row.transaction_id,
                code,
            )
        return {"applied": 0, "errors": 1}

    result_dict = await append_lifecycle_from_confirm_fill(
        append,
        action=str(payload.get("action") or ""),
        account_id=row.account_id,
        instrument_id=str(payload.get("instrument_id") or ""),
        quantity=float(payload.get("quantity") or 0),
        price=float(payload.get("price") or 0),
        tx_id=row.transaction_id,
        trade=_TradeShim(payload),
        trade_plan_dict=payload.get("trade_plan_dict")
        if isinstance(payload.get("trade_plan_dict"), dict)
        else None,
        decision_id=payload.get("decision_id")
        if isinstance(payload.get("decision_id"), str)
        else None,
        symbol=payload.get("symbol")
        if isinstance(payload.get("symbol"), str)
        else None,
        open_position_id=row.position_id,
        filled_at=payload.get("filled_at")
        if isinstance(payload.get("filled_at"), str)
        else None,
        reason_code=payload.get("reason_code")
        if isinstance(payload.get("reason_code"), str)
        else None,
    )
    status = result_dict.get("status")
    if status == "applied" or (
        status == "skipped"
        and result_dict.get("reason")
        in ("recommend_short_rejected", "unmapped_action_or_missing_ids")
    ):
        await outbox.mark_applied(row.id)
        return {"applied": 1, "errors": 0}
    reason = str(result_dict.get("reason") or status or "unknown")
    dead = row.attempts + 1 >= max_attempts
    await outbox.mark_attempt(row.id, error=reason, dead=dead)
    if dead:
        logger.warning(
            "lifecycle_outbox dead id=%s tx=%s reason=%s",
            row.id,
            row.transaction_id,
            reason,
        )
    return {"applied": 0, "errors": 1}


async def drain_lifecycle_outbox(
    outbox: LifecycleOutboxStore,
    append: AppendLifecycleEvent | None,
    *,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
    limit: int = 50,
) -> dict[str, Any]:
    """Best-effort drain: claim pending → AppendLifecycleEvent → applied/dead.

    Single-session helper for HTTP kick / in-memory tests. The continuous
    worker uses TX-split claim vs apply (V1.93).
    """
    if append is None:
        return {"drained": 0, "applied": 0, "errors": 0, "reason": "no_append"}
    claim = getattr(outbox, "claim_batch", None)
    if claim is not None:
        pending = await claim(limit=limit)
    else:
        pending = await outbox.list_pending(limit=limit)
    applied = 0
    errors = 0
    for row in pending:
        try:
            result = await apply_lifecycle_outbox_row(
                outbox, append, row, max_attempts=max_attempts
            )
            applied += result["applied"]
            errors += result["errors"]
        except Exception as exc:  # noqa: BLE001
            dead = row.attempts + 1 >= max_attempts
            await outbox.mark_attempt(row.id, error=str(exc), dead=dead)
            errors += 1
            logger.warning("lifecycle_outbox drain exception id=%s: %s", row.id, exc)
    return {
        "drained": len(pending),
        "applied": applied,
        "errors": errors,
    }


class _TradeShim:
    """Minimal trade-like object for drain replay from outbox payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.summary = None
        executed = payload.get("filled_at")
        self.transaction = type("Tx", (), {"executed_at": executed})()
        positions = payload.get("ledger_positions")
        if isinstance(positions, list):
            self.summary = type(
                "Sum",
                (),
                {
                    "positions": [
                        type(
                            "Pos",
                            (),
                            {
                                "id": p.get("id"),
                                "instrument_id": p.get("instrument_id"),
                            },
                        )()
                        for p in positions
                        if isinstance(p, dict)
                    ]
                },
            )()


__all__ = [
    "InMemoryLifecycleOutboxStore",
    "LifecycleOutboxRecord",
    "LifecycleOutboxStore",
    "OUTBOX_MAX_ATTEMPTS",
    "OUTBOX_SLA_PENDING_SECONDS",
    "OUTBOX_SLA_PROCESSING_SECONDS",
    "OUTBOX_STALE_PROCESSING_SECONDS",
    "PostgresLifecycleOutboxStore",
    "SESSION_OUTBOX_ENQUEUED",
    "apply_lifecycle_outbox_row",
    "drain_lifecycle_outbox",
]
