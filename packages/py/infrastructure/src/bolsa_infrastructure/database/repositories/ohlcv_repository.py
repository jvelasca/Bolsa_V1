from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.ohlcv_time import format_bar_timestamp, parse_bar_timestamp
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.models import OhlcvBarRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyOhlcvRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
        limit: int | None = 365,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[OhlcvBar]:
        filters = [
            OhlcvBarRow.instrument_id == instrument_id,
            OhlcvBarRow.timeframe == timeframe,
        ]
        if date_from:
            start = date.fromisoformat(date_from[:10])
            filters.append(OhlcvBarRow.timestamp >= datetime(start.year, start.month, start.day, tzinfo=UTC))
        if date_to:
            end = date.fromisoformat(date_to[:10])
            end_exclusive = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(
                days=1
            )
            filters.append(OhlcvBarRow.timestamp < end_exclusive)

        stmt = select(OhlcvBarRow).where(*filters).order_by(OhlcvBarRow.timestamp.desc())
        resolved_limit = 10_000 if limit is None else max(1, min(int(limit), 10_000))
        stmt = stmt.limit(resolved_limit)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()

        return [
            OhlcvBar(
                timestamp=format_bar_timestamp(row.timestamp, timeframe),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=int(row.volume),
                adj_close=float(row.adj_close) if row.adj_close is not None else None,
                source=row.source,  # type: ignore[arg-type]
            )
            for row in rows
        ]

    async def count_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(OhlcvBarRow)
            .where(
                OhlcvBarRow.instrument_id == instrument_id,
                OhlcvBarRow.timeframe == timeframe,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_latest_bar_date(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> str | None:
        stmt = (
            select(OhlcvBarRow.timestamp)
            .where(
                OhlcvBarRow.instrument_id == instrument_id,
                OhlcvBarRow.timeframe == timeframe,
            )
            .order_by(OhlcvBarRow.timestamp.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return format_bar_timestamp(row, timeframe)

    async def get_earliest_bar_date(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> str | None:
        stmt = (
            select(OhlcvBarRow.timestamp)
            .where(
                OhlcvBarRow.instrument_id == instrument_id,
                OhlcvBarRow.timeframe == timeframe,
            )
            .order_by(OhlcvBarRow.timestamp.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return format_bar_timestamp(row, timeframe)

    async def get_daily_bars_by_dates(
        self,
        instrument_id: str,
        date_keys: list[str],
    ) -> dict[str, OhlcvBar]:
        if not date_keys:
            return {}

        from sqlalchemy import Date, cast

        unique_keys = sorted({key[:10] for key in date_keys})
        stmt = (
            select(OhlcvBarRow)
            .where(
                OhlcvBarRow.instrument_id == instrument_id,
                OhlcvBarRow.timeframe == TimeFrame.D1,
                cast(OhlcvBarRow.timestamp, Date).in_(
                    [date.fromisoformat(key) for key in unique_keys],
                ),
            )
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        mapped: dict[str, OhlcvBar] = {}
        for row in rows:
            key = row.timestamp.date().isoformat()
            mapped[key] = OhlcvBar(
                timestamp=format_bar_timestamp(row.timestamp, TimeFrame.D1),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=int(row.volume),
                adj_close=float(row.adj_close) if row.adj_close is not None else None,
                source=row.source,  # type: ignore[arg-type]
            )
        return mapped

    async def upsert_daily_bars(self, instrument_id: str, bars: list[OhlcvBar]) -> int:
        return await self.upsert_bars(instrument_id, TimeFrame.D1, bars)

    async def upsert_bars(
        self,
        instrument_id: str,
        timeframe: TimeFrame,
        bars: list[OhlcvBar],
    ) -> int:
        if not bars:
            return 0

        now = datetime.now(UTC)
        rows = [
            {
                "id": new_id(),
                "instrument_id": instrument_id,
                "timeframe": timeframe,
                "timestamp": parse_bar_timestamp(bar.timestamp),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "adj_close": bar.adj_close,
                "source": bar.source,
                "created_at": now,
            }
            for bar in bars
        ]
        stmt = insert(OhlcvBarRow).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_id", "timeframe", "timestamp"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "adj_close": stmt.excluded.adj_close,
                "source": stmt.excluded.source,
            },
        )
        # P2.3: un solo INSERT multi-fila ON CONFLICT DO UPDATE (bulk) en vez del
        # loop 1×1 previo (N+1). `excluded` se resuelve a nivel de BD.
        await self._session.execute(stmt)
        await self._session.flush()
        return len(bars)
