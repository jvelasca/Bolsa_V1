"""R-8C.1 (actualizado R-10 F3) — invariante de `balance_after` **secuencial por fila** en `ledger_entries`.

Invariante objetivo: recorriendo las filas de un account ordenadas por
``executed_at, id``, el `balance_after` de CADA fila es igual al `balance_after`
de la anterior MÁS su `amount`::

    balance_after[n] == balance_after[n-1] + amount[n]

Modela EXACTAMENTE el comportamiento de producción ``ExecuteTrade``
(``bolsa_application/accounts.py``) desde **R-10 F3**:
- la fila ``trade`` escribe ``balance_after = cash_before + amount`` (cash tras
  aplicar SOLO el notional, aún sin fee);
- la fila ``fee`` escribe ``balance_after = trade_balance - abs(fees)`` (cash final
  post-operación).

Ya NO existe el caso de grupo atómico que comparte balance_after entre trade y fee;
cada fila encadena con la anterior según la suma de su propio ``amount``.

Nota sobre signos (emulación fiel de producción):
- ``append_trade`` escribe ``amount = -notional`` (buy) / ``+notional`` (sell).
- ``append_fee`` escribe ``amount = -abs(fees)`` SIEMPRE (``ledger_repository.py``
  ``append_fee``) → en buy la fee es negativa, en sell también (resta cash).
- Ambas filas comparten ``reference_id = result.transaction.id``.

⇒ Para un buy: ``balance_after[trade] = cash_before − notional`` y
``balance_after[fee] = cash_before − notional − fees`` (impacto de cash total).

PostgreSQL real (patrón ``db_session`` local, ``pytest.skip`` si no hay DB).
No modifica producción: es SOLO un test-espejo de la semántica secuencial.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.rollback()
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


def _now() -> datetime:
    return datetime.now(UTC)


async def _new_account(
    session: AsyncSession, tag: str
) -> tuple[InvestmentAccountRow, InvestmentPortfolioRow]:
    """Crea un ``InvestmentAccountRow`` + ``InvestmentPortfolioRow`` reales."""
    account = InvestmentAccountRow(
        id=f"acc_{tag}_{uuid4().hex[:12]}",
        user_id=None,
        name=f"R8C {tag}",
        type="simulated",
        status="active",
        currency="EUR",
        base_currency="EUR",
        initial_deposit=Decimal("0"),
        leverage=Decimal("1"),
        is_default=False,
        created_at=_now(),
        updated_at=_now(),
    )
    portfolio = InvestmentPortfolioRow(
        id=f"pf_{tag}_{uuid4().hex[:12]}",
        account_id=account.id,
        name=f"Portfolio R8C {tag}",
        is_default=True,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([account, portfolio])
    await session.flush()
    return account, portfolio


class _LedgerBuilder:
    """Construye una secuencia de filas ``LedgerEntryRow`` imitando producción.

    Lleva el ``running_balance`` y el ``tick`` para que cada fila tenga un
    ``executed_at`` estrictamente creciente (SQL ordena por ``executed_at, id``).
    """

    def __init__(self, session: AsyncSession, account_id: str, portfolio_id: str) -> None:
        self._session = session
        self._account_id = account_id
        self._portfolio_id = portfolio_id
        self._running = Decimal("0")
        self._tick = 0
        self._now = _now()

    def _stamp(self) -> datetime:
        # Monotónico distinto por fila (microsegundos), base común.
        self._tick += 1
        return self._now.replace(microsecond=self._tick)

    async def _add(
        self,
        *,
        type: str,
        amount: Decimal,
        balance_after: Decimal,
        reference_type: str | None = None,
        reference_id: str | None = None,
        description: str | None = None,
    ) -> LedgerEntryRow:
        row = LedgerEntryRow(
            id=f"le_{self._tick}_{uuid4().hex[:12]}",
            account_id=self._account_id,
            portfolio_id=self._portfolio_id,
            type=type,
            amount=amount,
            currency="EUR",
            balance_after=balance_after,
            instrument_id=None,
            quantity=None,
            price=None,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            executed_at=self._stamp(),
            created_at=self._now,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def seed_deposit(self, amount: Decimal) -> LedgerEntryRow:
        self._running += amount
        return await self._add(
            type="deposit",
            amount=amount,
            balance_after=self._running,
            reference_type="manual",
        )

    async def external_deposit(self, amount: Decimal) -> LedgerEntryRow:
        self._running += amount
        return await self._add(
            type="deposit",
            amount=amount,
            balance_after=self._running,
            reference_type="external",
            reference_id=f"ext_{uuid4().hex[:12]}",
        )

    async def withdraw(self, amount: Decimal) -> LedgerEntryRow:
        self._running -= amount
        return await self._add(
            type="withdrawal",
            amount=-amount,
            balance_after=self._running,
            reference_type="external",
            reference_id=f"wd_{uuid4().hex[:12]}",
        )

    async def custody_fee(self, amount: Decimal) -> LedgerEntryRow:
        self._running -= amount
        return await self._add(
            type="fee",
            amount=-amount,
            balance_after=self._running,
            reference_type="custody",
            reference_id="custody-2026",
        )

    async def trade_with_fees(
        self, *, notional: Decimal, fees: Decimal, trade_type: str
    ) -> tuple[LedgerEntryRow, LedgerEntryRow]:
        """Emula `ExecuteTrade` (accounts.py) tras R-10 F3: balance_after SECUENCIAL.

        - amount[trade] = -notional (buy) / +notional (sell)
        - amount[fee]   = -abs(fees)   (append_fee siempre negativo)
        - balance_after[trade] = running_balance + amount[trade]   (cash sin fee)
        - balance_after[fee]   = balance_after[trade] + amount[fee] (cash final)
        """
        trade_amount = -notional if trade_type == "buy" else notional
        fee_amount = -abs(fees)
        trade_balance = self._running + trade_amount
        self._running = trade_balance + fee_amount
        tx_id = f"tx_{uuid4().hex[:12]}"
        trade = await self._add(
            type=trade_type,
            amount=trade_amount,
            balance_after=trade_balance,
            reference_type="transaction",
            reference_id=tx_id,
        )
        fee = await self._add(
            type="fee",
            amount=fee_amount,
            balance_after=self._running,
            reference_type="transaction",
            reference_id=tx_id,
        )
        return trade, fee

    @property
    def running_balance(self) -> Decimal:
        return self._running


async def _load_sorted_rows(session: AsyncSession, account_id: str) -> list[LedgerEntryRow]:
    stmt = (
        select(LedgerEntryRow)
        .where(LedgerEntryRow.account_id == account_id)
        .order_by(LedgerEntryRow.executed_at, LedgerEntryRow.id)
    )
    return list((await session.execute(stmt)).scalars())


def _check_atomic_invariant(rows: list[LedgerEntryRow]) -> None:
    """Valida el invariante **secuencial por fila** sobre una secuencia ordenada.

    Regla (R-10 F3): ``balance_after[n] == balance_after[n-1] + amount[n]`` para
    TODA fila, arrancando desde ``prev_balance = 0``. Ya no hay grupos atómicos que
    compartan balance_after: la fila ``trade`` y la fila ``fee`` encadenan cada una
    con la suma de su propio ``amount``.
    """
    assert rows, "sin filas de ledger para validar"
    prev_balance = Decimal("0")
    for r in rows:
        expected = prev_balance + r.amount
        if r.balance_after != expected:
            raise AssertionError(
                f"fila {r.id} balance={r.balance_after} "
                f"!= prev={prev_balance} + amount({r.amount})={expected}"
            )
        prev_balance = r.balance_after


@pytest.mark.asyncio
async def test_r8c_atomic_grupo_ledger_pasa(db_session: AsyncSession) -> None:
    """Cadena completa seed/deposit/withdraw/custody + 2 trades+fee cumple el invariante."""
    account, portfolio = await _new_account(db_session, "chain")
    builder = _LedgerBuilder(db_session, account.id, portfolio.id)

    await builder.seed_deposit(Decimal("100000.00"))
    await builder.external_deposit(Decimal("2500.00"))
    await builder.withdraw(Decimal("1000.00"))
    await builder.custody_fee(Decimal("5.75"))

    # 2 trades secuenciales, cada uno un grupo atómico trade+fee post-fee.
    await builder.trade_with_fees(
        notional=Decimal("10000"), fees=Decimal("5.50"), trade_type="buy"
    )
    await builder.trade_with_fees(
        notional=Decimal("3000"), fees=Decimal("2.25"), trade_type="sell"
    )
    await db_session.commit()

    rows = await _load_sorted_rows(db_session, account.id)
    # 4 filas sueltas + 2 grupos × 2 filas = 8 filas.
    assert len(rows) == 8
    _check_atomic_invariant(rows)


@pytest.mark.asyncio
async def test_r8c_atomic_grupo_balance_final(db_session: AsyncSession) -> None:
    """El balance_after final coincide con el running esperado tras la cadena."""
    account, portfolio = await _new_account(db_session, "final")
    builder = _LedgerBuilder(db_session, account.id, portfolio.id)

    await builder.seed_deposit(Decimal("100000.00"))
    await builder.trade_with_fees(
        notional=Decimal("10000"), fees=Decimal("5.50"), trade_type="buy"
    )
    await builder.trade_with_fees(
        notional=Decimal("3000"), fees=Decimal("2.25"), trade_type="sell"
    )
    await db_session.commit()

    rows = await _load_sorted_rows(db_session, account.id)
    assert rows[-1].balance_after == builder.running_balance
    _check_atomic_invariant(rows)


@pytest.mark.asyncio
async def test_r8c_detectar_fila_descuadrada(db_session: AsyncSession) -> None:
    """NEGATIVO: un `balance_after` corrupto rompe el invariante secuencial."""
    account, portfolio = await _new_account(db_session, "broken")
    builder = _LedgerBuilder(db_session, account.id, portfolio.id)

    await builder.seed_deposit(Decimal("100000.00"))
    trade, fee = await builder.trade_with_fees(
        notional=Decimal("10000"), fees=Decimal("5.50"), trade_type="buy"
    )
    # Sentido R-10 F3: trade y fee tienen balance_after SECUENCIALES y distintos.
    assert fee.balance_after == trade.balance_after - Decimal("5.50")
    # Corromper la fila fee: balance_after descuadrado (rompe la cadena secuencial).
    fee.balance_after = fee.balance_after + Decimal("0.01")
    db_session.add(fee)
    await db_session.commit()

    rows = await _load_sorted_rows(db_session, account.id)
    with pytest.raises(AssertionError):
        _check_atomic_invariant(rows)
