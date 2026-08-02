"""Repository: mandate_tenures + mandate_trade_links (ADR-020 M1b)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import MandateTenureRow, MandateTradeLinkRow


@dataclass(slots=True)
class MandateTenureRecord:
    id: str
    account_id: str
    instrument_id: str
    timeframe: str | None
    strategy_definition_id: str | None
    strategy_label_snapshot: str | None
    effective_from: datetime
    effective_to: datetime | None
    actor: str
    reason: str
    source_top_id: str | None
    source_top_version: int | None
    evidence_level: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MandateTradeLinkRecord:
    transaction_id: str
    mandate_tenure_id: str
    instrument_id: str
    account_id: str
    linked_at: datetime
    engine: str


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _map_tenure(row: MandateTenureRow) -> MandateTenureRecord:
    return MandateTenureRecord(
        id=row.id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        timeframe=row.timeframe,
        strategy_definition_id=row.strategy_definition_id,
        strategy_label_snapshot=row.strategy_label_snapshot,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        actor=row.actor,
        reason=row.reason,
        source_top_id=row.source_top_id,
        source_top_version=row.source_top_version,
        evidence_level=row.evidence_level,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _map_link(row: MandateTradeLinkRow) -> MandateTradeLinkRecord:
    return MandateTradeLinkRecord(
        transaction_id=row.transaction_id,
        mandate_tenure_id=row.mandate_tenure_id,
        instrument_id=row.instrument_id,
        account_id=row.account_id,
        linked_at=row.linked_at,
        engine=row.engine,
    )


class SqlAlchemyMandateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tenures(
        self,
        account_id: str,
        *,
        instrument_id: str | None = None,
    ) -> list[MandateTenureRecord]:
        stmt = select(MandateTenureRow).where(MandateTenureRow.account_id == account_id)
        if instrument_id:
            stmt = stmt.where(MandateTenureRow.instrument_id == instrument_id)
        stmt = stmt.order_by(MandateTenureRow.effective_from.asc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map_tenure(r) for r in rows]

    async def list_links(
        self,
        account_id: str,
        *,
        instrument_id: str | None = None,
    ) -> list[MandateTradeLinkRecord]:
        stmt = select(MandateTradeLinkRow).where(MandateTradeLinkRow.account_id == account_id)
        if instrument_id:
            stmt = stmt.where(MandateTradeLinkRow.instrument_id == instrument_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map_link(r) for r in rows]

    async def sync_account(
        self,
        account_id: str,
        tenures: list[dict[str, Any]],
        links: list[dict[str, Any]],
    ) -> tuple[list[MandateTenureRecord], list[MandateTradeLinkRecord]]:
        """Upsert tenures/links for account; drop local rows not present in payload."""
        now = datetime.now(UTC)
        incoming_tenure_ids = set()

        for raw in tenures:
            tid = str(raw.get("id") or f"mt_{uuid4().hex}")
            incoming_tenure_ids.add(tid)
            existing = await self._session.get(MandateTenureRow, tid)
            eff_from = _parse_dt(raw.get("effectiveFrom") or raw.get("effective_from")) or now
            eff_to = _parse_dt(raw.get("effectiveTo") or raw.get("effective_to"))
            fields = {
                "account_id": account_id,
                "instrument_id": str(raw.get("instrumentId") or raw.get("instrument_id") or ""),
                "timeframe": raw.get("timeframe"),
                "strategy_definition_id": raw.get("strategyDefinitionId")
                or raw.get("strategy_definition_id"),
                "strategy_label_snapshot": raw.get("strategyLabelSnapshot")
                or raw.get("strategy_label_snapshot"),
                "effective_from": eff_from,
                "effective_to": eff_to,
                "actor": str(raw.get("actor") or "user"),
                "reason": str(raw.get("reason") or "manual"),
                "source_top_id": raw.get("sourceTopId") or raw.get("source_top_id"),
                "source_top_version": raw.get("sourceTopVersion") or raw.get("source_top_version"),
                "evidence_level": raw.get("evidenceLevel") or raw.get("evidence_level"),
                "updated_at": now,
            }
            if not fields["instrument_id"]:
                continue
            if existing is None:
                self._session.add(
                    MandateTenureRow(id=tid, created_at=now, **fields),
                )
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)

        existing_tenures = (
            await self._session.execute(
                select(MandateTenureRow).where(MandateTenureRow.account_id == account_id)
            )
        ).scalars().all()
        for row in existing_tenures:
            if row.id not in incoming_tenure_ids:
                await self._session.delete(row)

        await self._session.flush()

        incoming_tx = set()
        for raw in links:
            tx_id = str(raw.get("transactionId") or raw.get("transaction_id") or "")
            tenure_id = str(raw.get("mandateTenureId") or raw.get("mandate_tenure_id") or "")
            if not tx_id or not tenure_id:
                continue
            incoming_tx.add(tx_id)
            linked_at = _parse_dt(raw.get("linkedAt") or raw.get("linked_at")) or now
            fields = {
                "mandate_tenure_id": tenure_id,
                "instrument_id": str(raw.get("instrumentId") or raw.get("instrument_id") or ""),
                "account_id": account_id,
                "linked_at": linked_at,
                "engine": str(raw.get("engine") or "mandate-trade-links-v1"),
            }
            if not fields["instrument_id"]:
                continue
            existing = await self._session.get(MandateTradeLinkRow, tx_id)
            if existing is None:
                self._session.add(MandateTradeLinkRow(transaction_id=tx_id, **fields))
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)

        existing_links = (
            await self._session.execute(
                select(MandateTradeLinkRow).where(MandateTradeLinkRow.account_id == account_id)
            )
        ).scalars().all()
        for row in existing_links:
            if row.transaction_id not in incoming_tx:
                await self._session.delete(row)

        await self._session.commit()
        return (
            await self.list_tenures(account_id),
            await self.list_links(account_id),
        )
