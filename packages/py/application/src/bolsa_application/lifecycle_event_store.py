"""V1.86 — Lifecycle event store (append-only) + append/get snapshot use-case."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
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
from bolsa_infrastructure.database.models.tables import LifecycleEventRow


def _parse_at(iso: str) -> datetime:
    normalized = iso.replace("Z", "+00:00") if iso.endswith("Z") else iso
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _iso_at(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


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
        quantity=float(row.quantity) if row.quantity is not None else None,
        price=float(row.price) if row.price is not None else None,
        fees=float(row.fees) if row.fees is not None else None,
        venue=row.venue,
        venue_order_id=row.venue_order_id,
        previous_stop=float(row.previous_stop) if row.previous_stop is not None else None,
        new_stop=float(row.new_stop) if row.new_stop is not None else None,
        reason=row.reason,
        revision_id=row.revision_id,
        payload_hash=row.payload_hash,
        schema_version=row.schema_version,
        causation_id=row.causation_id,
        correlation_id=row.correlation_id,
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
        fill_id=event.fill_id,
        quantity=Decimal(str(event.quantity)) if event.quantity is not None else None,
        price=Decimal(str(event.price)) if event.price is not None else None,
        fees=Decimal(str(event.fees)) if event.fees is not None else None,
        venue=event.venue,
        venue_order_id=event.venue_order_id,
        previous_stop=(
            Decimal(str(event.previous_stop))
            if event.previous_stop is not None
            else None
        ),
        new_stop=(
            Decimal(str(event.new_stop)) if event.new_stop is not None else None
        ),
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
    async def list_by_position(self, position_id: str) -> list[LifecycleStoreEvent]: ...

    async def append(self, event: LifecycleStoreEvent) -> None: ...

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None: ...


class PostgresLifecycleEventStore:
    """Append-only PostgreSQL store. No UPDATE/DELETE API."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_position(self, position_id: str) -> list[LifecycleStoreEvent]:
        stmt = (
            select(LifecycleEventRow)
            .where(LifecycleEventRow.position_id == position_id)
            .order_by(LifecycleEventRow.at.asc(), LifecycleEventRow.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [row_to_event(row) for row in rows]

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None:
        stmt = select(LifecycleEventRow).where(LifecycleEventRow.event_id == event_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row_to_event(row) if row else None

    async def append(self, event: LifecycleStoreEvent) -> None:
        async with self._session.begin_nested():
            self._session.add(event_to_row(event))
            await self._session.flush()


class InMemoryLifecycleEventStore:
    """Process-local store for unit tests (no PG)."""

    def __init__(self) -> None:
        self._by_position: dict[str, list[LifecycleStoreEvent]] = {}
        self._by_event_id: dict[str, LifecycleStoreEvent] = {}

    async def list_by_position(self, position_id: str) -> list[LifecycleStoreEvent]:
        return list(self._by_position.get(position_id, []))

    async def get_by_event_id(self, event_id: str) -> LifecycleStoreEvent | None:
        return self._by_event_id.get(event_id)

    async def append(self, event: LifecycleStoreEvent) -> None:
        if event.event_id in self._by_event_id:
            raise IntegrityError(
                "INSERT",
                {"event_id": event.event_id},
                Exception("duplicate event_id"),
            )
        self._by_event_id[event.event_id] = event
        self._by_position.setdefault(event.position_id, []).append(event)


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
        acct = self.accounting
        return {
            "ok": True,
            "idempotent": self.idempotent,
            "count": len(self.log),
            "stage": self.stage,
            "lineagePath": self.lineage_path,
            "event": self.event.to_canonical_dict() if self.event else None,
            "accounting": (
                {
                    "cash": acct.cash,
                    "remaining": acct.remaining,
                    "realizedPnl": acct.realized_pnl,
                    "unrealizedPnl": acct.unrealized_pnl,
                    "totalPnl": acct.total_pnl,
                    "lastPrice": acct.last_price,
                    "marketValue": acct.market_value,
                    "totalEquity": acct.total_equity,
                    "avgCost": acct.avg_cost,
                    "initialEquity": acct.initial_equity,
                }
                if acct
                else None
            ),
        }


class AppendLifecycleEvent:
    """POST path: load log → validate → insert → commit semantics via session."""

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
            from dataclasses import replace

            input_event = replace(input_event, position_id=pos)

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
            await self._store.append(result.event)
        except IntegrityError:
            # Race: another writer won UNIQUE(event_id)
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
            event=result.event,
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
            "accounting": {
                "cash": acct.cash,
                "remaining": acct.remaining,
                "realizedPnl": acct.realized_pnl,
                "unrealizedPnl": acct.unrealized_pnl,
                "totalPnl": acct.total_pnl,
                "lastPrice": acct.last_price,
                "marketValue": acct.market_value,
                "totalEquity": acct.total_equity,
                "avgCost": acct.avg_cost,
                "initialEquity": acct.initial_equity,
            },
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
        quantity=_opt_float(body.get("quantity")),
        price=_opt_float(body.get("price")),
        fees=_opt_float(body.get("fees")),
        venue=body.get("venue"),
        venue_order_id=body.get("venueOrderId") or body.get("venue_order_id"),
        previous_stop=_opt_float(body.get("previousStop") or body.get("previous_stop")),
        new_stop=_opt_float(body.get("newStop") or body.get("new_stop")),
        reason=body.get("reason"),
        revision_id=body.get("revisionId") or body.get("revision_id"),
        causation_id=body.get("causationId") or body.get("causation_id"),
        correlation_id=body.get("correlationId") or body.get("correlation_id"),
    )


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


__all__ = [
    "AppendLifecycleEvent",
    "AppendLifecycleResult",
    "GetLifecycleSnapshot",
    "InMemoryLifecycleEventStore",
    "LifecycleEventStore",
    "PostgresLifecycleEventStore",
    "input_from_body",
]
