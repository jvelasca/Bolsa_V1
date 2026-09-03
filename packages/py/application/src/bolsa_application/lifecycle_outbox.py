"""V1.90 — Lifecycle outbox: durable pending appends (fail-soft without loss).

PositionSync / AUTO persist principal state, enqueue outbox in the same session,
then drain best-effort. Crash between persist and append leaves a pending row
that lifespan drain recovers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_application.lifecycle_event_store import AppendLifecycleEvent
from bolsa_application.lifecycle_from_fill import append_lifecycle_from_confirm_fill
from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

logger = logging.getLogger(__name__)

OUTBOX_MAX_ATTEMPTS = 5
OutboxStatus = str  # pending | applied | dead


def _now() -> datetime:
    return datetime.now(UTC)


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

    async def mark_applied(self, outbox_id: str) -> None: ...

    async def mark_attempt(
        self,
        outbox_id: str,
        *,
        error: str,
        dead: bool = False,
    ) -> None: ...


class InMemoryLifecycleOutboxStore:
    def __init__(self) -> None:
        self._by_id: dict[str, LifecycleOutboxRecord] = {}
        self._by_tx: dict[str, str] = {}

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
        )
        self._by_id[row.id] = row
        self._by_tx[transaction_id] = row.id
        return row

    async def list_pending(
        self, *, limit: int = 50
    ) -> list[LifecycleOutboxRecord]:
        pending = [r for r in self._by_id.values() if r.status == "pending"]
        return pending[:limit]

    async def mark_applied(self, outbox_id: str) -> None:
        row = self._by_id.get(outbox_id)
        if row is None:
            return
        self._by_id[outbox_id] = LifecycleOutboxRecord(
            id=row.id,
            position_id=row.position_id,
            account_id=row.account_id,
            transaction_id=row.transaction_id,
            kind=row.kind,
            payload=row.payload,
            status="applied",
            attempts=row.attempts,
            last_error=None,
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
        self._by_id[outbox_id] = LifecycleOutboxRecord(
            id=row.id,
            position_id=row.position_id,
            account_id=row.account_id,
            transaction_id=row.transaction_id,
            kind=row.kind,
            payload=row.payload,
            status="dead" if dead else "pending",
            attempts=row.attempts + 1,
            last_error=error,
        )


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
    )


class PostgresLifecycleOutboxStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["transaction_id"])
            .returning(LifecycleOutboxRow.id)
        )
        result = await self._session.execute(stmt)
        inserted = result.scalar_one_or_none()
        await self._session.flush()
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
        stmt = (
            select(LifecycleOutboxRow)
            .where(LifecycleOutboxRow.status == "pending")
            .order_by(LifecycleOutboxRow.created_at.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_row_to_record(r) for r in rows]

    async def mark_applied(self, outbox_id: str) -> None:
        row = await self._session.get(LifecycleOutboxRow, outbox_id)
        if row is None:
            return
        row.status = "applied"
        row.last_error = None
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
        row.status = "dead" if dead else "pending"
        row.updated_at = _now()
        await self._session.flush()


async def drain_lifecycle_outbox(
    outbox: LifecycleOutboxStore,
    append: AppendLifecycleEvent | None,
    *,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
    limit: int = 50,
) -> dict[str, Any]:
    """Best-effort drain of pending outbox rows into AppendLifecycleEvent."""
    if append is None:
        return {"drained": 0, "applied": 0, "errors": 0, "reason": "no_append"}
    pending = await outbox.list_pending(limit=limit)
    applied = 0
    errors = 0
    for row in pending:
        payload = row.payload
        try:
            # AUTO path may plant a pre-built input under "direct_input"
            direct = payload.get("direct_input")
            if isinstance(direct, dict):
                from bolsa_application.lifecycle_event_store import input_from_body

                result = await append.execute(input_from_body(direct))
                if result.ok:
                    await outbox.mark_applied(row.id)
                    applied += 1
                    continue
                code = result.error.code if result.error else "append_failed"
                dead = row.attempts + 1 >= max_attempts
                await outbox.mark_attempt(row.id, error=code, dead=dead)
                errors += 1
                if dead:
                    logger.warning(
                        "lifecycle_outbox dead id=%s tx=%s code=%s",
                        row.id,
                        row.transaction_id,
                        code,
                    )
                continue

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
            )
            status = result_dict.get("status")
            if status == "applied" or (
                status == "skipped"
                and result_dict.get("reason")
                in ("recommend_short_rejected", "unmapped_action_or_missing_ids")
            ):
                # skipped reject/unmapped: mark applied so we don't retry forever
                if status == "skipped":
                    await outbox.mark_applied(row.id)
                else:
                    await outbox.mark_applied(row.id)
                applied += 1
                continue
            reason = str(result_dict.get("reason") or status or "unknown")
            dead = row.attempts + 1 >= max_attempts
            await outbox.mark_attempt(row.id, error=reason, dead=dead)
            errors += 1
            if dead:
                logger.warning(
                    "lifecycle_outbox dead id=%s tx=%s reason=%s",
                    row.id,
                    row.transaction_id,
                    reason,
                )
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
    "PostgresLifecycleOutboxStore",
    "drain_lifecycle_outbox",
]
