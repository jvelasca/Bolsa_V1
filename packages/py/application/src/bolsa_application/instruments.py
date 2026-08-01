from bolsa_domain.repositories.instrument_repository import InstrumentRepository, InstrumentWithMeta


class ListInstrumentsWithMeta:
    """Caso de uso: listar instrumentos IBEX con metadatos de sync y precio."""

    def __init__(self, repository: InstrumentRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        exchange: str | None = "BME",
        active_only: bool = True,
    ) -> list[InstrumentWithMeta]:
        return await self._repository.list_with_meta(
            exchange=exchange,
            active_only=active_only,
        )
