"""Persistencia PG de artefactos cognitivos RFC-008 (D7+)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bolsa_domain.entities.cognitive_artifacts import (
    ConfidenceStateRecord,
    DecisionMemoryRecord,
    DecisionSessionRecord,
    EdgeReportRecord,
    TrialRecordPersist,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    ConfidenceStateRow,
    DecisionMemoryRow,
    DecisionSessionRow,
    EdgeReportRow,
    TrialRecordRow,
)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


class SqlAlchemyCognitiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Decision Memory ─────────────────────────────────────────────

    async def append_decision_memory(self, record: DecisionMemoryRecord) -> DecisionMemoryRecord:
        now = _parse_ts(record.created_at) or datetime.now(UTC)
        row = DecisionMemoryRow(
            id=record.id,
            decision_id=record.decision_id,
            instrument_id=record.instrument_id,
            account_id=record.account_id,
            outcome=record.outcome,
            reasons=list(record.reasons),
            policy_rule_ids=list(record.policy_rule_ids),
            reevaluate_when=list(record.reevaluate_when),
            opportunity_intact=record.opportunity_intact,
            policy_id=record.policy_id,
            policy_version=record.policy_version,
            payload=record.payload,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return record

    # ── Decision Session ────────────────────────────────────────────

    async def append_decision_session(self, record: DecisionSessionRecord) -> DecisionSessionRecord:
        now = _parse_ts(record.created_at) or datetime.now(UTC)
        row = DecisionSessionRow(
            id=record.id,
            kind=record.kind,
            status=record.status,
            instrument_id=record.instrument_id,
            account_id=record.account_id,
            symbol=record.symbol,
            recommendation_id=record.recommendation_id,
            decision_id=record.decision_id,
            payload=record.payload,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return record

    async def get_decision_session(self, session_id: str) -> DecisionSessionRecord | None:
        row = await self._session.get(DecisionSessionRow, session_id)
        if row is None:
            return None
        return DecisionSessionRecord(
            id=row.id,
            kind=row.kind,
            status=row.status,
            instrument_id=row.instrument_id,
            created_at=_iso(row.created_at),
            account_id=row.account_id,
            symbol=row.symbol,
            recommendation_id=row.recommendation_id,
            decision_id=row.decision_id,
            payload=dict(row.payload) if row.payload else None,
        )

    async def list_decision_sessions(
        self,
        *,
        limit: int = 50,
        account_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[DecisionSessionRecord]:
        stmt = (
            select(DecisionSessionRow)
            .order_by(DecisionSessionRow.created_at.desc())
            .limit(limit)
        )
        if account_id:
            stmt = stmt.where(DecisionSessionRow.account_id == account_id)
        if instrument_id:
            stmt = stmt.where(DecisionSessionRow.instrument_id == instrument_id)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            DecisionSessionRecord(
                id=row.id,
                kind=row.kind,
                status=row.status,
                instrument_id=row.instrument_id,
                created_at=_iso(row.created_at),
                account_id=row.account_id,
                symbol=row.symbol,
                recommendation_id=row.recommendation_id,
                decision_id=row.decision_id,
                payload=dict(row.payload) if row.payload else None,
            )
            for row in rows
        ]

    async def update_decision_session(
        self, record: DecisionSessionRecord
    ) -> DecisionSessionRecord:
        row = await self._session.get(DecisionSessionRow, record.id)
        if row is None:
            raise ValueError(f"DecisionSession no encontrada: {record.id}")
        row.kind = record.kind
        row.status = record.status
        row.instrument_id = record.instrument_id
        row.account_id = record.account_id
        row.symbol = record.symbol
        row.recommendation_id = record.recommendation_id
        row.decision_id = record.decision_id
        row.payload = record.payload
        await self._session.flush()
        return record

    async def list_decision_memory(
        self,
        *,
        limit: int = 100,
        account_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[DecisionMemoryRecord]:
        stmt = (
            select(DecisionMemoryRow)
            .order_by(DecisionMemoryRow.created_at.desc())
            .limit(limit)
        )
        if account_id:
            stmt = stmt.where(DecisionMemoryRow.account_id == account_id)
        if instrument_id:
            stmt = stmt.where(DecisionMemoryRow.instrument_id == instrument_id)
        result = await self._session.execute(stmt)
        return [self._map_memory(row) for row in result.scalars().all()]

    def _map_memory(self, row: DecisionMemoryRow) -> DecisionMemoryRecord:
        return DecisionMemoryRecord(
            id=row.id,
            decision_id=row.decision_id,
            instrument_id=row.instrument_id,
            outcome=row.outcome,
            reasons=tuple(row.reasons or []),
            policy_rule_ids=tuple(row.policy_rule_ids or []),
            reevaluate_when=tuple(row.reevaluate_when or []),
            opportunity_intact=row.opportunity_intact,
            created_at=_iso(row.created_at),
            account_id=row.account_id,
            policy_id=row.policy_id,
            policy_version=row.policy_version,
            payload=dict(row.payload) if row.payload else None,
        )

    # ── Trials ──────────────────────────────────────────────────────

    async def append_trial(self, record: TrialRecordPersist) -> TrialRecordPersist:
        now = _parse_ts(record.created_at) or datetime.now(UTC)
        row = TrialRecordRow(
            id=record.id,
            log_id=record.log_id,
            strategy_family_ref=record.strategy_family_ref,
            hypothesis_ref=record.hypothesis_ref,
            params_hash=record.params_hash,
            sharpe_is=None if record.sharpe_is is None else Decimal(str(record.sharpe_is)),
            notes=record.notes,
            account_id=record.account_id,
            payload=record.payload,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return record

    async def count_trials(
        self,
        *,
        strategy_family_ref: str | None = None,
        log_id: str | None = None,
        account_id: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(TrialRecordRow)
        if strategy_family_ref:
            stmt = stmt.where(TrialRecordRow.strategy_family_ref == strategy_family_ref)
        if log_id:
            stmt = stmt.where(TrialRecordRow.log_id == log_id)
        if account_id:
            stmt = stmt.where(TrialRecordRow.account_id == account_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_trials(
        self,
        *,
        strategy_family_ref: str | None = None,
        log_id: str | None = None,
        account_id: str | None = None,
        limit: int = 500,
    ) -> list[TrialRecordPersist]:
        stmt = select(TrialRecordRow).order_by(TrialRecordRow.created_at.asc()).limit(limit)
        if strategy_family_ref:
            stmt = stmt.where(TrialRecordRow.strategy_family_ref == strategy_family_ref)
        if log_id:
            stmt = stmt.where(TrialRecordRow.log_id == log_id)
        if account_id:
            stmt = stmt.where(TrialRecordRow.account_id == account_id)
        result = await self._session.execute(stmt)
        return [self._map_trial(row) for row in result.scalars().all()]

    def _map_trial(self, row: TrialRecordRow) -> TrialRecordPersist:
        return TrialRecordPersist(
            id=row.id,
            log_id=row.log_id,
            strategy_family_ref=row.strategy_family_ref,
            hypothesis_ref=row.hypothesis_ref,
            params_hash=row.params_hash,
            created_at=_iso(row.created_at),
            sharpe_is=None if row.sharpe_is is None else float(row.sharpe_is),
            notes=row.notes,
            account_id=row.account_id,
            payload=dict(row.payload) if row.payload else None,
        )

    # ── Confidence State ────────────────────────────────────────────

    async def upsert_confidence_state(
        self, record: ConfidenceStateRecord
    ) -> ConfidenceStateRecord:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ConfidenceStateRow).where(ConfidenceStateRow.id == record.id)
        )
        row = result.scalar_one_or_none()
        events = list(record.events)
        if row is None:
            row = ConfidenceStateRow(
                id=record.id,
                decision_id=record.decision_id,
                instrument_id=record.instrument_id,
                account_id=record.account_id,
                confidence_0=Decimal(str(record.confidence_0)),
                confidence=Decimal(str(record.confidence)),
                hint=record.hint,
                expires_at=_parse_ts(record.expires_at),
                expired=record.expired,
                events=events,
                notes=list(record.notes),
                payload=record.payload,
                created_at=_parse_ts(record.created_at) or now,
                updated_at=_parse_ts(record.updated_at) or now,
            )
            self._session.add(row)
        else:
            row.confidence = Decimal(str(record.confidence))
            row.hint = record.hint
            row.expires_at = _parse_ts(record.expires_at)
            row.expired = record.expired
            row.events = events
            row.notes = list(record.notes)
            row.payload = record.payload
            row.updated_at = _parse_ts(record.updated_at) or now
            if record.account_id is not None:
                row.account_id = record.account_id
        await self._session.flush()
        return record

    async def get_confidence_state(self, state_id: str) -> ConfidenceStateRecord | None:
        result = await self._session.execute(
            select(ConfidenceStateRow).where(ConfidenceStateRow.id == state_id)
        )
        row = result.scalar_one_or_none()
        return None if row is None else self._map_confidence(row)

    async def list_open_confidence_states(
        self,
        *,
        limit: int = 50,
        account_id: str | None = None,
    ) -> list[ConfidenceStateRecord]:
        stmt = (
            select(ConfidenceStateRow)
            .where(ConfidenceStateRow.expired.is_(False))
            .order_by(ConfidenceStateRow.updated_at.desc())
            .limit(limit)
        )
        if account_id:
            stmt = stmt.where(ConfidenceStateRow.account_id == account_id)
        result = await self._session.execute(stmt)
        return [self._map_confidence(row) for row in result.scalars().all()]

    def _map_confidence(self, row: ConfidenceStateRow) -> ConfidenceStateRecord:
        raw_events = row.events or []
        events = tuple(e for e in raw_events if isinstance(e, dict))
        return ConfidenceStateRecord(
            id=row.id,
            decision_id=row.decision_id,
            instrument_id=row.instrument_id,
            confidence_0=float(row.confidence_0),
            confidence=float(row.confidence),
            hint=row.hint,
            expired=row.expired,
            events=events,
            notes=tuple(row.notes or []),
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
            expires_at=None if row.expires_at is None else _iso(row.expires_at),
            account_id=row.account_id,
            payload=dict(row.payload) if row.payload else None,
        )

    # ── Edge Reports ────────────────────────────────────────────────

    async def append_edge_report(self, record: EdgeReportRecord) -> EdgeReportRecord:
        now = _parse_ts(record.created_at) or datetime.now(UTC)
        row = EdgeReportRow(
            id=record.id,
            version=record.version,
            strategy_or_signal_ref=record.strategy_or_signal_ref,
            instrument_universe_ref=record.instrument_universe_ref,
            account_id=record.account_id,
            credibility=Decimal(str(record.credibility)),
            edge_score=Decimal(str(record.edge_score)),
            band=record.band,
            suite=dict(record.suite),
            notes=list(record.notes),
            payload=record.payload,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return record

    async def latest_edge_report(
        self,
        *,
        strategy_or_signal_ref: str | None = None,
        account_id: str | None = None,
    ) -> EdgeReportRecord | None:
        stmt = select(EdgeReportRow).order_by(EdgeReportRow.created_at.desc()).limit(1)
        if strategy_or_signal_ref:
            stmt = stmt.where(EdgeReportRow.strategy_or_signal_ref == strategy_or_signal_ref)
        if account_id:
            stmt = stmt.where(EdgeReportRow.account_id == account_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return None if row is None else self._map_edge(row)

    def _map_edge(self, row: EdgeReportRow) -> EdgeReportRecord:
        return EdgeReportRecord(
            id=row.id,
            version=row.version,
            strategy_or_signal_ref=row.strategy_or_signal_ref,
            credibility=float(row.credibility),
            edge_score=float(row.edge_score),
            band=row.band,
            suite=dict(row.suite or {}),
            notes=tuple(row.notes or []),
            created_at=_iso(row.created_at),
            instrument_universe_ref=row.instrument_universe_ref,
            account_id=row.account_id,
            payload=dict(row.payload) if row.payload else None,
        )

    async def persistence_stats(self, *, account_id: str | None = None) -> dict[str, Any]:
        """Conteos rápidos para el panel Efectividad."""
        mem_q = select(func.count()).select_from(DecisionMemoryRow)
        trial_q = select(func.count()).select_from(TrialRecordRow)
        edge_q = select(func.count()).select_from(EdgeReportRow)
        conf_q = (
            select(func.count())
            .select_from(ConfidenceStateRow)
            .where(ConfidenceStateRow.expired.is_(False))
        )
        if account_id:
            mem_q = mem_q.where(DecisionMemoryRow.account_id == account_id)
            trial_q = trial_q.where(TrialRecordRow.account_id == account_id)
            edge_q = edge_q.where(EdgeReportRow.account_id == account_id)
            conf_q = conf_q.where(ConfidenceStateRow.account_id == account_id)
        mem_n = int((await self._session.execute(mem_q)).scalar_one())
        trial_n = int((await self._session.execute(trial_q)).scalar_one())
        edge_n = int((await self._session.execute(edge_q)).scalar_one())
        open_conf = int((await self._session.execute(conf_q)).scalar_one())
        return {
            "decisionMemoryCount": mem_n,
            "trialCount": trial_n,
            "edgeReportCount": edge_n,
            "openConfidenceStates": open_conf,
        }
