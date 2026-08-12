from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.repositories.instrument_repository import (
    InstrumentWithMeta,
    SyncLogDetail,
    SyncLogSnapshot,
)
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.models import DataSyncLogRow, InstrumentRow, OhlcvBarRow
from bolsa_infrastructure.instrument_search import normalize_isin
from bolsa_market.instrument_fundamentals import parse_fundamentals_from_profile_snapshot
from bolsa_market.list_freshness import resolve_list_freshness


class SqlAlchemyInstrumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_with_meta(
        self,
        *,
        exchange: str | None = None,
        active_only: bool = True,
    ) -> list[InstrumentWithMeta]:
        stmt = select(InstrumentRow).order_by(InstrumentRow.symbol.asc())
        if exchange:
            stmt = stmt.where(InstrumentRow.exchange == exchange)
        if active_only:
            stmt = stmt.where(InstrumentRow.is_active.is_(True))

        result = await self._session.execute(stmt)
        instruments = list(result.scalars().all())
        return await self._rows_to_with_meta(instruments)

    async def search_catalog(self, query: str, *, limit: int = 12) -> list[InstrumentWithMeta]:
        normalized = query.strip()
        if not normalized:
            return []

        pattern = f"%{normalized}%"
        isin_query = normalize_isin(normalized)
        filters = [
            InstrumentRow.symbol.ilike(pattern),
            InstrumentRow.name.ilike(pattern),
            InstrumentRow.yahoo_symbol.ilike(pattern),
        ]
        if isin_query:
            filters.append(InstrumentRow.isin.ilike(f"%{isin_query}%"))

        stmt = (
            select(InstrumentRow)
            .where(
                InstrumentRow.is_active.is_(True),
                or_(*filters),
            )
            .order_by(InstrumentRow.symbol.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        instruments = list(result.scalars().all())
        return await self._rows_to_with_meta(instruments)

    async def _rows_to_with_meta(self, instruments: list[InstrumentRow]) -> list[InstrumentWithMeta]:
        """Hydrate meta with a few batched queries (not 4×N)."""
        if not instruments:
            return []

        ids = [row.id for row in instruments]
        bar_counts = await self._batch_daily_bar_counts(ids)
        last_bar_dates = await self._batch_latest_daily_bar_dates(ids)
        last_syncs = await self._batch_latest_syncs(ids)
        price_changes = await self._batch_price_changes(ids)

        items: list[InstrumentWithMeta] = []
        for instrument in instruments:
            bar_count = bar_counts.get(instrument.id, 0)
            last_sync = last_syncs.get(instrument.id)
            last_close, change_pct = price_changes.get(instrument.id, (None, None))
            last_bar_date = last_bar_dates.get(instrument.id)
            freshness, expected = resolve_list_freshness(
                bar_count=bar_count,
                last_bar_date=last_bar_date,
                last_sync_status=last_sync.status if last_sync else None,
                exchange=instrument.exchange,
                country=instrument.country,
            )
            items.append(
                InstrumentWithMeta(
                    id=instrument.id,
                    symbol=instrument.symbol,
                    yahoo_symbol=instrument.yahoo_symbol,
                    name=instrument.name,
                    exchange=instrument.exchange,
                    country=instrument.country,
                    currency=instrument.currency,
                    sector=instrument.sector,
                    isin=instrument.isin,
                    is_active=instrument.is_active,
                    bar_count=bar_count,
                    last_sync=last_sync,
                    last_close=last_close,
                    change_pct=change_pct,
                    last_bar_date=last_bar_date,
                    freshness_status=freshness,
                    expected_last_bar_date=expected,
                )
            )
        return items

    async def _row_to_with_meta(self, instrument: InstrumentRow) -> InstrumentWithMeta:
        items = await self._rows_to_with_meta([instrument])
        return items[0]

    async def get_with_meta_by_id(self, instrument_id: str) -> InstrumentWithMeta | None:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return await self._row_to_with_meta(row)

    async def get_by_yahoo_symbol(self, yahoo_symbol: str) -> Instrument | None:
        stmt = select(InstrumentRow).where(
            InstrumentRow.yahoo_symbol == yahoo_symbol,
            InstrumentRow.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return Instrument(
            id=row.id,
            symbol=row.symbol,
            yahoo_symbol=row.yahoo_symbol,
            name=row.name,
            exchange=row.exchange,
            country=row.country,
            currency=row.currency,
            sector=row.sector,
            isin=row.isin,
            is_active=row.is_active,
        )

    async def get_ids_by_yahoo_symbols(self, yahoo_symbols: list[str]) -> dict[str, str]:
        """Mapa yahoo_symbol (tal cual) → instrument_id para activos encontrados."""
        ordered: list[str] = []
        seen: set[str] = set()
        for sym in yahoo_symbols:
            s = (sym or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            ordered.append(s)
        if not ordered:
            return {}
        stmt = select(InstrumentRow.yahoo_symbol, InstrumentRow.id).where(
            InstrumentRow.yahoo_symbol.in_(ordered),
            InstrumentRow.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return {str(yahoo): str(iid) for yahoo, iid in result.all()}

    async def update_isin(self, instrument_id: str, isin: str | None) -> None:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.isin = isin
        row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def update_profile_snapshot(self, instrument_id: str, snapshot: dict[str, Any]) -> None:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.profile_snapshot = snapshot
        row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def get_profile_snapshot(self, instrument_id: str) -> dict[str, Any] | None:
        stmt = select(InstrumentRow.profile_snapshot).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_fundamentals(self, instrument_id: str) -> dict[str, Any] | None:
        snapshot = await self.get_profile_snapshot(instrument_id)
        return parse_fundamentals_from_profile_snapshot(snapshot)

    async def update_sector(self, instrument_id: str, sector: str | None) -> None:
        if not sector:
            return
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None or row.sector:
            return
        row.sector = sector
        row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def update_last_xtb_validation(self, instrument_id: str, payload: dict[str, Any]) -> None:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.last_xtb_validation = payload
        row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def get_last_xtb_validation(self, instrument_id: str) -> dict[str, Any] | None:
        stmt = select(InstrumentRow.last_xtb_validation).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        value = result.scalar_one_or_none()
        return value if isinstance(value, dict) else None

    async def get_quotes_by_ids(self, instrument_ids: list[str]) -> list[InstrumentWithMeta]:
        """Preserve input order; one batched meta hydrate for the set."""
        ordered: list[str] = []
        seen: set[str] = set()
        for instrument_id in instrument_ids:
            if not instrument_id or instrument_id in seen:
                continue
            seen.add(instrument_id)
            ordered.append(instrument_id)
        if not ordered:
            return []

        stmt = select(InstrumentRow).where(InstrumentRow.id.in_(ordered))
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        by_id = {row.id: row for row in rows}
        # Keep caller order
        ordered_rows = [by_id[iid] for iid in ordered if iid in by_id]
        return await self._rows_to_with_meta(ordered_rows)

    async def create(self, instrument: Instrument) -> Instrument:
        now = datetime.now(UTC)
        row = InstrumentRow(
            id=instrument.id,
            symbol=instrument.symbol,
            yahoo_symbol=instrument.yahoo_symbol,
            name=instrument.name,
            exchange=instrument.exchange,
            country=instrument.country,
            currency=instrument.currency,
            sector=instrument.sector,
            isin=instrument.isin,
            type="stock",
            is_active=instrument.is_active,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return instrument

    async def get_by_id(self, instrument_id: str) -> Instrument | None:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return Instrument(
            id=row.id,
            symbol=row.symbol,
            yahoo_symbol=row.yahoo_symbol,
            name=row.name,
            exchange=row.exchange,
            country=row.country,
            currency=row.currency,
            sector=row.sector,
            isin=row.isin,
            is_active=row.is_active,
        )

    async def list_existing_ids(self, instrument_ids: list[str]) -> set[str]:
        """Devuelve el subconjunto de ids que realmente existen en el catálogo.

        Permite que servicios que hacen writes con FK (p.ej. instrument_daily_opinions)
        descarten ids huérfanos/inválidos de una sola llamada en lugar de 500 por
        violación de integridad referencial.
        """
        ids = [i for i in dict.fromkeys(instrument_ids) if i]
        if not ids:
            return set()
        stmt = select(InstrumentRow.id).where(InstrumentRow.id.in_(ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {str(r) for r in rows}

    async def get_last_sync_detail(self, instrument_id: str) -> SyncLogDetail | None:
        stmt = (
            select(DataSyncLogRow)
            .where(DataSyncLogRow.instrument_id == instrument_id)
            .order_by(DataSyncLogRow.synced_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return SyncLogDetail(
            status=row.status,
            synced_at=row.synced_at.isoformat(),
            bars_added=row.bars_added,
            error=row.error,
        )

    async def _batch_daily_bar_counts(self, instrument_ids: list[str]) -> dict[str, int]:
        stmt = (
            select(OhlcvBarRow.instrument_id, func.count())
            .where(
                OhlcvBarRow.instrument_id.in_(instrument_ids),
                OhlcvBarRow.timeframe == TimeFrame.D1,
            )
            .group_by(OhlcvBarRow.instrument_id)
        )
        result = await self._session.execute(stmt)
        return {str(iid): int(count) for iid, count in result.all()}

    async def _batch_latest_daily_bar_dates(self, instrument_ids: list[str]) -> dict[str, str]:
        stmt = (
            select(OhlcvBarRow.instrument_id, func.max(OhlcvBarRow.timestamp))
            .where(
                OhlcvBarRow.instrument_id.in_(instrument_ids),
                OhlcvBarRow.timeframe == TimeFrame.D1,
            )
            .group_by(OhlcvBarRow.instrument_id)
        )
        result = await self._session.execute(stmt)
        out: dict[str, str] = {}
        for iid, value in result.all():
            if value is None:
                continue
            out[str(iid)] = value.date().isoformat() if hasattr(value, "date") else str(value)[:10]
        return out

    async def _batch_latest_syncs(self, instrument_ids: list[str]) -> dict[str, SyncLogSnapshot]:
        # DISTINCT ON (Postgres) — latest sync per instrument.
        stmt = (
            select(DataSyncLogRow)
            .where(DataSyncLogRow.instrument_id.in_(instrument_ids))
            .distinct(DataSyncLogRow.instrument_id)
            .order_by(DataSyncLogRow.instrument_id, DataSyncLogRow.synced_at.desc())
        )
        result = await self._session.execute(stmt)
        out: dict[str, SyncLogSnapshot] = {}
        for row in result.scalars().all():
            out[row.instrument_id] = SyncLogSnapshot(
                status=row.status,
                synced_at=row.synced_at.isoformat(),
                error=row.error,
            )
        return out

    async def _batch_price_changes(
        self, instrument_ids: list[str]
    ) -> dict[str, tuple[float | None, float | None]]:
        rn = (
            func.row_number()
            .over(
                partition_by=OhlcvBarRow.instrument_id,
                order_by=OhlcvBarRow.timestamp.desc(),
            )
            .label("rn")
        )
        ranked = (
            select(
                OhlcvBarRow.instrument_id.label("instrument_id"),
                OhlcvBarRow.close.label("close"),
                rn,
            )
            .where(
                OhlcvBarRow.instrument_id.in_(instrument_ids),
                OhlcvBarRow.timeframe == TimeFrame.D1,
            )
            .subquery()
        )
        stmt = (
            select(ranked.c.instrument_id, ranked.c.close, ranked.c.rn)
            .where(ranked.c.rn <= 2)
            .order_by(ranked.c.instrument_id, ranked.c.rn)
        )
        result = await self._session.execute(stmt)
        closes_by_id: dict[str, list[float]] = {}
        for iid, close, _rn in result.all():
            key = str(iid)
            value = float(close) if isinstance(close, (int, float, Decimal)) else float(close)
            closes_by_id.setdefault(key, []).append(value)

        out: dict[str, tuple[float | None, float | None]] = {}
        for iid, closes in closes_by_id.items():
            if not closes:
                out[iid] = (None, None)
                continue
            last_close = closes[0]
            if len(closes) < 2 or closes[1] == 0:
                out[iid] = (last_close, None)
            else:
                out[iid] = (last_close, ((last_close - closes[1]) / closes[1]) * 100)
        return out

    async def _count_daily_bars(self, instrument_id: str) -> int:
        counts = await self._batch_daily_bar_counts([instrument_id])
        return counts.get(instrument_id, 0)

    async def _latest_daily_bar_date(self, instrument_id: str) -> str | None:
        dates = await self._batch_latest_daily_bar_dates([instrument_id])
        return dates.get(instrument_id)

    async def _latest_sync(self, instrument_id: str) -> SyncLogSnapshot | None:
        syncs = await self._batch_latest_syncs([instrument_id])
        return syncs.get(instrument_id)

    async def _price_change(self, instrument_id: str) -> tuple[float | None, float | None]:
        changes = await self._batch_price_changes([instrument_id])
        return changes.get(instrument_id, (None, None))

    async def get_latest_close(self, instrument_id: str) -> float | None:
        close, _ = await self._price_change(instrument_id)
        return close
