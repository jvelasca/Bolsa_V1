"""OperationalIncidentStore — puerto durable DEX-3 (ADR-035).

InMemory: unit tests. Postgres: runtime (sobrevive al PID).
Nunca auto-heal.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_analytics.cognitive.operational_incident import (
    OperationalIncident,
    OperationalIncidentKind,
    OperationalIncidentStatus,
    clear_incident,
    incident_blocks_opening,
    kinds_from_recon,
    open_incident,
    resolve_incident,
)
from bolsa_infrastructure.database.models.tables import OperationalIncidentRow
from bolsa_infrastructure.ids import new_id

IncidentOpeningStatus = Literal["clear", "unresolved"]

_ACTIVE: frozenset[str] = frozenset({"open", "in_review", "resolved"})


class OperationalIncidentStore(Protocol):
    """get/put por id; activo por (account, kind)."""

    async def get(self, incident_id: str) -> OperationalIncident | None: ...

    async def get_active(
        self, account_id: str, kind: OperationalIncidentKind
    ) -> OperationalIncident | None: ...

    async def list_active(self, account_id: str) -> list[OperationalIncident]: ...

    async def put(self, incident: OperationalIncident) -> None: ...


class InMemoryOperationalIncidentStore:
    """Store de proceso. No sobrevive al PID."""

    def __init__(self) -> None:
        self._by_id: dict[str, OperationalIncident] = {}

    async def get(self, incident_id: str) -> OperationalIncident | None:
        key = (incident_id or "").strip()
        if not key:
            return None
        return self._by_id.get(key)

    async def get_active(
        self, account_id: str, kind: OperationalIncidentKind
    ) -> OperationalIncident | None:
        aid = (account_id or "").strip()
        if not aid:
            return None
        for inc in self._by_id.values():
            if inc.account_id == aid and inc.kind == kind and inc.status in _ACTIVE:
                return inc
        return None

    async def list_active(self, account_id: str) -> list[OperationalIncident]:
        aid = (account_id or "").strip()
        if not aid:
            return []
        return [
            inc
            for inc in self._by_id.values()
            if inc.account_id == aid and inc.status in _ACTIVE
        ]

    async def put(self, incident: OperationalIncident) -> None:
        key = (incident.incident_id or "").strip()
        if not key:
            return
        self._by_id[key] = incident


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _kind(raw: str) -> OperationalIncidentKind:
    if raw in {"portfolio_drift", "live_drift", "live_unavailable"}:
        return raw  # type: ignore[return-value]
    return "portfolio_drift"


def _status(raw: str) -> OperationalIncidentStatus:
    if raw in {"open", "in_review", "resolved", "cleared"}:
        return raw  # type: ignore[return-value]
    return "open"


def _row_to_incident(row: OperationalIncidentRow) -> OperationalIncident:
    return OperationalIncident(
        incident_id=row.id,
        account_id=row.account_id,
        kind=_kind(row.kind),
        status=_status(row.status),
        snapshot=row.snapshot,
        opened_at=row.opened_at,
        reviewed_at=row.reviewed_at,
        reviewed_by=row.reviewed_by,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
        resolution_note=row.resolution_note,
        cleared_at=row.cleared_at,
    )


def _apply_row(row: OperationalIncidentRow, incident: OperationalIncident) -> None:
    row.account_id = incident.account_id
    row.kind = incident.kind
    row.status = incident.status
    row.snapshot = incident.snapshot
    row.opened_at = incident.opened_at
    row.reviewed_at = incident.reviewed_at
    row.reviewed_by = incident.reviewed_by
    row.resolved_at = incident.resolved_at
    row.resolved_by = incident.resolved_by
    row.resolution_note = incident.resolution_note
    row.cleared_at = incident.cleared_at
    row.updated_at = _utcnow()


class PostgresOperationalIncidentStore:
    """DEX-3 — persistencia física. put hace commit."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, incident_id: str) -> OperationalIncident | None:
        key = (incident_id or "").strip()
        if not key:
            return None
        stmt = select(OperationalIncidentRow).where(OperationalIncidentRow.id == key)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _row_to_incident(row) if row is not None else None

    async def get_active(
        self, account_id: str, kind: OperationalIncidentKind
    ) -> OperationalIncident | None:
        aid = (account_id or "").strip()
        if not aid:
            return None
        stmt = (
            select(OperationalIncidentRow)
            .where(OperationalIncidentRow.account_id == aid)
            .where(OperationalIncidentRow.kind == kind)
            .where(OperationalIncidentRow.status.in_(tuple(_ACTIVE)))
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _row_to_incident(row) if row is not None else None

    async def list_active(self, account_id: str) -> list[OperationalIncident]:
        aid = (account_id or "").strip()
        if not aid:
            return []
        stmt = (
            select(OperationalIncidentRow)
            .where(OperationalIncidentRow.account_id == aid)
            .where(OperationalIncidentRow.status.in_(tuple(_ACTIVE)))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_row_to_incident(row) for row in rows]

    async def put(self, incident: OperationalIncident) -> None:
        key = (incident.incident_id or "").strip()
        if not key:
            return
        now = _utcnow()
        stmt = select(OperationalIncidentRow).where(OperationalIncidentRow.id == key)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        try:
            if row is None:
                self._session.add(
                    OperationalIncidentRow(
                        id=key,
                        account_id=incident.account_id,
                        kind=incident.kind,
                        status=incident.status,
                        snapshot=incident.snapshot,
                        opened_at=incident.opened_at,
                        reviewed_at=incident.reviewed_at,
                        reviewed_by=incident.reviewed_by,
                        resolved_at=incident.resolved_at,
                        resolved_by=incident.resolved_by,
                        resolution_note=incident.resolution_note,
                        cleared_at=incident.cleared_at,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                _apply_row(row, incident)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise


async def sync_opening_incidents(
    store: OperationalIncidentStore,
    *,
    account_id: str,
    portfolio_recon_status: str | None = None,
    live_recon_status: str | None = None,
    broker_venue: str | None = None,
) -> IncidentOpeningStatus:
    """Abre INC si hay drift/unavailable; devuelve unresolved si hay alguno activo."""
    aid = (account_id or "").strip()
    if not aid:
        return "clear"
    for kind in kinds_from_recon(
        portfolio_recon_status=portfolio_recon_status,
        live_recon_status=live_recon_status,
        broker_venue=broker_venue,
    ):
        existing = await store.get_active(aid, kind)
        if existing is None:
            await store.put(
                open_incident(
                    incident_id=new_id(),
                    account_id=aid,
                    kind=kind,
                    snapshot=kind,
                )
            )
    active = await store.list_active(aid)
    if any(incident_blocks_opening(inc.status) for inc in active):
        return "unresolved"
    return "clear"


async def resolve_and_store(
    store: OperationalIncidentStore,
    *,
    incident_id: str,
    resolution_note: str,
    resolved_by: str | None = None,
) -> OperationalIncident:
    inc = await store.get(incident_id)
    if inc is None:
        raise ValueError("incident:not_found")
    updated = resolve_incident(
        inc,
        resolution_note=resolution_note,
        resolved_by=resolved_by,
    )
    await store.put(updated)
    return updated


async def clear_and_store(
    store: OperationalIncidentStore,
    *,
    incident_id: str,
    recon_status: str | None,
) -> OperationalIncident:
    inc = await store.get(incident_id)
    if inc is None:
        raise ValueError("incident:not_found")
    updated = clear_incident(inc, recon_status=recon_status)
    await store.put(updated)
    return updated


async def mark_in_review_and_store(
    store: OperationalIncidentStore,
    *,
    incident_id: str,
    reviewed_by: str | None = None,
) -> OperationalIncident:
    from bolsa_analytics.cognitive.operational_incident import mark_in_review

    inc = await store.get(incident_id)
    if inc is None:
        raise ValueError("incident:not_found")
    updated = mark_in_review(inc, reviewed_by=reviewed_by)
    await store.put(updated)
    return updated


async def recon_status_for_incident_clear(
    incident: OperationalIncident,
    *,
    portfolio_recon: object,
    live_recon: object,
) -> str:
    """Status recon relevante para clear según kind del incidente."""
    aid = incident.account_id
    if incident.kind == "portfolio_drift":
        return await portfolio_recon.portfolio_recon_status(aid)  # type: ignore[no-any-return]
    return await live_recon.live_recon_status(aid)  # type: ignore[no-any-return]
