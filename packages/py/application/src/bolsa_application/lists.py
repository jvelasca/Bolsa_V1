"""Use-cases de listas / universos."""

from bolsa_application.market_indices import SyncSubscribedCatalogIndices
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository

# Reservado salvo la lista canónica ADR-024 (id = estudio).
_RESERVED_ESTUDIO_NAMES = frozenset({"estudio", "en estudio"})


def _assert_list_name_allowed(name: str, *, list_id: str | None = None) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("List name is required")
    if cleaned.casefold() in _RESERVED_ESTUDIO_NAMES:
        if list_id == SqlAlchemyListRepository.ESTUDIO_LIST_ID:
            return SqlAlchemyListRepository.ESTUDIO_LIST_NAME
        raise ValueError(
            "El nombre «Estudio» está reservado para la lista canónica de supervisión. "
            "Añade valores a «Estudio» desde Listas; no crees otra con ese nombre."
        )
    return cleaned


class ListInstrumentLists:
    """Lista Instrument Lists."""

    def __init__(
        self,
        list_repo: SqlAlchemyListRepository,
        sync_indices: SyncSubscribedCatalogIndices | None = None,
    ) -> None:
        self._list_repo = list_repo
        self._sync_indices = sync_indices

    async def execute(self) -> list:
        # Índices suscritos: import faltantes + membresía exacta (join/leave; no borra Instrument).
        if self._sync_indices is not None:
            await self._sync_indices.execute(sync_bars=False)
        else:
            await self._list_repo.sync_ibex_catalog_list_if_present()

        # ADR-024: universo supervisable canónico (fusiona «Estudio personal» legacy).
        await self._list_repo.ensure_estudio_list()

        return await self._list_repo.list_all()


class GetInstrumentList:
    """Obtiene Instrument List."""

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:
        self._list_repo = list_repo

    async def execute(self, list_id: str):
        if list_id == SqlAlchemyListRepository.ESTUDIO_LIST_ID:
            await self._list_repo.ensure_estudio_list()
        return await self._list_repo.get_by_id(list_id)


class CreateInstrumentList:
    """Crea Instrument List."""

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:
        self._list_repo = list_repo

    async def execute(
        self,
        *,
        name: str,
        instrument_ids: list[str] | None = None,
        source: str | None = "custom",
        kind: str | None = None,
    ):
        cleaned = _assert_list_name_allowed(name)
        return await self._list_repo.create(
            name=cleaned,
            source=source or "custom",
            instrument_ids=instrument_ids or [],
            kind=kind,
        )


class UpdateInstrumentList:
    """Actualiza Instrument List."""

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:
        self._list_repo = list_repo

    async def execute(
        self,
        list_id: str,
        *,
        name: str | None = None,
        instrument_ids: list[str] | None = None,
    ):
        cleaned_name = (
            _assert_list_name_allowed(name, list_id=list_id) if name is not None else None
        )

        updated = await self._list_repo.update(
            list_id, name=cleaned_name, instrument_ids=instrument_ids
        )

        if updated is None:
            raise ValueError("List not found")

        return updated


class DeleteInstrumentList:
    """Elimina Instrument List."""

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:
        self._list_repo = list_repo

    async def execute(self, list_id: str) -> None:
        if list_id == SqlAlchemyListRepository.ESTUDIO_LIST_ID:
            raise ValueError(
                "La lista «Estudio» es canónica de supervisión y no se puede eliminar."
            )
        deleted = await self._list_repo.delete(list_id)

        if not deleted:
            raise ValueError("List not found")


class GetListQuotes:
    """Obtiene List Quotes."""

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:
        self._list_repo = list_repo

    async def execute(self, list_id: str):
        quotes = await self._list_repo.get_quotes_for_list(list_id)

        if quotes is None:
            raise ValueError("List not found")

        return quotes
