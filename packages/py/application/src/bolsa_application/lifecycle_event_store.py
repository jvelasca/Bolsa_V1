"""V1.87 — Lifecycle event store (append-only) + aggregate lock + sequence_no.

V1.97 — ``append_many`` persists N events in one savepoint (T2 pair atomicity).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import uuid4

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
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_application.lifecycle_t2_bridge import (
    build_t2_triggered_input,
    needs_atomic_t2_pair,
)

# Optional inject: called after flushing event at index ``i`` inside append_many.
AppendManyHook = Callable[[int, LifecycleStoreEvent], Awaitable[None] | None]

IntegrityKind = Literal["event_id_conflict", "duplicate_fill_id", "sequence_conflict"]


async def _run_append_hook(
    hook: AppendManyHook | None,
    index: int,
    event: LifecycleStoreEvent,
) -> None:
    if hook is None:
        return
    maybe = hook(index, event)
    if maybe is not None:
        await maybe


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

    async def list_events_for_account(
        self, account_id: str
    ) -> list[LifecycleStoreEvent]: ...

    async def append(self, event: LifecycleStoreEvent) -> LifecycleStoreEvent: ...

    async def append_many(
        self, events: list[LifecycleStoreEvent]
    ) -> list[LifecycleStoreEvent]: ...

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None: ...

    async def get_account_id(self, position_id: str) -> str | None: ...


class PostgresLifecycleEventStore:
    """Append-only PostgreSQL store. No UPDATE/DELETE API. Serializes per position."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        on_after_append_index: AppendManyHook | None = None,
    ) -> None:
        self._session = session
        self.on_after_append_index = on_after_append_index

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

    async def list_events_for_account(
        self, account_id: str
    ) -> list[LifecycleStoreEvent]:
        """V1.94 — batch read for account-scoped integrity (no N+1)."""
        aid = account_id.strip() if account_id else ""
        if not aid:
            return []
        stmt = (
            select(LifecycleEventRow)
            .where(LifecycleEventRow.account_id == aid)
            .order_by(
                LifecycleEventRow.position_id.asc(),
                LifecycleEventRow.sequence_no.asc(),
            )
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
        stored = await self.append_many([event])
        return stored[0]

    async def append_many(
        self, events: list[LifecycleStoreEvent]
    ) -> list[LifecycleStoreEvent]:
        """Persist N events in one savepoint. Failure rolls back the whole batch."""
        if not events:
            return []
        position_id = events[0].position_id
        if any(e.position_id != position_id for e in events):
            raise ValueError("append_many requires a single position_id")
        agg = await self._session.get(LifecycleAggregateRow, position_id)
        last = agg.last_sequence_no if agg is not None else 0
        stored_list: list[LifecycleStoreEvent] = []
        async with self._session.begin_nested():
            for index, event in enumerate(events):
                last += 1
                stored = replace(event, sequence_no=last)
                self._session.add(event_to_row(stored))
                if agg is not None:
                    agg.last_sequence_no = last
                    if stored.account_id and not agg.account_id:
                        agg.account_id = stored.account_id
                else:
                    agg = LifecycleAggregateRow(
                        position_id=stored.position_id,
                        account_id=stored.account_id or "",
                        last_sequence_no=last,
                        created_at=datetime.now(UTC),
                    )
                    self._session.add(agg)
                await self._session.flush()
                stored_list.append(stored)
                await _run_append_hook(self.on_after_append_index, index, stored)
        return stored_list


class InMemoryLifecycleEventStore:
    """Process-local store for unit tests (no PG)."""

    def __init__(
        self,
        *,
        on_after_append_index: AppendManyHook | None = None,
    ) -> None:
        self._by_position: dict[str, list[LifecycleStoreEvent]] = {}
        self._by_event_id: dict[str, LifecycleStoreEvent] = {}
        self._account: dict[str, str] = {}
        self._seq: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.on_after_append_index = on_after_append_index

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

    async def list_events_for_account(
        self, account_id: str
    ) -> list[LifecycleStoreEvent]:
        aid = account_id.strip() if account_id else ""
        if not aid:
            return []
        out: list[LifecycleStoreEvent] = []
        for pid, acc in self._account.items():
            if acc == aid:
                out.extend(await self.list_by_position(pid))
        # Also catch events whose account_id matches even if aggregate map missed.
        for ev in self._by_event_id.values():
            if ev.account_id == aid and ev not in out:
                out.append(ev)
        return sorted(
            out,
            key=lambda e: (e.position_id, e.sequence_no or 0),
        )

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None:
        return self._by_event_id.get(event_id)

    async def get_account_id(self, position_id: str) -> str | None:
        if position_id in self._account:
            return self._account[position_id]
        events = await self.list_by_position(position_id)
        return events[0].account_id if events else None

    def _append_one_unlocked(self, event: LifecycleStoreEvent) -> LifecycleStoreEvent:
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

    async def append(self, event: LifecycleStoreEvent) -> LifecycleStoreEvent:
        stored = await self.append_many([event])
        return stored[0]

    async def append_many(
        self, events: list[LifecycleStoreEvent]
    ) -> list[LifecycleStoreEvent]:
        """All-or-nothing: on failure after partial apply, restore prior snapshot."""
        if not events:
            return []
        position_id = events[0].position_id
        if any(e.position_id != position_id for e in events):
            raise ValueError("append_many requires a single position_id")

        snap_pos = list(self._by_position.get(position_id, []))
        snap_seq = self._seq.get(position_id, 0)
        snap_account = self._account.get(position_id)
        snap_ids = {e.event_id for e in snap_pos}

        stored_list: list[LifecycleStoreEvent] = []
        try:
            for index, event in enumerate(events):
                stored = self._append_one_unlocked(event)
                stored_list.append(stored)
                await _run_append_hook(self.on_after_append_index, index, stored)
            return stored_list
        except Exception:
            # Roll back this position's appends from this batch.
            self._by_position[position_id] = snap_pos
            self._seq[position_id] = snap_seq
            if snap_account is None:
                self._account.pop(position_id, None)
            else:
                self._account[position_id] = snap_account
            for eid in list(self._by_event_id.keys()):
                if eid not in snap_ids and any(
                    e.event_id == eid for e in stored_list
                ):
                    del self._by_event_id[eid]
            raise


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

    @property
    def store(self) -> LifecycleEventStore:
        return self._store

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

        # V1.97 — from t1_executed, T2_EXECUTED must arrive with T2_TRIGGERED
        # in one savepoint (SEMI Confirm, AUTO, and outbox direct_input).
        if needs_atomic_t2_pair(log, input_event):
            return await self._execute_t2_pair_locked(input_event, pos, log)

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
            return await self._integrity_result(
                exc, result.event, pos, log, result.stage, result.lineage_path
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

    async def _execute_t2_pair_locked(
        self,
        execute_event: LifecycleEventInput,
        pos: str,
        log: list[LifecycleStoreEvent],
    ) -> AppendLifecycleResult:
        """Validate T2_TRIGGERED + T2_EXECUTED in memory, then append_many."""
        trigger_input = build_t2_triggered_input(execute_event)
        trigger_result = append_validated_lifecycle_event(log, trigger_input)
        if isinstance(trigger_result, AppendFail):
            return AppendLifecycleResult(
                ok=False, error=trigger_result.error, log=log
            )
        assert isinstance(trigger_result, AppendOk)
        if trigger_result.idempotent:
            # Trigger already present — fall through to single EXECUTED path.
            return await self._execute_single_validated(execute_event, pos, log)

        mid_log = list(trigger_result.log)
        execute_result = append_validated_lifecycle_event(mid_log, execute_event)
        if isinstance(execute_result, AppendFail):
            return AppendLifecycleResult(
                ok=False, error=execute_result.error, log=log
            )
        assert isinstance(execute_result, AppendOk)
        if execute_result.idempotent:
            return AppendLifecycleResult(
                ok=True,
                idempotent=True,
                event=execute_result.event,
                log=list(execute_result.log),
                stage=execute_result.stage,
                lineage_path=execute_result.lineage_path,
                accounting=account_lifecycle_fills(list(execute_result.log)),
            )

        try:
            stored_pair = await self._store.append_many(
                [trigger_result.event, execute_result.event]
            )
        except IntegrityError as exc:
            return await self._integrity_result(
                exc,
                execute_result.event,
                pos,
                log,
                execute_result.stage,
                execute_result.lineage_path,
            )
        except Exception:
            # Injected crash mid-pair (or unexpected): savepoint / in-memory
            # rollback leaves zero new events; propagate so outer TX can abort.
            raise

        fresh = await self._store.list_by_position(pos)
        acct = account_lifecycle_fills(fresh)
        assert_equity_invariant(acct)
        return AppendLifecycleResult(
            ok=True,
            idempotent=False,
            event=stored_pair[-1],
            log=fresh,
            stage=execute_result.stage,
            lineage_path=execute_result.lineage_path,
            accounting=acct,
        )

    async def _execute_single_validated(
        self,
        input_event: LifecycleEventInput,
        pos: str,
        log: list[LifecycleStoreEvent],
    ) -> AppendLifecycleResult:
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
            return await self._integrity_result(
                exc, result.event, pos, log, result.stage, result.lineage_path
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

    async def _integrity_result(
        self,
        exc: IntegrityError,
        event: LifecycleStoreEvent,
        pos: str,
        log: list[LifecycleStoreEvent],
        stage: str | None,
        lineage_path: str | None,
    ) -> AppendLifecycleResult:
        kind = classify_lifecycle_integrity_error(exc)
        if kind == "duplicate_fill_id":
            return AppendLifecycleResult(
                ok=False,
                error=LifecycleAppendError(
                    code="duplicate_fill_id",
                    message=f"fillId {event.fill_id} already persisted",
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
        existing = await self._store.get_by_event_id(event.event_id)
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
        new_hash = event.payload_hash or compute_payload_hash(event)
        if existing_hash == new_hash:
            fresh = await self._store.list_by_position(pos)
            acct = account_lifecycle_fills(fresh)
            assert_equity_invariant(acct)
            return AppendLifecycleResult(
                ok=True,
                idempotent=True,
                event=existing,
                log=fresh,
                stage=stage,
                lineage_path=lineage_path,
                accounting=acct,
            )
        return AppendLifecycleResult(
            ok=False,
            error=LifecycleAppendError(
                code="event_id_conflict",
                message=(
                    f"eventId {event.event_id} already exists "
                    "with different payload"
                ),
            ),
            log=log,
        )


def snapshot_from_log(
    position_id: str, log: list[LifecycleStoreEvent]
) -> dict[str, Any]:
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


class GetLifecycleSnapshot:
    def __init__(self, store: LifecycleEventStore) -> None:
        self._store = store

    async def execute(self, position_id: str) -> dict[str, Any]:
        log = await self._store.list_by_position(position_id)
        return snapshot_from_log(position_id, log)

    async def execute_for_account(
        self, account_id: str
    ) -> dict[str, dict[str, Any]]:
        """V1.94 — one query → snapshots keyed by position_id."""
        events = await self._store.list_events_for_account(account_id)
        by_pos: dict[str, list[LifecycleStoreEvent]] = {}
        for ev in events:
            by_pos.setdefault(ev.position_id, []).append(ev)
        return {
            pid: snapshot_from_log(pid, log) for pid, log in by_pos.items()
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
