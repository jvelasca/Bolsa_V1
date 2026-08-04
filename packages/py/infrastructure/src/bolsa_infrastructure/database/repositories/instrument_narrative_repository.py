"""Repository: instrument_narratives (evolución corta por valor)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
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
        existing = await self.get(instrument_id, scope)
        if existing is None:
            row = InstrumentNarrativeRow(
                id=f"inar_{uuid4().hex}",
                instrument_id=instrument_id,
                scope=scope,
                body=body,
                source=source,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
            return _map(row)

        stmt = select(InstrumentNarrativeRow).where(InstrumentNarrativeRow.id == existing.id)
        row = (await self._session.execute(stmt)).scalar_one()
        row.body = body
        row.source = source
        row.version = int(row.version or 1) + 1
        row.updated_at = now
        await self._session.commit()
        await self._session.refresh(row)
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
