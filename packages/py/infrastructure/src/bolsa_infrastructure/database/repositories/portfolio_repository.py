from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from bolsa_domain.entities.portfolio import (
    Portfolio,
    PortfolioSummary,
    Position,
    TradeResult,
    Transaction,
)
from bolsa_domain.value_objects.timeframe import TimeFrame
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bolsa_infrastructure.database.models import (
    InstrumentRow,
    OhlcvBarRow,
    PortfolioRow,
    PositionRow,
    TransactionRow,
)
from bolsa_infrastructure.ids import new_id

DEFAULT_PORTFOLIO_NAME = "Cartera principal"
INITIAL_CASH = Decimal(100000)


class SqlAlchemyPortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_default_portfolio(self) -> Portfolio:
        stmt = select(PortfolioRow).where(PortfolioRow.name == DEFAULT_PORTFOLIO_NAME)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            now = datetime.now(UTC)
            row = PortfolioRow(
                id=new_id(),
                name=DEFAULT_PORTFOLIO_NAME,
                currency="EUR",
                cash=INITIAL_CASH,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
            await self._session.flush()
        return Portfolio(
            id=row.id,
            name=row.name,
            currency=row.currency,
            cash=float(row.cash),
        )

    async def _resolve_portfolio(self, legacy_portfolio_id: str | None) -> Portfolio:
        if legacy_portfolio_id:
            row = await self._session.get(PortfolioRow, legacy_portfolio_id)
            if row is None:
                raise ValueError("Cartera no encontrada")
            return Portfolio(
                id=row.id,
                name=row.name,
                currency=row.currency,
                cash=float(row.cash),
            )
        return await self.get_or_create_default_portfolio()

    async def _latest_closes(self, instrument_ids: list[str]) -> dict[str, float]:
        """Latest D1 close per instrument — one query for the whole set."""
        if not instrument_ids:
            return {}
        # DISTINCT ON (Postgres): latest bar per instrument.
        stmt = (
            select(OhlcvBarRow.instrument_id, OhlcvBarRow.close)
            .where(
                OhlcvBarRow.instrument_id.in_(instrument_ids),
                OhlcvBarRow.timeframe == TimeFrame.D1,
            )
            .distinct(OhlcvBarRow.instrument_id)
            .order_by(OhlcvBarRow.instrument_id, OhlcvBarRow.timestamp.desc())
        )
        result = await self._session.execute(stmt)
        out: dict[str, float] = {}
        for iid, close in result.all():
            if close is None:
                continue
            out[str(iid)] = float(close) if isinstance(close, (int, float, Decimal)) else float(close)
        return out

    async def _latest_close(self, instrument_id: str) -> float | None:
        closes = await self._latest_closes([instrument_id])
        return closes.get(instrument_id)

    async def get_summary(self, legacy_portfolio_id: str | None = None) -> PortfolioSummary:
        portfolio = await self._resolve_portfolio(legacy_portfolio_id)
        stmt = (
            select(PositionRow)
            .where(PositionRow.portfolio_id == portfolio.id)
            .options(selectinload(PositionRow.instrument))
            .join(InstrumentRow)
            .order_by(InstrumentRow.symbol.asc())
        )
        result = await self._session.execute(stmt)
        positions_rows = list(result.scalars().all())
        closes = await self._latest_closes([row.instrument_id for row in positions_rows])

        positions: list[Position] = []
        total_market_value = 0.0
        total_cost = 0.0

        for row in positions_rows:
            quantity = float(row.quantity)
            avg_cost = float(row.avg_cost)
            cost_basis = quantity * avg_cost
            last_price = closes.get(row.instrument_id)
            market_value = quantity * last_price if last_price is not None else None
            unrealized_pnl = market_value - cost_basis if market_value is not None else None
            unrealized_pnl_pct = (
                (unrealized_pnl / cost_basis) * 100
                if unrealized_pnl is not None and cost_basis > 0
                else None
            )
            if market_value is not None:
                total_market_value += market_value
            total_cost += cost_basis
            positions.append(
                Position(
                    id=row.id,
                    instrument_id=row.instrument_id,
                    symbol=row.instrument.symbol,
                    name=row.instrument.name,
                    quantity=quantity,
                    avg_cost=avg_cost,
                    last_price=last_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                ),
            )

        return PortfolioSummary(
            portfolio=portfolio,
            positions=positions,
            total_market_value=total_market_value,
            total_cost=total_cost,
            total_unrealized_pnl=total_market_value - total_cost,
            total_equity=portfolio.cash + total_market_value,
        )

    async def list_transactions(
        self,
        limit: int = 50,
        legacy_portfolio_id: str | None = None,
    ) -> list[Transaction]:
        portfolio = await self._resolve_portfolio(legacy_portfolio_id)
        stmt = (
            select(TransactionRow)
            .where(TransactionRow.portfolio_id == portfolio.id)
            .options(selectinload(TransactionRow.instrument))
            .order_by(TransactionRow.executed_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            Transaction(
                id=row.id,
                type=row.type,  # type: ignore[arg-type]
                instrument_id=row.instrument_id,
                symbol=row.instrument.symbol,
                quantity=float(row.quantity),
                price=float(row.price),
                total=float(row.total),
                executed_at=row.executed_at.isoformat(),
            )
            for row in rows
        ]

    async def execute_trade(
        self,
        *,
        instrument_id: str,
        trade_type: Literal["buy", "sell"],
        quantity: float,
        price: float,
        legacy_portfolio_id: str | None = None,
        fee_amount: float = 0.0,
    ) -> TradeResult:
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")
        if price <= 0:
            raise ValueError("El precio debe ser mayor que cero")

        instrument_stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        instrument_result = await self._session.execute(instrument_stmt)
        instrument = instrument_result.scalar_one_or_none()
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        portfolio = await self._resolve_portfolio(legacy_portfolio_id)
        total = Decimal(str(quantity * price))
        fees = Decimal(str(max(fee_amount, 0)))

        portfolio_row = await self._session.get(PortfolioRow, portfolio.id)
        if portfolio_row is None:
            raise ValueError("Cartera no encontrada")

        cash = portfolio_row.cash
        if trade_type == "buy" and cash < total + fees:
            needed = float(total + fees)
            raise ValueError(
                f"Efectivo insuficiente (incl. comisiones). Necesario: {needed:.2f} € · Disponible: {float(cash):.2f} €",
            )

        position_stmt = select(PositionRow).where(
            PositionRow.portfolio_id == portfolio.id,
            PositionRow.instrument_id == instrument_id,
        )
        position_result = await self._session.execute(position_stmt)
        existing_position = position_result.scalar_one_or_none()

        if trade_type == "sell":
            held = float(existing_position.quantity) if existing_position else 0.0
            if held < quantity:
                raise ValueError(f"No tienes suficientes acciones. En cartera: {held}")

        now = datetime.now(UTC)
        transaction = TransactionRow(
            id=new_id(),
            portfolio_id=portfolio.id,
            instrument_id=instrument_id,
            type=trade_type,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)),
            total=total,
            executed_at=now,
        )
        self._session.add(transaction)

        if trade_type == "buy":
            portfolio_row.cash = cash - total - fees
            if existing_position:
                old_qty = existing_position.quantity
                old_cost = existing_position.avg_cost
                new_qty = old_qty + Decimal(str(quantity))
                new_avg = (old_qty * old_cost + total) / new_qty
                existing_position.quantity = new_qty
                existing_position.avg_cost = new_avg
                existing_position.updated_at = now
            else:
                self._session.add(
                    PositionRow(
                        id=new_id(),
                        portfolio_id=portfolio.id,
                        instrument_id=instrument_id,
                        quantity=Decimal(str(quantity)),
                        avg_cost=Decimal(str(price)),
                        updated_at=now,
                    ),
                )
        else:
            portfolio_row.cash = cash + total - fees
            assert existing_position is not None
            new_qty = existing_position.quantity - Decimal(str(quantity))
            if new_qty == 0:
                await self._session.delete(existing_position)
            else:
                existing_position.quantity = new_qty
                existing_position.updated_at = now

        portfolio_row.updated_at = now
        await self._session.flush()

        summary = await self.get_summary(legacy_portfolio_id)
        return TradeResult(
            transaction=Transaction(
                id=transaction.id,
                type=trade_type,
                instrument_id=instrument_id,
                symbol=instrument.symbol,
                quantity=quantity,
                price=price,
                total=float(total),
                executed_at=transaction.executed_at.isoformat(),
            ),
            summary=summary,
        )

    async def deduct_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        if amount <= 0:
            portfolio = await self.get_summary(legacy_portfolio_id)
            return portfolio.portfolio.cash
        row = await self._session.get(PortfolioRow, legacy_portfolio_id)
        if row is None:
            raise ValueError("Cartera no encontrada")
        fee = Decimal(str(amount))
        fee = min(fee, row.cash)
        row.cash -= fee
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return float(row.cash)

    async def transfer_cash(
        self,
        from_legacy_portfolio_id: str,
        to_legacy_portfolio_id: str,
        amount: float,
    ) -> tuple[float, float]:
        if from_legacy_portfolio_id == to_legacy_portfolio_id:
            raise ValueError("Origen y destino deben ser carteras distintas")
        if amount <= 0:
            raise ValueError("El importe debe ser mayor que cero")

        amount_dec = Decimal(str(amount))
        from_row = await self._session.get(PortfolioRow, from_legacy_portfolio_id)
        to_row = await self._session.get(PortfolioRow, to_legacy_portfolio_id)
        if from_row is None or to_row is None:
            raise ValueError("Cartera no encontrada")
        if from_row.currency != to_row.currency:
            raise ValueError("Las carteras deben usar la misma moneda")
        if from_row.cash < amount_dec:
            available = float(from_row.cash)
            raise ValueError(
                f"Efectivo insuficiente en origen. Disponible: {available:.2f} {from_row.currency}",
            )

        from_row.cash -= amount_dec
        to_row.cash += amount_dec
        now = datetime.now(UTC)
        from_row.updated_at = now
        to_row.updated_at = now
        await self._session.flush()
        return float(from_row.cash), float(to_row.cash)

    async def add_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        if amount <= 0:
            portfolio = await self.get_summary(legacy_portfolio_id)
            return portfolio.portfolio.cash
        row = await self._session.get(PortfolioRow, legacy_portfolio_id)
        if row is None:
            raise ValueError("Cartera no encontrada")
        credit = Decimal(str(amount))
        row.cash += credit
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return float(row.cash)
