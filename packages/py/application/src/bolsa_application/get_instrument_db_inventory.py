"""Inventario de datos persistidos en BD para un instrumento."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_infrastructure.database.models import (
    BacktestRunRow,
    DataSyncLogRow,
    InstrumentListItemRow,
    InstrumentRow,
    LedgerEntryRow,
    OhlcvBarRow,
    PendingOrderRow,
    PositionRow,
    PriceAlertRow,
    TransactionRow,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class OhlcvLayerInventory:
    """Use-case / tipo: Ohlcv Layer Inventory."""
    timeframe: str
    source: str
    bar_count: int
    first_date: str | None
    last_date: str | None


@dataclass(frozen=True, slots=True)
class SyncLogInventoryEntry:
    """Sincroniza Log Inventory Entry."""
    provider: str
    status: str
    bars_added: int
    synced_at: str
    error: str | None


@dataclass(frozen=True, slots=True)
class AppDataInventory:
    """Use-case / tipo: App Data Inventory."""
    positions: int
    transactions: int
    backtest_runs: int
    list_memberships: int
    price_alerts: int
    pending_orders: int
    ledger_entries: int


@dataclass(frozen=True, slots=True)
class InstrumentRecordInventory:
    """Use-case / tipo: Instrument Record Inventory."""
    id: str
    symbol: str
    yahoo_symbol: str
    name: str
    exchange: str
    country: str
    currency: str
    sector: str | None
    isin: str | None
    is_active: bool
    created_at: str
    updated_at: str
    profile_fetched_at: str | None
    last_xtb_validation: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class InstrumentDbInventory:
    """Use-case / tipo: Instrument Db Inventory."""
    instrument: InstrumentRecordInventory
    ohlcv_layers: tuple[OhlcvLayerInventory, ...]
    recent_sync_logs: tuple[SyncLogInventoryEntry, ...]
    app_data: AppDataInventory
    derived_data_notes: tuple[str, ...]


DERIVED_DATA_NOTES: tuple[str, ...] = (
    "Indicadores técnicos (SMA, EMA, RSI): calculados al vuelo desde ohlcv_bars, no se guardan.",
    "Price summary (último, % día, rango): derivado de las velas diarias en BD.",
    "Calidad/frescura (data-status): evaluada en cada consulta; no se persiste salvo sync_log.",
    "Cotización XTB en vivo: efímera vía bridge HTTP; no se escribe en ohlcv_bars hoy.",
    "Gráficos, estudios y workspaces: configuración en workspace JSON, no duplican OHLCV.",
)


class GetInstrumentDbInventory:
    """Obtiene Instrument Db Inventory."""
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, instrument_id: str) -> InstrumentDbInventory | None:
        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        profile_fetched_at: str | None = None
        if isinstance(row.profile_snapshot, dict):
            fetched = row.profile_snapshot.get("fetchedAt")
            if isinstance(fetched, str):
                profile_fetched_at = fetched

        last_xtb_validation = row.last_xtb_validation if isinstance(row.last_xtb_validation, dict) else None

        ohlcv_layers = await self._ohlcv_layers(instrument_id)
        recent_sync_logs = await self._recent_sync_logs(instrument_id)
        app_data = await self._app_data_counts(instrument_id)

        instrument = InstrumentRecordInventory(
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
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            profile_fetched_at=profile_fetched_at,
            last_xtb_validation=last_xtb_validation,
        )

        return InstrumentDbInventory(
            instrument=instrument,
            ohlcv_layers=tuple(ohlcv_layers),
            recent_sync_logs=tuple(recent_sync_logs),
            app_data=app_data,
            derived_data_notes=DERIVED_DATA_NOTES,
        )

    async def _ohlcv_layers(self, instrument_id: str) -> list[OhlcvLayerInventory]:
        stmt = (
            select(
                OhlcvBarRow.timeframe,
                OhlcvBarRow.source,
                func.count(),
                func.min(OhlcvBarRow.timestamp),
                func.max(OhlcvBarRow.timestamp),
            )
            .where(OhlcvBarRow.instrument_id == instrument_id)
            .group_by(OhlcvBarRow.timeframe, OhlcvBarRow.source)
            .order_by(OhlcvBarRow.timeframe.asc(), OhlcvBarRow.source.asc())
        )
        result = await self._session.execute(stmt)
        layers: list[OhlcvLayerInventory] = []
        for timeframe, source, count, first_ts, last_ts in result.all():
            layers.append(
                OhlcvLayerInventory(
                    timeframe=str(timeframe),
                    source=str(source),
                    bar_count=int(count),
                    first_date=first_ts.date().isoformat() if first_ts else None,
                    last_date=last_ts.date().isoformat() if last_ts else None,
                ),
            )
        return layers

    async def _recent_sync_logs(self, instrument_id: str) -> list[SyncLogInventoryEntry]:
        stmt = (
            select(DataSyncLogRow)
            .where(DataSyncLogRow.instrument_id == instrument_id)
            .order_by(DataSyncLogRow.synced_at.desc())
            .limit(8)
        )
        result = await self._session.execute(stmt)
        return [
            SyncLogInventoryEntry(
                provider=row.provider,
                status=row.status,
                bars_added=row.bars_added,
                synced_at=row.synced_at.isoformat(),
                error=row.error,
            )
            for row in result.scalars().all()
        ]

    async def _app_data_counts(self, instrument_id: str) -> AppDataInventory:
        async def count(model: type[Any], column: Any) -> int:
            stmt = select(func.count()).select_from(model).where(column == instrument_id)
            result = await self._session.execute(stmt)
            return int(result.scalar_one())

        return AppDataInventory(
            positions=await count(PositionRow, PositionRow.instrument_id),
            transactions=await count(TransactionRow, TransactionRow.instrument_id),
            backtest_runs=await count(BacktestRunRow, BacktestRunRow.instrument_id),
            list_memberships=await count(InstrumentListItemRow, InstrumentListItemRow.instrument_id),
            price_alerts=await count(PriceAlertRow, PriceAlertRow.instrument_id),
            pending_orders=await count(PendingOrderRow, PendingOrderRow.instrument_id),
            ledger_entries=await count(LedgerEntryRow, LedgerEntryRow.instrument_id),
        )
