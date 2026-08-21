"""Use-case: perfil / snapshot de instrumento."""

from typing import Any

from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)


class GetInstrumentProfile:
    """Obtiene Instrument Profile."""
    def __init__(self, repository: SqlAlchemyInstrumentRepository) -> None:
        self._repository = repository

    async def execute(self, instrument_id: str) -> dict[str, Any] | None:
        return await self._repository.get_profile_snapshot(instrument_id)
