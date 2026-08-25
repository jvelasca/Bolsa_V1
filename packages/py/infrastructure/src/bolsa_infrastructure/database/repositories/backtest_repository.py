from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from bolsa_domain.entities.backtest import BacktestRun, BacktestRunDetail, BacktestTrade
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bolsa_infrastructure.database.models import BacktestRunRow, BacktestTradeRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyBacktestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map_run(self, row: BacktestRunRow) -> BacktestRun:
        manifest = row.manifest if isinstance(row.manifest, dict) else None
        return BacktestRun(
            id=row.id,
            instrument_id=row.instrument_id,
            symbol=row.instrument.symbol,
            name=row.instrument.name,
            strategy_type=row.strategy_type,
            initial_cash=float(row.initial_cash),
            final_equity=float(row.final_equity),
            total_return_pct=float(row.total_return_pct),
            max_drawdown_pct=float(row.max_drawdown_pct),
            trade_count=row.trade_count,
            win_count=row.win_count,
            bar_count=row.bar_count,
            first_date=row.first_date.isoformat(),
            last_date=row.last_date.isoformat(),
            created_at=row.created_at.isoformat(),
            timeframe=row.timeframe,
            data_version=row.data_version,
            commission_bps=row.commission_bps,
            slippage_bps=row.slippage_bps,
            manifest=manifest,
            strategy_definition_id=row.strategy_definition_id,
        )

    async def list_runs(self, limit: int = 20) -> list[BacktestRun]:
        stmt = (
            select(BacktestRunRow)
            .options(selectinload(BacktestRunRow.instrument))
            .order_by(BacktestRunRow.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._map_run(row) for row in result.scalars().all()]

    async def prune_runs(self, keep: int) -> int:
        """Delete oldest runs beyond `keep` (newest kept). Returns deleted count."""
        keep_n = max(0, int(keep))
        ids_stmt = (
            select(BacktestRunRow.id)
            .order_by(BacktestRunRow.created_at.desc())
            .offset(keep_n)
        )
        result = await self._session.execute(ids_stmt)
        stale_ids = [row[0] for row in result.all()]
        if not stale_ids:
            return 0
        await self._session.execute(
            delete(BacktestRunRow).where(BacktestRunRow.id.in_(stale_ids)),
        )
        await self._session.flush()
        return len(stale_ids)

    async def get_run(self, run_id: str) -> BacktestRunDetail | None:
        stmt = (
            select(BacktestRunRow)
            .where(BacktestRunRow.id == run_id)
            .options(
                selectinload(BacktestRunRow.instrument),
                selectinload(BacktestRunRow.trades),
            )
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        base = self._map_run(row)
        trades = sorted(row.trades, key=lambda t: t.timestamp)
        return BacktestRunDetail(
            id=base.id,
            instrument_id=base.instrument_id,
            symbol=base.symbol,
            name=base.name,
            strategy_type=base.strategy_type,
            initial_cash=base.initial_cash,
            final_equity=base.final_equity,
            total_return_pct=base.total_return_pct,
            max_drawdown_pct=base.max_drawdown_pct,
            trade_count=base.trade_count,
            win_count=base.win_count,
            bar_count=base.bar_count,
            first_date=base.first_date,
            last_date=base.last_date,
            created_at=base.created_at,
            timeframe=base.timeframe,
            data_version=base.data_version,
            commission_bps=base.commission_bps,
            slippage_bps=base.slippage_bps,
            manifest=base.manifest,
            strategy_definition_id=base.strategy_definition_id,
            trades=[
                BacktestTrade(
                    id=trade.id,
                    type=trade.type,  # type: ignore[arg-type]
                    timestamp=trade.timestamp.isoformat(),
                    price=float(trade.price),
                    quantity=float(trade.quantity),
                    equity_after=float(trade.equity_after),
                )
                for trade in trades
            ],
        )

    async def save_run(
        self,
        *,
        instrument_id: str,
        strategy_type: str,
        initial_cash: float,
        final_equity: float,
        total_return_pct: float,
        max_drawdown_pct: float,
        trade_count: int,
        win_count: int,
        bar_count: int,
        first_date: str,
        last_date: str,
        trades: list[tuple[Literal["buy", "sell"], str, float, float, float]],
        timeframe: str = "1d",
        data_version: str | None = None,
        commission_bps: int = 0,
        slippage_bps: int = 0,
        manifest: dict[str, Any] | None = None,
        run_id: str | None = None,
        strategy_definition_id: str | None = None,
    ) -> BacktestRunDetail:
        now = datetime.now(UTC)
        resolved_run_id = run_id or new_id()
        run = BacktestRunRow(
            id=resolved_run_id,
            instrument_id=instrument_id,
            strategy_type=strategy_type,
            initial_cash=Decimal(str(initial_cash)),
            final_equity=Decimal(str(final_equity)),
            total_return_pct=Decimal(str(total_return_pct)),
            max_drawdown_pct=Decimal(str(max_drawdown_pct)),
            trade_count=trade_count,
            win_count=win_count,
            bar_count=bar_count,
            first_date=date.fromisoformat(first_date),
            last_date=date.fromisoformat(last_date),
            created_at=now,
            timeframe=timeframe,
            data_version=data_version,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            manifest=manifest,
            strategy_definition_id=strategy_definition_id,
        )
        self._session.add(run)

        for trade_type, timestamp, price, quantity, equity_after in trades:
            self._session.add(
                BacktestTradeRow(
                    id=new_id(),
                    backtest_run_id=resolved_run_id,
                    type=trade_type,
                    timestamp=date.fromisoformat(timestamp),
                    price=Decimal(str(price)),
                    quantity=Decimal(str(quantity)),
                    equity_after=Decimal(str(equity_after)),
                ),
            )

        await self._session.flush()
        detail = await self.get_run(resolved_run_id)
        assert detail is not None
        return detail
