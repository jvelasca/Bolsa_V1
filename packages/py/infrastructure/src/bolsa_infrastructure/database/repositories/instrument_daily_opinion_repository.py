"""Repository: instrument_daily_opinions (dictamen EOD / on-demand).

Scope por CUENTA: la postura depende de si ESA cuenta tiene posición abierta, así que la
caché no puede ser global. Las filas antiguas sin cuenta viven en el scope sentinel
``__global__`` (migración 067) y se exponen como ``account_id=None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InstrumentDailyOpinionRow

#: Scope de las filas sin cuenta (heredadas). No es un ``account_id`` real.
GLOBAL_ACCOUNT_SCOPE = "__global__"


def account_scope_for(account_id: str | None) -> str:
    """``account_id`` real o el sentinel global cuando no hay cuenta medida."""
    text = str(account_id or "").strip()
    return text or GLOBAL_ACCOUNT_SCOPE


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
    #: TRI-ESTADO: ``None`` = la cartera no se midió al calcular el dictamen.
    position_open: bool | None = None


def _map(row: InstrumentDailyOpinionRow) -> InstrumentDailyOpinionRecord:
    reasons_raw = row.reasons or []
    reasons = [str(x) for x in reasons_raw] if isinstance(reasons_raw, list) else []
    stored_scope = str(row.account_id or "")
    return InstrumentDailyOpinionRecord(
        id=row.id,
        instrument_id=row.instrument_id,
        account_id=None if stored_scope == GLOBAL_ACCOUNT_SCOPE else (stored_scope or None),
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
        position_open=row.position_open,
    )


def make_idempotency_key(
    instrument_id: str,
    as_of: date,
    source: str,
    account_scope: str = GLOBAL_ACCOUNT_SCOPE,
) -> str:
    scope = account_scope_for(account_scope)
    return f"{instrument_id}|{as_of.isoformat()}|{source}|{scope}"


class SqlAlchemyInstrumentDailyOpinionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        instrument_id: str,
        as_of: date,
        source: str = "on_demand",
        *,
        account_scope: str = GLOBAL_ACCOUNT_SCOPE,
    ) -> InstrumentDailyOpinionRecord | None:
        stmt = select(InstrumentDailyOpinionRow).where(
            InstrumentDailyOpinionRow.instrument_id == instrument_id,
            InstrumentDailyOpinionRow.as_of_bar_date == as_of,
            InstrumentDailyOpinionRow.source == source,
            InstrumentDailyOpinionRow.account_id == account_scope_for(account_scope),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _map(row) if row else None

    async def list_for_instruments(
        self,
        instrument_ids: list[str],
        as_of: date,
        source: str = "on_demand",
        *,
        account_scope: str = GLOBAL_ACCOUNT_SCOPE,
    ) -> list[InstrumentDailyOpinionRecord]:
        ids = [i for i in instrument_ids if i]
        if not ids:
            return []
        stmt = select(InstrumentDailyOpinionRow).where(
            InstrumentDailyOpinionRow.instrument_id.in_(ids),
            InstrumentDailyOpinionRow.as_of_bar_date == as_of,
            InstrumentDailyOpinionRow.source == source,
            InstrumentDailyOpinionRow.account_id == account_scope_for(account_scope),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map(r) for r in rows]

    async def list_history(
        self,
        instrument_id: str,
        *,
        date_from: date,
        date_to: date,
        source: str = "on_demand",
        account_scope: str = GLOBAL_ACCOUNT_SCOPE,
    ) -> list[InstrumentDailyOpinionRecord]:
        stmt = (
            select(InstrumentDailyOpinionRow)
            .where(
                InstrumentDailyOpinionRow.instrument_id == instrument_id,
                InstrumentDailyOpinionRow.source == source,
                InstrumentDailyOpinionRow.as_of_bar_date >= date_from,
                InstrumentDailyOpinionRow.as_of_bar_date <= date_to,
                InstrumentDailyOpinionRow.account_id == account_scope_for(account_scope),
            )
            .order_by(InstrumentDailyOpinionRow.as_of_bar_date.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map(r) for r in rows]

    async def list_range(
        self,
        *,
        date_from: date,
        date_to: date,
        instrument_ids: list[str] | None = None,
        source: str | None = None,
        account_scope: str | None = None,
        limit: int = 5_000,
    ) -> list[InstrumentDailyOpinionRecord]:
        """Rango para telemetría A0. ``account_scope=None`` = todas las cuentas."""
        filters = [
            InstrumentDailyOpinionRow.as_of_bar_date >= date_from,
            InstrumentDailyOpinionRow.as_of_bar_date <= date_to,
        ]
        if instrument_ids:
            ids = [i for i in instrument_ids if i]
            if not ids:
                return []
            filters.append(InstrumentDailyOpinionRow.instrument_id.in_(ids))
        if source:
            filters.append(InstrumentDailyOpinionRow.source == source)
        if account_scope is not None:
            filters.append(
                InstrumentDailyOpinionRow.account_id == account_scope_for(account_scope)
            )
        stmt = (
            select(InstrumentDailyOpinionRow)
            .where(*filters)
            .order_by(
                InstrumentDailyOpinionRow.as_of_bar_date.asc(),
                InstrumentDailyOpinionRow.instrument_id.asc(),
            )
            .limit(max(1, min(int(limit), 20_000)))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_map(r) for r in rows]

    async def upsert(self, payload: dict[str, Any]) -> InstrumentDailyOpinionRecord:
        instrument_id = str(payload["instrument_id"])
        as_of: date = payload["as_of_bar_date"]
        source = str(payload.get("source") or "on_demand")
        scope = str(
            payload.get("account_scope") or account_scope_for(payload.get("account_id"))
        )
        key = str(
            payload.get("idempotency_key")
            or make_idempotency_key(instrument_id, as_of, source, scope)
        )
        now = datetime.now(UTC)
        position_open = payload.get("position_open")
        insert_stmt = pg_insert(InstrumentDailyOpinionRow).values(
            id=f"ido_{uuid4().hex}",
            instrument_id=instrument_id,
            account_id=scope,
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
            position_open=(
                None if position_open is None else bool(position_open)
            ),
            computed_at=payload.get("computed_at") or now,
            created_at=now,
            updated_at=now,
        )
        # Upsert atómico por (instrument_id, as_of_bar_date, source, account_id): la
        # postura depende de la posición de ESA cuenta, así que dos cuentas no comparten
        # fila. `idempotency_key` no se reescribe en conflicto (semántica previa: la
        # clave se fija al crear).
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[
                InstrumentDailyOpinionRow.instrument_id,
                InstrumentDailyOpinionRow.as_of_bar_date,
                InstrumentDailyOpinionRow.source,
                InstrumentDailyOpinionRow.account_id,
            ],
            set_={
                "account_id": insert_stmt.excluded.account_id,
                "stance": insert_stmt.excluded.stance,
                "dictamen_stars": insert_stmt.excluded.dictamen_stars,
                "strategy_stars": insert_stmt.excluded.strategy_stars,
                "io_score": insert_stmt.excluded.io_score,
                "fa_score": insert_stmt.excluded.fa_score,
                "ta_score": insert_stmt.excluded.ta_score,
                "distress": insert_stmt.excluded.distress,
                "reasons": insert_stmt.excluded.reasons,
                "gate_status": insert_stmt.excluded.gate_status,
                "top_id": insert_stmt.excluded.top_id,
                "top_version": insert_stmt.excluded.top_version,
                "engine_version": insert_stmt.excluded.engine_version,
                "position_open": insert_stmt.excluded.position_open,
                "computed_at": insert_stmt.excluded.computed_at,
                "updated_at": insert_stmt.excluded.updated_at,
            },
        ).returning(InstrumentDailyOpinionRow)
        row = (await self._session.execute(stmt)).scalar_one()
        await self._session.commit()
        return _map(row)
