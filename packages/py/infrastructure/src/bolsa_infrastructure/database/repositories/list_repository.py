from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bolsa_infrastructure.database.models import (
    InstrumentListItemRow,
    InstrumentListRow,
    InstrumentRow,
)
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.ids import new_id


def derive_list_kind(source: str) -> str:

    return "linked_universe" if source == "catalog" else "personal"

@dataclass(frozen=True, slots=True)

class InstrumentListSummary:

    id: str

    name: str

    source: str

    item_count: int

    updated_at: str

    kind: str | None = None

    universe_code: str | None = None

    last_synced_at: str | None = None

    content_hash: str | None = None

@dataclass(frozen=True, slots=True)

class InstrumentListDetail:

    id: str

    name: str

    source: str

    instrument_ids: list[str]

    updated_at: str

    kind: str | None = None

    universe_code: str | None = None

    last_synced_at: str | None = None

    content_hash: str | None = None

    membership_changelog: dict[str, Any] | None = None

class SqlAlchemyListRepository:

    IBEX_LIST_NAME = "IBEX 35"

    CATALOG_IBEX_LIST_ID = "ibex35"

    def __init__(self, session: AsyncSession) -> None:

        self._session = session

    def _summary(self, row: InstrumentListRow, item_count: int) -> InstrumentListSummary:

        return InstrumentListSummary(

            id=row.id,

            name=row.name,

            source=row.source,

            item_count=int(item_count or 0),

            updated_at=row.updated_at.isoformat(),

            kind=row.kind or derive_list_kind(row.source),

            universe_code=row.universe_code,

            last_synced_at=row.last_synced_at.isoformat() if row.last_synced_at else None,

            content_hash=row.content_hash,

        )

    def _detail(self, row: InstrumentListRow, instrument_ids: list[str]) -> InstrumentListDetail:

        return InstrumentListDetail(

            id=row.id,

            name=row.name,

            source=row.source,

            instrument_ids=instrument_ids,

            updated_at=row.updated_at.isoformat(),

            kind=row.kind or derive_list_kind(row.source),

            universe_code=row.universe_code,

            last_synced_at=row.last_synced_at.isoformat() if row.last_synced_at else None,

            content_hash=row.content_hash,

            membership_changelog=row.membership_changelog,

        )

    async def list_all(self) -> list[InstrumentListSummary]:

        stmt = (

            select(

                InstrumentListRow,

                func.count(InstrumentListItemRow.id).label("item_count"),

            )

            .outerjoin(InstrumentListItemRow, InstrumentListItemRow.list_id == InstrumentListRow.id)

            .group_by(InstrumentListRow.id)

            .order_by(InstrumentListRow.name.asc())

        )

        result = await self._session.execute(stmt)

        return [self._summary(row, item_count) for row, item_count in result.all()]

    async def get_by_id(self, list_id: str) -> InstrumentListDetail | None:

        stmt = (

            select(InstrumentListRow)

            .where(InstrumentListRow.id == list_id)

            .options(selectinload(InstrumentListRow.items))

        )

        result = await self._session.execute(stmt)

        row = result.scalar_one_or_none()

        if row is None:

            return None

        instrument_ids = [item.instrument_id for item in sorted(row.items, key=lambda i: i.sort_order)]

        return self._detail(row, instrument_ids)

    async def create(

        self,

        *,

        name: str,

        source: str,

        instrument_ids: list[str],

        list_id: str | None = None,

        kind: str | None = None,

        universe_code: str | None = None,

        last_synced_at: datetime | None = None,

        content_hash: str | None = None,

        membership_changelog: dict[str, Any] | None = None,

    ) -> InstrumentListDetail:

        now = datetime.now(UTC)

        row_id = list_id or new_id()

        row = InstrumentListRow(

            id=row_id,

            name=name,

            source=source,

            kind=kind or derive_list_kind(source),

            universe_code=universe_code,

            last_synced_at=last_synced_at,

            content_hash=content_hash,

            membership_changelog=membership_changelog,

            created_at=now,

            updated_at=now,

        )

        self._session.add(row)

        await self._replace_items(row_id, instrument_ids)

        await self._session.flush()

        detail = await self.get_by_id(row_id)

        assert detail is not None

        return detail

    async def update(

        self,

        list_id: str,

        *,

        name: str | None = None,

        instrument_ids: list[str] | None = None,

    ) -> InstrumentListDetail | None:

        stmt = select(InstrumentListRow).where(InstrumentListRow.id == list_id)

        result = await self._session.execute(stmt)

        row = result.scalar_one_or_none()

        if row is None:

            return None

        if row.source == "catalog" and instrument_ids is not None:

            raise ValueError("No se puede modificar los instrumentos de una lista de catálogo")

        if name is not None:

            row.name = name

        row.updated_at = datetime.now(UTC)

        if instrument_ids is not None:

            await self._replace_items(list_id, instrument_ids)

        await self._session.flush()

        return await self.get_by_id(list_id)

    async def mark_universe_sync(

        self,

        list_id: str,

        *,

        universe_code: str,

        content_hash: str,

        membership_changelog: dict[str, Any],

        last_synced_at: datetime | None = None,

    ) -> InstrumentListDetail | None:

        """Persiste metadatos L2 tras sync de índice."""

        stmt = select(InstrumentListRow).where(InstrumentListRow.id == list_id)

        result = await self._session.execute(stmt)

        row = result.scalar_one_or_none()

        if row is None:

            return None

        now = last_synced_at or datetime.now(UTC)

        row.kind = "linked_universe"

        row.source = "catalog"

        row.universe_code = universe_code

        row.content_hash = content_hash

        row.membership_changelog = membership_changelog

        row.last_synced_at = now

        row.updated_at = now

        await self._session.flush()

        return await self.get_by_id(list_id)

    async def delete(self, list_id: str) -> bool:

        """Elimina lista personal o desuscribe índice (catalog)."""

        detail = await self.get_by_id(list_id)

        if detail is None:

            return False

        stmt = delete(InstrumentListRow).where(InstrumentListRow.id == list_id)

        result = await self._session.execute(stmt)

        return result.rowcount > 0

    async def sync_ibex_catalog_list_if_present(self) -> InstrumentListDetail | None:

        """Si IBEX ya está suscrito, re-sincroniza constitutivos. No lo recrea."""

        existing = await self.get_by_id(self.CATALOG_IBEX_LIST_ID)

        if existing is None:

            stmt = select(InstrumentListRow).where(

                InstrumentListRow.source == "catalog",

                InstrumentListRow.name == self.IBEX_LIST_NAME,

            )

            result = await self._session.execute(stmt)

            row = result.scalar_one_or_none()

            if row is None:

                return None

        return await self.ensure_ibex_catalog_list()

    async def ensure_ibex_catalog_list(self) -> InstrumentListDetail:

        """Lista catálogo IBEX 35 = constitutivos curados (no todos los BME)."""

        from bolsa_market.indices.curated_ibex35 import IBEX35_CURATED

        yahoo_symbols = [yahoo for _, yahoo, _ in IBEX35_CURATED]

        instrument_repo = SqlAlchemyInstrumentRepository(self._session)

        by_yahoo = await instrument_repo.get_ids_by_yahoo_symbols(yahoo_symbols)

        instrument_ids = [

            by_yahoo[yahoo]

            for yahoo in yahoo_symbols

            if yahoo in by_yahoo

        ]

        existing = await self.get_by_id(self.CATALOG_IBEX_LIST_ID)

        if existing is None:

            stmt = select(InstrumentListRow).where(

                InstrumentListRow.source == "catalog",

                InstrumentListRow.name == self.IBEX_LIST_NAME,

            )

            result = await self._session.execute(stmt)

            row = result.scalar_one_or_none()

            if row is not None:

                existing = await self.get_by_id(row.id)

        if existing is None:

            return await self.create(

                name=self.IBEX_LIST_NAME,

                source="catalog",

                instrument_ids=instrument_ids,

                list_id=self.CATALOG_IBEX_LIST_ID,

                kind="linked_universe",

                universe_code="IBEX35",

            )

        if existing.instrument_ids != instrument_ids:

            await self.replace_catalog_membership(existing.id, instrument_ids)

            detail = await self.get_by_id(existing.id)

            assert detail is not None

            return detail

        return existing

    async def replace_catalog_membership(

        self,

        list_id: str,

        instrument_ids: list[str],

    ) -> InstrumentListDetail | None:

        """Actualiza miembros de una lista catalog (sync de índice; bypass lock de update)."""

        stmt = select(InstrumentListRow).where(InstrumentListRow.id == list_id)

        result = await self._session.execute(stmt)

        row = result.scalar_one_or_none()

        if row is None:

            return None

        if row.source != "catalog":

            raise ValueError("replace_catalog_membership solo aplica a source=catalog")

        row.updated_at = datetime.now(UTC)

        await self._replace_items(list_id, instrument_ids)

        await self._session.flush()

        return await self.get_by_id(list_id)

    async def get_quotes_for_list(self, list_id: str) -> list[InstrumentWithMeta] | None:

        detail = await self.get_by_id(list_id)

        if detail is None:

            return None

        if not detail.instrument_ids:

            return []

        instrument_repo = SqlAlchemyInstrumentRepository(self._session)

        return await instrument_repo.get_quotes_by_ids(detail.instrument_ids)

    async def _replace_items(self, list_id: str, instrument_ids: list[str]) -> None:

        await self._session.execute(

            delete(InstrumentListItemRow).where(InstrumentListItemRow.list_id == list_id),

        )

        unique_ids: list[str] = []

        seen: set[str] = set()

        for instrument_id in instrument_ids:

            if instrument_id in seen:

                continue

            seen.add(instrument_id)

            unique_ids.append(instrument_id)

        if unique_ids:

            stmt = select(InstrumentRow.id).where(InstrumentRow.id.in_(unique_ids))

            result = await self._session.execute(stmt)

            valid_ids = {row[0] for row in result.all()}

            unique_ids = [iid for iid in unique_ids if iid in valid_ids]

        for index, instrument_id in enumerate(unique_ids):

            self._session.add(

                InstrumentListItemRow(

                    id=new_id(),

                    list_id=list_id,

                    instrument_id=instrument_id,

                    sort_order=index,

                ),

            )

