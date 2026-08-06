"""Use-cases de catálogo de instrumentos."""

from bolsa_domain.repositories.instrument_repository import InstrumentRepository, InstrumentWithMeta


class ListInstrumentsWithMeta:
    """Caso de uso: listar instrumentos del catálogo con metadatos de sync y precio.

    Por defecto incluye todos los exchanges (IBEX, S&P 100, etc.). Filtrar por
    ``exchange`` solo cuando el caller lo pida explícitamente.
    """

    def __init__(self, repository: InstrumentRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        exchange: str | None = None,
        active_only: bool = True,
    ) -> list[InstrumentWithMeta]:
        return await self._repository.list_with_meta(
            exchange=exchange,
            active_only=active_only,
        )
