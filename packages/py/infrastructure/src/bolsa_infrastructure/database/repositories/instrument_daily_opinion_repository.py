"""Repository: instrument_daily_opinions (dictamen EOD / on-demand)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InstrumentDailyOpinionRow


@dataclass(slots=True)
class InstrumentDailyOpinionRecord:
    id: str
    instrument_id: str
    account_id: str | None
    as_of_bar_date: date
    stance: str
    dictamen_stars: int
    strategy_stars: int | None
    io_score: float | None
    fa_score: float | None
    ta_score: float | None
    distress: bool
    reasons: list[str]
    gate_status: str | None
    top_id: str | None
    top_version: int | None
    source: str
    engine_version: str
    idempotency_key: str
    computed_at: datetime
    created_at: datetime
    updated_at: datetime


def _map(row: InstrumentDailyOpinionRow) -> InstrumentDailyOpinionRecord:
    reasons_raw = row.reasons or []
    reasons = [str(x) for x in reasons_raw] if isinstance(reasons_raw, list) else []
    return InstrumentDailyOpinionRecord(
        id=row.id,
        instrument_id=row.instrument_id,
        account_id=row.account_id,
        as_of_bar_date=row.as_of_bar_date,
        stance=row.stance,
        dictamen_stars=int(row.dictamen_stars),
        strategy_stars=row.strategy_stars,
        io_score=row.io_score,
        fa_score=row.fa_score,
        ta_score=row.ta_score,
        distress=bool(row.distress),
        reasons=reasons,
        gate_status=row.gate_status,
        top_id=row.top_id,
        top_version=row.top_version,
        source=row.source,
        engine_version=row.engine_version,
        idempotency_key=row.idempotency_key,
        computed_at=row.computed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def make_idempotency_key(instrument_id: str, as_of: date, source: str) -> str:
    return f"{instrument_id}|{as_of.isoformat()}|{source}"


class SqlAlchemyInstrumentDailyOpinionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        instrument_id: str,
        as_of: date,
        source: str = "on_demand",
    ) -> InstrumentDailyOpinionRecord | None:
        stmt = select(InstrumentDailyOpinionRow).where(
            InstrumentDailyOpinionRow.instrument_id == instrument_id,
            InstrumentDailyOpinionRow.as_of_bar_date == as_of,
            InstrumentDailyOpinionRow.source == source,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _map(row) if row else None

    async def list_for_instruments(
        self,
        instrument_ids: list[str],
        as_of: date,
        source: str = "on_demand",
    ) -> list[InstrumentDailyOpinionRecord]:
        ids = [i for i in instrument_ids if i]
        if not ids:
            return []
        stmt = select(InstrumentDailyOpinionRow).where(
            InstrumentDailyOpinionRow.instrument_id.in_(ids),
            InstrumentDailyOpinionRow.as_of_bar_date == as_of,
            InstrumentDailyOpinionRow.source == source,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map(r) for r in rows]

    async def upsert(self, payload: dict[str, Any]) -> InstrumentDailyOpinionRecord:
        instrument_id = str(payload["instrument_id"])
        as_of: date = payload["as_of_bar_date"]
        source = str(payload.get("source") or "on_demand")
        key = str(payload.get("idempotency_key") or make_idempotency_key(instrument_id, as_of, source))
        now = datetime.now(UTC)
        existing = await self.get(instrument_id, as_of, source)
        if existing is None:
            row = InstrumentDailyOpinionRow(
                id=f"ido_{uuid4().hex}",
                instrument_id=instrument_id,
                account_id=payload.get("account_id"),
                as_of_bar_date=as_of,
                stance=str(payload["stance"]),
                dictamen_stars=int(payload["dictamen_stars"]),
                strategy_stars=payload.get("strategy_stars"),
                io_score=payload.get("io_score"),
                fa_score=payload.get("fa_score"),
                ta_score=payload.get("ta_score"),
                distress=bool(payload.get("distress") or False),
                reasons=list(payload.get("reasons") or []),
                gate_status=payload.get("gate_status"),
                top_id=payload.get("top_id"),
                top_version=payload.get("top_version"),
                source=source,
                engine_version=str(payload.get("engine_version") or "opinion_v1"),
                idempotency_key=key,
                computed_at=payload.get("computed_at") or now,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
            return _map(row)

        stmt = select(InstrumentDailyOpinionRow).where(InstrumentDailyOpinionRow.id == existing.id)
        row = (await self._session.execute(stmt)).scalar_one()
        row.account_id = payload.get("account_id")
        row.stance = str(payload["stance"])
        row.dictamen_stars = int(payload["dictamen_stars"])
        row.strategy_stars = payload.get("strategy_stars")
        row.io_score = payload.get("io_score")
        row.fa_score = payload.get("fa_score")
        row.ta_score = payload.get("ta_score")
        row.distress = bool(payload.get("distress") or False)
        row.reasons = list(payload.get("reasons") or [])
        row.gate_status = payload.get("gate_status")
        row.top_id = payload.get("top_id")
        row.top_version = payload.get("top_version")
        row.engine_version = str(payload.get("engine_version") or "opinion_v1")
        row.computed_at = payload.get("computed_at") or now
        row.updated_at = now
        await self._session.commit()
        await self._session.refresh(row)
        return _map(row)
