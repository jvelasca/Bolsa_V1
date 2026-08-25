"""Resumen de tablas y volúmenes en PostgreSQL."""
from __future__ import annotations

from dataclasses import dataclass

from bolsa_infrastructure.database.models import OhlcvBarRow
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

TABLE_LABELS: tuple[tuple[str, str], ...] = (
    ("instruments", "Instrumentos"),
    ("ohlcv_bars", "Velas OHLCV"),
    ("data_sync_log", "Registros sync"),
    ("investment_accounts", "Cuentas de inversión"),
    ("investment_portfolios", "Carteras (cuenta)"),
    ("ledger_entries", "Ledger"),
    ("investor_profiles", "Perfiles inversor"),
    ("portfolios", "Carteras (legacy)"),
    ("positions", "Posiciones"),
    ("transactions", "Transacciones"),
    ("backtest_runs", "Backtests"),
    ("backtest_trades", "Trades backtest"),
    ("instrument_lists", "Listas"),
    ("instrument_list_items", "Elementos lista"),
    ("price_alerts", "Alertas precio"),
    ("signal_alert_subscriptions", "Alertas señal"),
    ("tracker_definitions", "Rastreadores"),
    ("workspaces", "Workspaces"),
    ("sync_queue", "Cola sync"),
    ("pending_orders", "Órdenes pendientes"),
)


@dataclass(frozen=True, slots=True)
class DatabaseTableCount:
    """Use-case / tipo: Database Table Count."""
    table: str
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class InstrumentOhlcvBreakdown:
    """Use-case / tipo: Instrument Ohlcv Breakdown."""
    timeframe: str
    bar_count: int


@dataclass(frozen=True, slots=True)
class DatabaseSummary:
    """Use-case / tipo: Database Summary."""
    connected: bool
    message: str
    tables: tuple[DatabaseTableCount, ...]
    instrument_ohlcv: tuple[InstrumentOhlcvBreakdown, ...]


class GetDatabaseSummary:
    """Obtiene Database Summary."""
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, instrument_id: str | None = None) -> DatabaseSummary:
        try:
            await self._session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — resumen BD
            return DatabaseSummary(
                connected=False,
                message=str(exc),
                tables=(),
                instrument_ohlcv=(),
            )

        tables: list[DatabaseTableCount] = []
        for table_name, label in TABLE_LABELS:
            result = await self._session.execute(
                text(f"SELECT COUNT(*) FROM {table_name}"),
            )
            tables.append(
                DatabaseTableCount(table=table_name, label=label, count=int(result.scalar_one())),
            )

        instrument_ohlcv: list[InstrumentOhlcvBreakdown] = []
        if instrument_id:
            stmt = (
                select(OhlcvBarRow.timeframe, func.count())
                .where(OhlcvBarRow.instrument_id == instrument_id)
                .group_by(OhlcvBarRow.timeframe)
                .order_by(OhlcvBarRow.timeframe)
            )
            result = await self._session.execute(stmt)
            for timeframe, count in result.all():
                instrument_ohlcv.append(
                    InstrumentOhlcvBreakdown(timeframe=str(timeframe), bar_count=int(count)),
                )

        return DatabaseSummary(
            connected=True,
            message="PostgreSQL conectado",
            tables=tuple(tables),
            instrument_ohlcv=tuple(instrument_ohlcv),
        )
