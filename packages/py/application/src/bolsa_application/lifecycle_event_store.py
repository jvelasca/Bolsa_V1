"""V1.87 — Lifecycle event store (append-only) + aggregate lock + sequence_no."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.lifecycle import (
    AppendFail,
    AppendOk,
    LifecycleAccounting,
    LifecycleAppendError,
    LifecycleEventInput,
    LifecycleStoreEvent,
    account_lifecycle_fills,
    append_validated_lifecycle_event,
    assert_equity_invariant,
    compute_payload_hash,
    reduce_lifecycle_events,
)
from bolsa_infrastructure.database.models.tables import (
    LifecycleAggregateRow,
    LifecycleEventRow,
)

IntegrityKind = Literal["event_id_conflict", "duplicate_fill_id", "sequence_conflict"]


def _parse_at(iso: str) -> datetime:
    normalized = iso.replace("Z", "+00:00") if iso.endswith("Z") else iso
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _iso_at(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


def _json_num(value: Decimal) -> int | float:
    integral = value.to_integral_value()
    if value == integral:
        return int(integral)
    return float(value)


def accounting_to_dict(acct: LifecycleAccounting) -> dict[str, int | float]:
    return {
        "cash": _json_num(acct.cash),
        "remaining": _json_num(acct.remaining),
        "realizedPnl": _json_num(acct.realized_pnl),
        "unrealizedPnl": _json_num(acct.unrealized_pnl),
        "totalPnl": _json_num(acct.total_pnl),
        "lastPrice": _json_num(acct.last_price),
        "marketValue": _json_num(acct.market_value),
        "totalEquity": _json_num(acct.total_equity),
        "avgCost": _json_num(acct.avg_cost),
        "initialEquity": _json_num(acct.initial_equity),
    }


def classify_lifecycle_integrity_error(exc: IntegrityError) -> IntegrityKind:
    orig = exc.orig
    constraint = ""
    if orig is not None:
        diag = getattr(orig, "diag", None)
        if diag is not None:
            constraint = str(getattr(diag, "constraint_name", None) or "")
        if not constraint:
            constraint = str(orig)
    blob = f"{constraint} {exc}".lower()
    if "fill_id" in blob:
        return "duplicate_fill_id"
    if "sequence" in blob or "position_seq" in blob:
        return "sequence_conflict"
    return "event_id_conflict"


def row_to_event(row: LifecycleEventRow) -> LifecycleStoreEvent:
    return LifecycleStoreEvent(
        event_id=row.event_id,
        position_id=row.position_id,
        kind=row.kind,  # type: ignore[arg-type]
        at=_iso_at(row.at),
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        decision_id=row.decision_id,
        trade_plan_id=row.trade_plan_id,
        symbol=row.symbol,
        side=row.side,
        currency=row.currency,
        fill_id=row.fill_id,
        quantity=_money(row.quantity),
        price=_money(row.price),
        fees=_money(row.fees),
        venue=row.venue,
        venue_order_id=row.venue_order_id,
        previous_stop=_money(row.previous_stop),
        new_stop=_money(row.new_stop),
        reason=row.reason,
        revision_id=row.revision_id,
        payload_hash=row.payload_hash,
        schema_version=row.schema_version,
        causation_id=row.causation_id,
        correlation_id=row.correlation_id,
        sequence_no=row.sequence_no,
    )


def event_to_row(event: LifecycleStoreEvent) -> LifecycleEventRow:
    payload = event.to_canonical_dict()
    return LifecycleEventRow(
        id=str(uuid4()),
        event_id=event.event_id,
        account_id=event.account_id or "",
        position_id=event.position_id,
        instrument_id=event.instrument_id or "",
        decision_id=event.decision_id or "",
        trade_plan_id=event.trade_plan_id or "",
        symbol=event.symbol or "",
        side=event.side or "LONG",
        currency=event.currency or "USD",
        kind=event.kind,
        at=_parse_at(event.at),
        sequence_no=event.sequence_no if event.sequence_no is not None else 0,
        fill_id=event.fill_id,
        quantity=event.quantity,
        price=event.price,
        fees=event.fees,
        venue=event.venue,
        venue_order_id=event.venue_order_id,
        previous_stop=event.previous_stop,
        new_stop=event.new_stop,
        reason=event.reason,
        revision_id=event.revision_id,
        payload=payload,
        payload_hash=event.payload_hash or compute_payload_hash(event),
        schema_version=event.schema_version,
        causation_id=event.causation_id,
        correlation_id=event.correlation_id,
        created_at=datetime.now(UTC),
    )


class LifecycleEventStore(Protocol):
    def locked(
        self, position_id: str, account_id: str
    ) -> AbstractAsyncContextManager[None]: ...

    async def list_by_position(self, position_id: str) -> list[LifecycleStoreEvent]: ...

    async def append(self, event: LifecycleStoreEvent) -> LifecycleStoreEvent: ...

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None: ...

    async def get_account_id(self, position_id: str) -> str | None: ...


class PostgresLifecycleEventStore:
    """Append-only PostgreSQL store. No UPDATE/DELETE API. Serializes per position."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def locked(self, position_id: str, account_id: str) -> AsyncIterator[None]:
        stmt = (
            pg_insert(LifecycleAggregateRow)
            .values(
                position_id=position_id,
                account_id=account_id or "",
                last_sequence_no=0,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["position_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()
        lock_stmt = (
            select(LifecycleAggregateRow)
            .where(LifecycleAggregateRow.position_id == position_id)
            .with_for_update()
        )
        await self._session.execute(lock_stmt)
        yield

    async def list_by_position(self, position_id: str) -> list[LifecycleStoreEvent]:
        stmt = (
            select(LifecycleEventRow)
            .where(LifecycleEventRow.position_id == position_id)
            .order_by(LifecycleEventRow.sequence_no.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [row_to_event(row) for row in rows]

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None:
        stmt = select(LifecycleEventRow).where(LifecycleEventRow.event_id == event_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row_to_event(row) if row else None

    async def get_account_id(self, position_id: str) -> str | None:
        agg = await self._session.get(LifecycleAggregateRow, position_id)
        if agg is not None and agg.account_id:
            return agg.account_id
        events = await self.list_by_position(position_id)
        if events and events[0].account_id:
            return events[0].account_id
        return None

    async def append(self, event: LifecycleStoreEvent) -> LifecycleStoreEvent:
        agg = await self._session.get(LifecycleAggregateRow, event.position_id)
        last = agg.last_sequence_no if agg is not None else 0
        stored = replace(event, sequence_no=last + 1)
        async with self._session.begin_nested():
            self._session.add(event_to_row(stored))
            if agg is not None:
                agg.last_sequence_no = stored.sequence_no or last + 1
                if stored.account_id and not agg.account_id:
                    agg.account_id = stored.account_id
            else:
                self._session.add(
                    LifecycleAggregateRow(
                        position_id=stored.position_id,
                        account_id=stored.account_id or "",
                        last_sequence_no=stored.sequence_no or 1,
                        created_at=datetime.now(UTC),
                    )
                )
            await self._session.flush()
        return stored


class InMemoryLifecycleEventStore:
    """Process-local store for unit tests (no PG)."""

    def __init__(self) -> None:
        self._by_position: dict[str, list[LifecycleStoreEvent]] = {}
        self._by_event_id: dict[str, LifecycleStoreEvent] = {}
        self._account: dict[str, str] = {}
        self._seq: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def locked(self, position_id: str, account_id: str) -> AsyncIterator[None]:
        lock = self._locks.setdefault(position_id, asyncio.Lock())
        async with lock:
            if account_id and position_id not in self._account:
                self._account[position_id] = account_id
            yield

    async def list_by_position(self, position_id: str) -> list[LifecycleStoreEvent]:
        rows = list(self._by_position.get(position_id, []))
        return sorted(rows, key=lambda e: e.sequence_no or 0)

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None:
        return self._by_event_id.get(event_id)

    async def get_account_id(self, position_id: str) -> str | None:
        if position_id in self._account:
            return self._account[position_id]
        events = await self.list_by_position(position_id)
        return events[0].account_id if events else None

    async def append(self, event: LifecycleStoreEvent) -> LifecycleStoreEvent:
        if event.event_id in self._by_event_id:
            raise IntegrityError(
                "INSERT",
                {"event_id": event.event_id},
                Exception("duplicate event_id lifecycle_events_event_id_key"),
            )
        if event.fill_id:
            for existing in self._by_event_id.values():
                if existing.fill_id == event.fill_id:
                    raise IntegrityError(
                        "INSERT",
                        {"fill_id": event.fill_id},
                        Exception("duplicate fill_id lifecycle_events_fill_id_uidx"),
                    )
        next_seq = self._seq.get(event.position_id, 0) + 1
        stored = replace(event, sequence_no=next_seq)
        self._seq[event.position_id] = next_seq
        self._by_event_id[stored.event_id] = stored
        self._by_position.setdefault(event.position_id, []).append(stored)
        if stored.account_id:
            self._account.setdefault(event.position_id, stored.account_id)
        return stored


class AppendLifecycleResult:
    def __init__(
        self,
        *,
        ok: bool,
        idempotent: bool = False,
        event: LifecycleStoreEvent | None = None,
        log: list[LifecycleStoreEvent] | None = None,
        stage: str | None = None,
        lineage_path: str | None = None,
        accounting: LifecycleAccounting | None = None,
        error: LifecycleAppendError | None = None,
    ) -> None:
        self.ok = ok
        self.idempotent = idempotent
        self.event = event
        self.log = log or []
        self.stage = stage
        self.lineage_path = lineage_path
        self.accounting = accounting
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        if not self.ok and self.error:
            return {
                "ok": False,
                "error": {"code": self.error.code, "message": self.error.message},
            }
        return {
            "ok": True,
            "idempotent": self.idempotent,
            "count": len(self.log),
            "stage": self.stage,
            "lineagePath": self.lineage_path,
            "event": self.event.to_canonical_dict() if self.event else None,
            "accounting": (
                accounting_to_dict(self.accounting) if self.accounting else None
            ),
        }


class AppendLifecycleEvent:
    """POST path: lock aggregate → load log → validate → insert → sequence."""

    def __init__(self, store: LifecycleEventStore) -> None:
        self._store = store

    async def execute(
        self,
        input_event: LifecycleEventInput,
        *,
        position_id: str | None = None,
    ) -> AppendLifecycleResult:
        pos = position_id or input_event.position_id or "pos-e2e-lifecycle-1"
        if input_event.position_id is None:
            input_event = replace(input_event, position_id=pos)
        account_id = input_event.account_id or ""

        async with self._store.locked(pos, account_id):
            return await self._execute_locked(input_event, pos)

    async def _execute_locked(
        self,
        input_event: LifecycleEventInput,
        pos: str,
    ) -> AppendLifecycleResult:
        log = await self._store.list_by_position(pos)
        result = append_validated_lifecycle_event(log, input_event)
        if isinstance(result, AppendFail):
            return AppendLifecycleResult(ok=False, error=result.error, log=log)

        assert isinstance(result, AppendOk)
        if result.idempotent:
            acct = account_lifecycle_fills(result.log) if result.log else None
            if acct:
                assert_equity_invariant(acct)
            return AppendLifecycleResult(
                ok=True,
                idempotent=True,
                event=result.event,
                log=list(result.log),
                stage=result.stage,
                lineage_path=result.lineage_path,
                accounting=acct,
            )

        try:
            stored = await self._store.append(result.event)
        except IntegrityError as exc:
            kind = classify_lifecycle_integrity_error(exc)
            if kind == "duplicate_fill_id":
                return AppendLifecycleResult(
                    ok=False,
                    error=LifecycleAppendError(
                        code="duplicate_fill_id",
                        message=(
                            f"fillId {result.event.fill_id} already persisted"
                        ),
                    ),
                    log=log,
                )
            if kind == "sequence_conflict":
                return AppendLifecycleResult(
                    ok=False,
                    error=LifecycleAppendError(
                        code="illegal_transition",
                        message="concurrent sequence conflict on position",
                    ),
                    log=log,
                )
            existing = await self._store.get_by_event_id(result.event.event_id)
            if existing is None:
                return AppendLifecycleResult(
                    ok=False,
                    error=LifecycleAppendError(
                        code="event_id_conflict",
                        message="event_id unique violation without existing row",
                    ),
                    log=log,
                )
            existing_hash = existing.payload_hash or compute_payload_hash(existing)
            new_hash = result.event.payload_hash or compute_payload_hash(result.event)
            if existing_hash == new_hash:
                fresh = await self._store.list_by_position(pos)
                acct = account_lifecycle_fills(fresh)
                assert_equity_invariant(acct)
                return AppendLifecycleResult(
                    ok=True,
                    idempotent=True,
                    event=existing,
                    log=fresh,
                    stage=result.stage,
                    lineage_path=result.lineage_path,
                    accounting=acct,
                )
            return AppendLifecycleResult(
                ok=False,
                error=LifecycleAppendError(
                    code="event_id_conflict",
                    message=(
                        f"eventId {result.event.event_id} already exists "
                        "with different payload"
                    ),
                ),
                log=log,
            )

        fresh = await self._store.list_by_position(pos)
        acct = account_lifecycle_fills(fresh)
        assert_equity_invariant(acct)
        return AppendLifecycleResult(
            ok=True,
            idempotent=False,
            event=stored,
            log=fresh,
            stage=result.stage,
            lineage_path=result.lineage_path,
            accounting=acct,
        )


class GetLifecycleSnapshot:
    def __init__(self, store: LifecycleEventStore) -> None:
        self._store = store

    async def execute(self, position_id: str) -> dict[str, Any]:
        log = await self._store.list_by_position(position_id)
        if not log:
            return {
                "positionId": position_id,
                "stage": "candidate",
                "lineagePath": "trail",
                "events": [],
                "accounting": None,
            }
        stage, lineage_path = reduce_lifecycle_events(log)
        acct = account_lifecycle_fills(log)
        assert_equity_invariant(acct)
        return {
            "positionId": position_id,
            "stage": stage,
            "lineagePath": lineage_path,
            "events": [e.to_canonical_dict() for e in log],
            "accounting": accounting_to_dict(acct),
        }


def input_from_body(body: dict[str, Any]) -> LifecycleEventInput:
    kind = body.get("kind")
    if not isinstance(kind, str):
        raise ValueError("kind required")
    return LifecycleEventInput(
        kind=kind,  # type: ignore[arg-type]
        at=body.get("at"),
        event_id=body.get("eventId") or body.get("event_id"),
        position_id=body.get("positionId") or body.get("position_id"),
        account_id=body.get("accountId") or body.get("account_id"),
        instrument_id=body.get("instrumentId") or body.get("instrument_id"),
        decision_id=body.get("decisionId") or body.get("decision_id"),
        trade_plan_id=body.get("tradePlanId") or body.get("trade_plan_id"),
        symbol=body.get("symbol"),
        side=body.get("side"),
        currency=body.get("currency"),
        fill_id=body.get("fillId") or body.get("fill_id"),
        quantity=_opt_decimal(body.get("quantity")),
        price=_opt_decimal(body.get("price")),
        fees=_opt_decimal(body.get("fees")),
        venue=body.get("venue"),
        venue_order_id=body.get("venueOrderId") or body.get("venue_order_id"),
        previous_stop=_opt_decimal(body.get("previousStop") or body.get("previous_stop")),
        new_stop=_opt_decimal(body.get("newStop") or body.get("new_stop")),
        reason=body.get("reason"),
        revision_id=body.get("revisionId") or body.get("revision_id"),
        causation_id=body.get("causationId") or body.get("causation_id"),
        correlation_id=body.get("correlationId") or body.get("correlation_id"),
    )


def _opt_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


__all__ = [
    "AppendLifecycleEvent",
    "AppendLifecycleResult",
    "GetLifecycleSnapshot",
    "InMemoryLifecycleEventStore",
    "LifecycleEventStore",
    "PostgresLifecycleEventStore",
    "accounting_to_dict",
    "classify_lifecycle_integrity_error",
    "input_from_body",
]
