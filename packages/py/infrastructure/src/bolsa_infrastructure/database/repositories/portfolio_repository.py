from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bolsa_domain.entities.portfolio import (
    Portfolio,
    PortfolioSummary,
    Position,
    TradeResult,
    Transaction,
)
from bolsa_domain.errors import IdempotencyKeyExists
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.db_errors import is_unique_violation
from bolsa_infrastructure.database.models import (
    InstrumentRow,
    OhlcvBarRow,
    PortfolioRow,
    PositionRow,
    TransactionRow,
)
from bolsa_infrastructure.ids import new_id


class SqlAlchemyPortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Sesión activa — R-8A (savepoint de idempotencia en use-cases)."""
        return self._session

    async def _resolve_portfolio(self, legacy_portfolio_id: str) -> Portfolio:
        # F-IND-1/F-FIN-1: NO existe un "default global por nombre". El scope a la
        # cartera SIEMPRE viene resuelto por cuenta (via AccountScope.legacy_portfolio_id
        # en account_repository). Si un call-site omite el scope, fallamos en lugar de
        # resolver silenciosamente una cartera que podría pertenecer a otra cuenta
        # (fail-closed): nunca tocamos dinero ajeno.
        row = await self._session.get(PortfolioRow, legacy_portfolio_id)
        if row is None:
            raise ValueError("Cartera no encontrada")
        return Portfolio(
            id=row.id,
            name=row.name,
            currency=row.currency,
            cash=float(row.cash),
        )

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
            out[str(iid)] = (
                float(close) if isinstance(close, (int, float, Decimal)) else float(close)
            )
        return out

    async def _latest_close(self, instrument_id: str) -> float | None:
        closes = await self._latest_closes([instrument_id])
        return closes.get(instrument_id)

    async def _latest_transaction_prices(
        self, portfolio_id: str, instrument_ids: list[str]
    ) -> dict[str, float]:
        """Último ``TransactionRow.price`` por instrumento, scoped a la cartera.

        Fallback "mark-to-cost" (M-1, Opción B): cuando un instrumento de la cartera no
        tiene close D1 (``_latest_closes`` no devuelve precio), usamos su último precio
        TRANSACCIONAL histórico como ``last_price``. Es un precio histórico de coste
        (≈ coste del último trade), NO un precio de mercado, pero es el mejor dato
        disponible y evita: (1) la pérdida ficticia (=coste completo de la posición)
        que antes se reportaba en ``total_unrealized_pnl``, y (2) subestimar la equity
        en custodia/riesgo (``total_equity = cash + Σ market_value`` seguía excluyendo
        estas posiciones mientras su cost ya sumaba). No es ideal como mark-to-market,
        pero es la decisión del usuario (Opción B).

        Una sola query para el conjunto (sin N+1): ``DISTINCT ON (instrument_id)`` con
        el ``executed_at`` más reciente por instrumento.
        """
        if not instrument_ids:
            return {}
        stmt = (
            select(TransactionRow.instrument_id, TransactionRow.price)
            .where(
                TransactionRow.portfolio_id == portfolio_id,
                TransactionRow.instrument_id.in_(instrument_ids),
            )
            .distinct(TransactionRow.instrument_id)
            .order_by(TransactionRow.instrument_id, TransactionRow.executed_at.desc())
        )
        result = await self._session.execute(stmt)
        out: dict[str, float] = {}
        for iid, price in result.all():
            if price is None:
                continue
            out[str(iid)] = float(price)
        return out

    async def get_summary(self, legacy_portfolio_id: str) -> PortfolioSummary:
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

        # M-1 (Opción B): para los instrumentos sin close D1, un fallback "mark-to-cost"
        # al último precio transaccional de la cartera (una query para el conjunto).
        ids_sin_precio = [
            row.instrument_id for row in positions_rows if closes.get(row.instrument_id) is None
        ]
        tx_prices = (
            await self._latest_transaction_prices(portfolio.id, ids_sin_precio)
            if ids_sin_precio
            else {}
        )

        positions: list[Position] = []
        total_market_value = 0.0
        total_cost = 0.0

        for row in positions_rows:
            quantity = float(row.quantity)
            avg_cost = float(row.avg_cost)
            cost_basis = quantity * avg_cost
            last_price = closes.get(row.instrument_id)
            if last_price is None:
                # fallback "mark-to-cost": último precio transaccional (M-1, Opción B)
                last_price = tx_prices.get(row.instrument_id)
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
            # Nota M-1 (Opción B): si la posición NO tiene ni close D1 ni transacción
            # en cartera, queda sin precio observable → NO suma a total_market_value
            # NI a total_cost, para que total_unrealized_pnl (= Σ market_value − Σ cost)
            # no fabrique una pérdida fantasma (=coste completo) ni total_equity
            # (`cash + total_market_value`) contabilice un valor desconocido.
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
                    sector=row.instrument.sector,
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
        legacy_portfolio_id: str,
        *,
        limit: int | None = 50,
        executed_before: datetime | None = None,
    ) -> list[Transaction]:
        portfolio = await self._resolve_portfolio(legacy_portfolio_id)
        stmt = (
            select(TransactionRow)
            .where(TransactionRow.portfolio_id == portfolio.id)
            .options(selectinload(TransactionRow.instrument))
            .order_by(TransactionRow.executed_at.desc())
        )
        if executed_before is not None:
            # F-FIN-2: el cómputo fiscal necesita TODAS las transacciones hasta el fin
            # del ejercicio (incluye carry-in de compras previas para FIFO/avg) pero no
            # los ejercicios futuros. Filtrar aquí evita traer años innecesarios.
            stmt = stmt.where(TransactionRow.executed_at < executed_before)
        if limit is not None:
            stmt = stmt.limit(limit)
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

    async def find_transaction_by_idempotency(
        self,
        legacy_portfolio_id: str,
        idempotency_key: str,
    ) -> Transaction | None:
        """Devuelve la transacción ya grabada para (cartera, idempotency_key), si existe."""
        portfolio = await self._resolve_portfolio(legacy_portfolio_id)
        stmt = (
            select(TransactionRow)
            .where(
                TransactionRow.portfolio_id == portfolio.id,
                TransactionRow.idempotency_key == idempotency_key,
            )
            .options(selectinload(TransactionRow.instrument))
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Transaction(
            id=row.id,
            type=row.type,  # type: ignore[arg-type]
            instrument_id=row.instrument_id,
            symbol=row.instrument.symbol,
            quantity=float(row.quantity),
            price=float(row.price),
            total=float(row.total),
            executed_at=row.executed_at.isoformat(),
        )

    async def _write_trade_rows(
        self,
        *,
        transaction: TransactionRow,
        portfolio_row: PortfolioRow,
        existing_position: PositionRow | None,
        trade_type: Literal["buy", "sell"],
        quantity: float,
        cash: Decimal,
        total: Decimal,
        fees: Decimal,
        now: datetime,
    ) -> None:
        """Escribe transaction + mutación de cartera/posición dentro del savepoint.

        Extraído en R-8A para poder envolver TODAS las escrituras del trade en un
        único ``begin_nested()`` y revertirlas juntas si surge un IntegrityError por
        idempotencia.
        """
        if trade_type == "buy":
            portfolio_row.cash = cash - total - fees
            if existing_position:
                old_qty = existing_position.quantity
                old_cost = existing_position.avg_cost
                new_qty: Decimal = old_qty + Decimal(str(quantity))
                new_avg = (old_qty * old_cost + total) / new_qty
                existing_position.quantity = new_qty
                existing_position.avg_cost = new_avg
                existing_position.updated_at = now
            else:
                self._session.add(
                    PositionRow(
                        id=new_id(),
                        portfolio_id=portfolio_row.id,
                        instrument_id=transaction.instrument_id,
                        quantity=Decimal(str(quantity)),
                        avg_cost=Decimal(str(transaction.price)),
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

    async def execute_trade(
        self,
        *,
        instrument_id: str,
        trade_type: Literal["buy", "sell"],
        quantity: float,
        price: float,
        legacy_portfolio_id: str,
        fee_amount: float = 0.0,
        idempotency_key: str,
    ) -> TradeResult:
        """Ejecuta un trade idempotente.

        ``idempotency_key`` es OBLIGATORIA y debe ser no vacía (defensa en
        profundidad R-11 C2): ``""``, whitespace puro ``"   "`` o cualquier cadena
        que tras ``strip()`` quede vacía lanzan ``ValueError`` antes de tocar el
        ledger. El guard DB de idempotencia (UNIQUE + ``IdempotencyKeyExists``) y el
        uso como ``reference`` dependen de una clave estable y no vacía; la capa DTO
        ya exige 16–128 chars, pero aquí se revalidan vacío/whitespace porque hay
        call-sites internos (AUTO execute / confirm) que la construyen desde datos.
        """
        if not idempotency_key.strip():
            raise ValueError("idempotency_key no puede estar vacía")
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
        # OR-P2: no multiplicar en float antes de Decimal.
        total = Decimal(str(quantity)) * Decimal(str(price))
        fees = Decimal(str(max(fee_amount, 0)))

        portfolio_row = await self._session.get(
            PortfolioRow,
            portfolio.id,
            with_for_update=True,
        )
        if portfolio_row is None:
            raise ValueError("Cartera no encontrada")

        cash = portfolio_row.cash
        if trade_type == "buy" and cash < total + fees:
            needed = float(total + fees)
            raise ValueError(
                f"Efectivo insuficiente (incl. comisiones). Necesario: {needed:.2f} € · Disponible: {float(cash):.2f} €",
            )

        position_stmt = (
            select(PositionRow)
            .where(
                PositionRow.portfolio_id == portfolio.id,
                PositionRow.instrument_id == instrument_id,
            )
            .with_for_update()
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
            idempotency_key=idempotency_key,
        )

        try:
            async with self._session.begin_nested():
                self._session.add(transaction)
                await self._write_trade_rows(
                    transaction=transaction,
                    portfolio_row=portfolio_row,
                    existing_position=existing_position,
                    trade_type=trade_type,
                    quantity=quantity,
                    cash=cash,
                    total=total,
                    fees=fees,
                    now=now,
                )
                await self._session.flush()
        except IntegrityError as exc:
            if idempotency_key is not None and is_unique_violation(exc):
                # R-8A/P0-B: otro request con la MISMA idempotency_key ya grabó esta
                # transacción (colisión del UNIQUE transactions(portfolio_id, idempotency_key)).
                # El savepoint revierte este intento (cartera/posición/transaction locales);
                # señalizamos al use-case para que rejuego el original en lugar de estallar.
                # Solo ante violación de unicidad; otros IntegrityError se re-propagan.
                raise IdempotencyKeyExists(idempotency_key) from exc
            raise

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

    async def deduct_cash(
        self,
        legacy_portfolio_id: str,
        amount: float,
        *,
        allow_partial: bool = False,
    ) -> float:
        if amount <= 0:
            portfolio = await self.get_summary(legacy_portfolio_id)
            return portfolio.portfolio.cash
        row = await self._session.get(
            PortfolioRow,
            legacy_portfolio_id,
            with_for_update=True,
        )
        if row is None:
            raise ValueError("Cartera no encontrada")
        debit = Decimal(str(amount))
        if debit > row.cash and not allow_partial:
            raise ValueError(
                f"Efectivo insuficiente. Necesario: {float(debit):.2f} € · Disponible: {float(row.cash):.2f} €",
            )
        if allow_partial:
            debit = min(debit, row.cash)
        row.cash -= debit
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return float(row.cash)

    async def add_cash(self, legacy_portfolio_id: str, amount: float) -> float:
        if amount <= 0:
            portfolio = await self.get_summary(legacy_portfolio_id)
            return portfolio.portfolio.cash
        row = await self._session.get(
            PortfolioRow,
            legacy_portfolio_id,
            with_for_update=True,
        )
        if row is None:
            raise ValueError("Cartera no encontrada")
        credit = Decimal(str(amount))
        row.cash += credit
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return float(row.cash)
