"""Repository: instrument_narratives (evolución corta por valor)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InstrumentNarrativeRow

NARRATIVE_MAX_CHARS = 4000
NARRATIVE_MAX_LINES = 20
ALLOWED_SCOPES = frozenset({"estudio", "global", "trading"})
ALLOWED_SOURCES = frozenset({"user", "ai", "system"})


@dataclass(slots=True)
class InstrumentNarrativeRecord:
    id: str
    instrument_id: str
    scope: str
    body: str
    source: str
    version: int
    created_at: datetime
    updated_at: datetime


def _map(row: InstrumentNarrativeRow) -> InstrumentNarrativeRecord:
    return InstrumentNarrativeRecord(
        id=row.id,
        instrument_id=row.instrument_id,
        scope=row.scope,
        body=row.body,
        source=row.source,
        version=int(row.version or 1),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def validate_narrative_body(body: str) -> None:
    if len(body) > NARRATIVE_MAX_CHARS:
        raise ValueError(f"body supera {NARRATIVE_MAX_CHARS} caracteres")
    lines = body.replace("\r\n", "\n").split("\n")
    if len(lines) > NARRATIVE_MAX_LINES:
        raise ValueError(f"body supera {NARRATIVE_MAX_LINES} líneas")


class SqlAlchemyInstrumentNarrativeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, instrument_id: str, scope: str = "estudio"
    ) -> InstrumentNarrativeRecord | None:
        stmt = select(InstrumentNarrativeRow).where(
            InstrumentNarrativeRow.instrument_id == instrument_id,
            InstrumentNarrativeRow.scope == scope,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _map(row) if row else None

    async def upsert(
        self,
        *,
        instrument_id: str,
        scope: str,
        body: str,
        source: str = "user",
    ) -> InstrumentNarrativeRecord:
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"scope inválido: {scope}")
        if source not in ALLOWED_SOURCES:
            raise ValueError(f"source inválido: {source}")
        validate_narrative_body(body)
        now = datetime.now(UTC)
        insert_stmt = pg_insert(InstrumentNarrativeRow).values(
            id=f"inar_{uuid4().hex}",
            instrument_id=instrument_id,
            scope=scope,
            body=body,
            source=source,
            version=1,
            created_at=now,
            updated_at=now,
        )
        # Upsert atómico por (instrument_id, scope): antes era check-then-insert y
        # dos escritores concurrentes duplicaban la fila (índice único: migración 041).
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[InstrumentNarrativeRow.instrument_id, InstrumentNarrativeRow.scope],
            set_={
                "body": insert_stmt.excluded.body,
                "source": insert_stmt.excluded.source,
                "version": InstrumentNarrativeRow.version + 1,
                "updated_at": insert_stmt.excluded.updated_at,
            },
        ).returning(InstrumentNarrativeRow)
        row = (await self._session.execute(stmt)).scalar_one()
        await self._session.commit()
        return _map(row)

    async def delete(self, instrument_id: str, scope: str = "estudio") -> bool:
        stmt = select(InstrumentNarrativeRow).where(
            InstrumentNarrativeRow.instrument_id == instrument_id,
            InstrumentNarrativeRow.scope == scope,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True
