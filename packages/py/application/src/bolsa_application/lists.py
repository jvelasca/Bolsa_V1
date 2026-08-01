from bolsa_application.market_indices import SyncSubscribedCatalogIndices

from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository





class ListInstrumentLists:

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

        return await self._list_repo.list_all()





class GetInstrumentList:

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:

        self._list_repo = list_repo



    async def execute(self, list_id: str):

        return await self._list_repo.get_by_id(list_id)





class CreateInstrumentList:
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
        if not name.strip():
            raise ValueError("List name is required")
        return await self._list_repo.create(
            name=name.strip(),
            source=source or "custom",
            instrument_ids=instrument_ids or [],
            kind=kind,
        )


class UpdateInstrumentList:

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:

        self._list_repo = list_repo



    async def execute(

        self,

        list_id: str,

        *,

        name: str | None = None,

        instrument_ids: list[str] | None = None,

    ):

        updated = await self._list_repo.update(list_id, name=name, instrument_ids=instrument_ids)

        if updated is None:

            raise ValueError("List not found")

        return updated





class DeleteInstrumentList:

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:

        self._list_repo = list_repo



    async def execute(self, list_id: str) -> None:

        deleted = await self._list_repo.delete(list_id)

        if not deleted:

            raise ValueError("List not found")





class GetListQuotes:

    def __init__(self, list_repo: SqlAlchemyListRepository) -> None:

        self._list_repo = list_repo



    async def execute(self, list_id: str):

        quotes = await self._list_repo.get_quotes_for_list(list_id)

        if quotes is None:

            raise ValueError("List not found")

        return quotes


