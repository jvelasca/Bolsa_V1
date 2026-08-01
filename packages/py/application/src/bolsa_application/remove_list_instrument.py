"""Quitar instrumento de lista y purga opcional de BD."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from bolsa_application.instrument_lifecycle import (
    GetInstrumentRemovalPreview,
    InstrumentRemovalPreview,
)
from bolsa_infrastructure.database.models import InstrumentListItemRow, InstrumentRow, OhlcvBarRow
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository


@dataclass(frozen=True, slots=True)
class RemoveFromListResult:
    list_id: str
    instrument_id: str
    removed_from_list: bool
    became_orphan: bool
    purged: bool
    purge_skipped_reasons: tuple[str, ...]
    preview: InstrumentRemovalPreview | None


class DeleteInstrument:
    """Borra el instrumento de BD (cascade en FKs PostgreSQL).

    Usa DELETE SQL (no ``session.delete`` ORM): sin cascade ORM, SQLAlchemy
    emite ``UPDATE … SET instrument_id=NULL`` en hijos NOT NULL (p. ej. data_sync_log)
    y provoca IntegrityError.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._preview = GetInstrumentRemovalPreview(session)

    async def execute(self, instrument_id: str, *, force: bool = False) -> None:
        preview = await self._preview.execute(instrument_id)
        if preview is None:
            raise ValueError("Instrumento no encontrado")
        if preview.remaining_list_count > 0 and not force:
            raise ValueError(
                "El instrumento aún pertenece a listas. Quítalo de todas las listas o usa force."
            )
        if not force and (preview.positions > 0 or preview.pending_orders > 0):
            raise ValueError("; ".join(preview.purge_blocked_reasons) or "Purge bloqueado")

        result = await self._session.execute(
            delete(InstrumentRow).where(InstrumentRow.id == instrument_id),
        )
        if result.rowcount == 0:
            raise ValueError("Instrumento no encontrado")
        await self._session.flush()


class RemoveInstrumentFromList:
    """Quita el instrumento de una lista; opcionalmente purga BD si queda huérfano."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._lists = SqlAlchemyListRepository(session)
        self._preview = GetInstrumentRemovalPreview(session)

    async def execute(
        self,
        list_id: str,
        instrument_id: str,
        *,
        purge_if_orphan: bool = False,
    ) -> RemoveFromListResult:
        detail = await self._lists.get_by_id(list_id)
        if detail is None:
            raise ValueError("Lista no encontrada")
        if detail.source == "catalog":
            raise ValueError("No se puede modificar los instrumentos de una lista de catálogo")
        if instrument_id not in detail.instrument_ids:
            preview = await self._preview.execute(instrument_id, excluding_list_id=list_id)
            return RemoveFromListResult(
                list_id=list_id,
                instrument_id=instrument_id,
                removed_from_list=False,
                became_orphan=False,
                purged=False,
                purge_skipped_reasons=("El valor no estaba en esta lista.",),
                preview=preview,
            )

        preview_before = await self._preview.execute(instrument_id, excluding_list_id=list_id)
        next_ids = [iid for iid in detail.instrument_ids if iid != instrument_id]
        await self._lists.update(list_id, instrument_ids=next_ids)

        became_orphan = preview_before is not None and preview_before.would_be_orphan
        purged = False
        skipped: list[str] = []

        if purge_if_orphan and became_orphan:
            if preview_before and not preview_before.can_purge:
                skipped.extend(preview_before.purge_blocked_reasons)
            else:
                await DeleteInstrument(self._session).execute(instrument_id)
                purged = True
        elif purge_if_orphan and not became_orphan:
            skipped.append("El valor sigue en otras listas; no se purga de BD.")

        preview_after = None if purged else await self._preview.execute(instrument_id)

        return RemoveFromListResult(
            list_id=list_id,
            instrument_id=instrument_id,
            removed_from_list=True,
            became_orphan=became_orphan and not purged,
            purged=purged,
            purge_skipped_reasons=tuple(skipped),
            preview=preview_after or preview_before,
        )


@dataclass(frozen=True, slots=True)
class OrphanInstrumentRow:
    id: str
    symbol: str
    name: str
    ohlcv_bar_count: int


@dataclass(frozen=True, slots=True)
class ListOrphanInstrumentsResult:
    orphans: tuple[OrphanInstrumentRow, ...]
    total_ohlcv_bars: int


class ListOrphanInstruments:
    """Instrumentos sin ninguna membresía de lista (candidatos a purge)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, *, limit: int = 100) -> ListOrphanInstrumentsResult:
        member = aliased(InstrumentListItemRow)
        bar_count = (
            select(func.count(OhlcvBarRow.id))
            .where(OhlcvBarRow.instrument_id == InstrumentRow.id)
            .correlate(InstrumentRow)
            .scalar_subquery()
        )
        stmt = (
            select(InstrumentRow.id, InstrumentRow.symbol, InstrumentRow.name, bar_count)
            .outerjoin(member, member.instrument_id == InstrumentRow.id)
            .where(member.id.is_(None))
            .order_by(InstrumentRow.symbol.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        orphans = [
            OrphanInstrumentRow(
                id=row[0],
                symbol=row[1],
                name=row[2],
                ohlcv_bar_count=int(row[3] or 0),
            )
            for row in result.all()
        ]
        return ListOrphanInstrumentsResult(
            orphans=tuple(orphans),
            total_ohlcv_bars=sum(o.ohlcv_bar_count for o in orphans),
        )


class PurgeOrphanInstruments:
    """Purga en lote instrumentos huérfanos (sin listas), respetando bloqueos."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._preview = GetInstrumentRemovalPreview(session)

    async def execute(self, *, limit: int = 50) -> dict[str, object]:
        listed = await ListOrphanInstruments(self._session).execute(limit=limit)
        purged: list[str] = []
        skipped: list[dict[str, object]] = []
        for orphan in listed.orphans:
            preview = await self._preview.execute(orphan.id)
            if preview is None:
                continue
            if not preview.can_purge:
                skipped.append(
                    {
                        "instrumentId": orphan.id,
                        "symbol": orphan.symbol,
                        "reasons": list(preview.purge_blocked_reasons),
                    }
                )
                continue
            await DeleteInstrument(self._session).execute(orphan.id)
            purged.append(orphan.id)
        return {"purgedIds": purged, "skipped": skipped, "scanned": len(listed.orphans)}
