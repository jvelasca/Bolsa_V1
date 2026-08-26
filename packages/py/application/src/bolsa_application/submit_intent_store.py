"""SubmitIntentStore — puerto durable OR-2 / DEX-1 (ADR-035).

InMemory: unit tests + fallback. Postgres: runtime Confirm (sobrevive al PID).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.cognitive.submit_intent import (
    DurableSubmitIntent,
    SubmitIntentPhase,
)
from bolsa_infrastructure.database.models.tables import SubmitIntentRow
from bolsa_infrastructure.ids import new_id


class SubmitIntentStore(Protocol):
    """get/put/delete por decision_id. Durabilidad = implementación."""

    async def get(self, decision_id: str) -> DurableSubmitIntent | None: ...

    async def put(self, intent: DurableSubmitIntent) -> None: ...

    async def delete(self, decision_id: str) -> None: ...


class InMemorySubmitIntentStore:
    """Store de proceso. Retry mismo worker; no sobrevive al PID."""

    def __init__(self) -> None:
        self._by_decision: dict[str, DurableSubmitIntent] = {}

    async def get(self, decision_id: str) -> DurableSubmitIntent | None:
        key = (decision_id or "").strip()
        if not key:
            return None
        return self._by_decision.get(key)

    async def put(self, intent: DurableSubmitIntent) -> None:
        key = (intent.decision_id or "").strip()
        if not key:
            return
        self._by_decision[key] = intent

    async def delete(self, decision_id: str) -> None:
        key = (decision_id or "").strip()
        if not key:
            return
        self._by_decision.pop(key, None)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _phase(raw: str) -> SubmitIntentPhase:
    if raw in {"recorded", "send_attempted", "venue_bound", "filled"}:
        return raw  # type: ignore[return-value]
    return "recorded"


def _row_to_intent(row: SubmitIntentRow) -> DurableSubmitIntent:
    return DurableSubmitIntent(
        decision_id=row.decision_id,
        intent_id=row.intent_id,
        order_id=row.order_id,
        account_id=row.account_id,
        phase=_phase(row.phase),
        venue_order_id=row.venue_order_id,
        reason=row.reason,
        venue=row.venue or "paper",
        send_attempted_at=row.send_attempted_at,
    )


class PostgresSubmitIntentStore:
    """DEX-1 — persistencia física. put/delete hacen commit (pre-submit durable)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, decision_id: str) -> DurableSubmitIntent | None:
        key = (decision_id or "").strip()
        if not key:
            return None
        stmt = select(SubmitIntentRow).where(SubmitIntentRow.decision_id == key)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _row_to_intent(row) if row is not None else None

    async def put(self, intent: DurableSubmitIntent) -> None:
        key = (intent.decision_id or "").strip()
        if not key:
            return
        now = _utcnow()
        stmt = select(SubmitIntentRow).where(SubmitIntentRow.decision_id == key)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        try:
            if row is None:
                self._session.add(
                    SubmitIntentRow(
                        id=new_id(),
                        decision_id=key,
                        intent_id=intent.intent_id,
                        order_id=intent.order_id,
                        account_id=intent.account_id,
                        venue=intent.venue or "paper",
                        phase=intent.phase,
                        venue_order_id=intent.venue_order_id,
                        reason=intent.reason,
                        send_attempted_at=intent.send_attempted_at,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                row.intent_id = intent.intent_id
                row.order_id = intent.order_id
                row.account_id = intent.account_id
                row.venue = intent.venue or "paper"
                row.phase = intent.phase
                row.venue_order_id = intent.venue_order_id
                row.reason = intent.reason
                row.send_attempted_at = intent.send_attempted_at
                row.updated_at = now
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise

    async def delete(self, decision_id: str) -> None:
        key = (decision_id or "").strip()
        if not key:
            return
        stmt = select(SubmitIntentRow).where(SubmitIntentRow.decision_id == key)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()


_PROCESS_STORE = InMemorySubmitIntentStore()


def process_submit_intent_store() -> InMemorySubmitIntentStore:
    """Singleton de proceso (tests / fallback sin sesión). Runtime API = PG."""
    return _PROCESS_STORE
