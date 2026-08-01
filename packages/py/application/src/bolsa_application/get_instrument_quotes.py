from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta
from bolsa_infrastructure.database.repositories.instrument_repository import SqlAlchemyInstrumentRepository


class GetInstrumentQuotes:
    """Metadatos de cotización (último, %, barras) para una lista de IDs."""

    def __init__(self, repository: SqlAlchemyInstrumentRepository) -> None:
        self._repository = repository

    async def execute(self, instrument_ids: list[str]) -> list[InstrumentWithMeta]:
        return await self._repository.get_quotes_by_ids(instrument_ids)
