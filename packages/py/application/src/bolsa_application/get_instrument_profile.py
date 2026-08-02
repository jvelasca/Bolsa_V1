from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)


class GetInstrumentProfile:
    def __init__(self, repository: SqlAlchemyInstrumentRepository) -> None:
        self._repository = repository

    async def execute(self, instrument_id: str) -> dict | None:
        return await self._repository.get_profile_snapshot(instrument_id)
