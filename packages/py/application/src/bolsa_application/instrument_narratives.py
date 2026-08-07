"""Use cases: narrativa de evolución por instrumento."""

from __future__ import annotations

from bolsa_infrastructure.database.repositories.instrument_narrative_repository import (
    InstrumentNarrativeRecord,
    SqlAlchemyInstrumentNarrativeRepository,
)


class GetInstrumentNarrative:
    def __init__(self, repo: SqlAlchemyInstrumentNarrativeRepository) -> None:
        self._repo = repo

    async def execute(
        self, instrument_id: str, scope: str = "estudio"
    ) -> InstrumentNarrativeRecord | None:
        return await self._repo.get(instrument_id, scope)


class UpsertInstrumentNarrative:
    def __init__(self, repo: SqlAlchemyInstrumentNarrativeRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        instrument_id: str,
        scope: str,
        body: str,
        source: str = "user",
    ) -> InstrumentNarrativeRecord:
        return await self._repo.upsert(
            instrument_id=instrument_id,
            scope=scope,
            body=body,
            source=source,
        )


class DeleteInstrumentNarrative:
    def __init__(self, repo: SqlAlchemyInstrumentNarrativeRepository) -> None:
        self._repo = repo

    async def execute(self, instrument_id: str, scope: str = "estudio") -> bool:
        return await self._repo.delete(instrument_id, scope)
