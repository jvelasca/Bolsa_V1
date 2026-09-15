"""P1/N1 (v2.39.3) — secuencia del ledger por cuenta bajo DOS carteras de la MISMA cuenta.

Regresión del hallazgo de auditoría: ``next_executed_at(account_id)`` es por CUENTA,
pero antes de v2.39.3 el lock que lo protegía era el de CARTERA (``with_for_update``
sobre ``PortfolioRow``). Dos carteras de la misma cuenta no comparten ``legacy_portfolio_id``,
de modo que sus escritores NO se excluían entre sí y podían leer el mismo ``MAX(executed_at)``
produciendo dos asientos con idéntico instante (el desempate por ``id``, UUID v4 aleatorio,
no rescata el orden real).

La corrección introduce ``SqlAlchemyAccountRepository.lock_account(account_id)`` (mutex
financiero por cuenta) que se adquiere ANTES de cualquier lock de cartera. Este test lo
ejerce a nivel de repositorio (``resolve_scope`` colapsa a la cartera default, así que se
orquesta el intercalado real entre dos carteras manualmente) y verifica:

- ``executed_at`` ESTRICTAMENTE creciente por cuenta (sin duplicados).
- ``sorted(ledger, executed_at)`` reconstruye el orden de aplicación por cartera
  (cadena ``balance_after[n] == balance_after[n-1] + amount[n]``).
- M-2: ``Σ ledger.amount == Σ cash`` de la cuenta.

Se ejecuta contra PostgreSQL REAL (DB aislada ``bolsa_v1_chaos``) y repite varias ráfagas
concurrentes para cazar carreras intermitentes. ``pytest.skip`` si no hay DB.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from bolsa_infrastructure.database.models import (
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Cifras: 2 carteras × N operaciones concurrentes por ráfaga, repetidas _BURSTS veces.
_OPS_PER_PORTFOLIO = 60
_BURSTS = 5


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@asynccontextmanager
async def _factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Engine nuevo + session_factory aislados (mismo patrón que ``test_load_concurrency_flow``).

    Apunta a ``DATABASE_URL`` (DB aislada ``bolsa_v1_chaos``) y hace ``pytest.skip`` si
    PostgreSQL no está disponible. ``pool_size=24`` acotado (las operaciones serializan
    sobre la fila de cuenta, así que un pool mayor no acelera y sí monopoliza el servidor).
    """
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url or "",
        pool_pre_ping=True,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=24,
        max_overflow=0,
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


def _now() -> datetime:
    return datetime.now(UTC)


async def _create_account_two_portfolios(
    session: AsyncSession, tag: str
) -> tuple[str, str, str, str, str]:
    """Cuenta simulada con DOS carteras. Devuelve (account, p1_legacy, p1_inv, p2_legacy, p2_inv).

    P1 es la cartera default que crea ``create_simulated_account`` (con seed ledger).
    P2 es una segunda cartera (``PortfolioRow`` + ``InvestmentPortfolioRow``) de la MISMA
    cuenta, sin seed ledger — exactamente la configuración multi-portfolio que destapó el
    P1/N1.
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"MP {tag}",
        initial_deposit=100_000.0,
    )
    p1_legacy = scope.portfolio.legacy_portfolio_id
    assert p1_legacy is not None
    p1_inv = scope.portfolio.id

    p2_legacy = PortfolioRow(
        id=f"leg2_{tag}_{uuid4().hex[:12]}",
        name=f"MP {tag} — cartera 2",
        currency="EUR",
        cash=Decimal("0"),
        created_at=_now(),
        updated_at=_now(),
    )
    p2_inv = InvestmentPortfolioRow(
        id=f"pf2_{tag}_{uuid4().hex[:12]}",
        account_id=scope.account.id,
        legacy_portfolio_id=p2_legacy.id,
        name=f"MP {tag} — portfolio 2",
        is_default=False,
        sort_order=1,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([p2_legacy, p2_inv])
    await session.flush()
    return scope.account.id, p1_legacy, p1_inv, p2_legacy.id, p2_inv.id


async def _portfolio_deposit_worker(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    legacy_pf_id: str,
    inv_pf_id: str,
    amount: float,
    key: str,
) -> None:
    """Un depósito real en una cartera de la cuenta, en sesión independiente.

    Orden de lock determinista cuenta → cartera: ``lock_account`` (FOR UPDATE sobre la
    fila de cuenta) antes de ``add_cash`` (with_for_update sobre la cartera). El asiento
    se escribe con ``append_cash_movement``, que secuencia internamente ``executed_at``.
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    async with factory() as s:
        account_repo = SqlAlchemyAccountRepository(s)
        portfolio_repo = SqlAlchemyPortfolioRepository(s)
        ledger_repo = SqlAlchemyLedgerRepository(s)
        # P1/N1: mutex financiero por CUENTA antes del lock de cartera.
        await account_repo.lock_account(account_id)
        balance_after = await portfolio_repo.add_cash(legacy_pf_id, amount)
        await ledger_repo.append_cash_movement(
            account_id=account_id,
            portfolio_id=inv_pf_id,
            entry_type="deposit",
            amount=amount,
            currency="EUR",
            balance_after=balance_after,
            reference_id=key,
            reference_type="external",
            description="multi-portfolio deposit",
        )
        await s.commit()


async def _load_sorted_rows(session: AsyncSession, account_id: str) -> list[LedgerEntryRow]:
    stmt = (
        select(LedgerEntryRow)
        .where(LedgerEntryRow.account_id == account_id)
        .order_by(LedgerEntryRow.executed_at, LedgerEntryRow.id)
    )
    return list((await session.execute(stmt)).scalars())


def _check_chain(rows: list[LedgerEntryRow]) -> None:
    """Cadena ``balance_after[n] == balance_after[n-1] + amount[n]`` desde ``prev = 0``."""
    prev = Decimal("0")
    for r in rows:
        expected = prev + r.amount
        if r.balance_after != expected:
            raise AssertionError(
                f"fila {r.id} balance={r.balance_after} != prev={prev} + amount({r.amount})={expected}"
            )
        prev = r.balance_after


async def _verify(session: AsyncSession, account_id: str) -> None:
    """Postcondiciones del P1/N1: monotonía estricta + cadena por cartera + M-2."""
    rows = await _load_sorted_rows(session, account_id)
    assert len(rows) >= 2, "sin filas suficientes de ledger"

    # 1) ``executed_at`` ESTRICTAMENTE creciente por cuenta (sin duplicados). Es la
    # propiedad que rompía el secuenciador por-cuenta protegido por lock de cartera.
    stamps = [r.executed_at for r in rows]
    assert len(set(stamps)) == len(stamps), "executed_at duplicado (secuenciador roto)"
    for prev, cur in zip(stamps, stamps[1:], strict=False):
        assert cur > prev, f"executed_at no estrictamente creciente: {cur} <= {prev}"

    # 2) Cadena balance_after por cartera: sorted(ledger, executed_at) reconstruye el
    # orden de aplicación de cada cartera (P1 con seed, P2 desde 0).
    portfolio_ids = {r.portfolio_id for r in rows if r.portfolio_id is not None}
    for pf_id in portfolio_ids:
        pf_rows = [r for r in rows if r.portfolio_id == pf_id]
        _check_chain(pf_rows)

    # 3) M-2: Σ ledger == Σ cash de la cuenta (todos sus legacy portfolios).
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    ledger_total = await SqlAlchemyLedgerRepository(session).sum_cash_amounts(account_id)
    cash_stmt = (
        select(PortfolioRow.cash)
        .join(InvestmentPortfolioRow, InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id)
        .where(InvestmentPortfolioRow.account_id == account_id)
    )
    cash_total = sum((c for c in (await session.execute(cash_stmt)).scalars().all()), Decimal("0"))
    assert ledger_total == cash_total, f"Σ ledger={ledger_total} != Σ cash={cash_total}"


async def _cleanup(factory: async_sessionmaker[AsyncSession], account_id: str) -> None:
    """Cierra y borra la cuenta (y sus dos carteras) — best-effort con postcondición."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    async with factory() as s:
        repo = SqlAlchemyAccountRepository(s)
        await repo.close_account(account_id)
        await repo.delete_simulated_account(account_id)
        await s.commit()
        remaining = await s.get(InvestmentAccountRow, account_id)
        if remaining is not None:
            raise AssertionError(
                f"cleanup incompleto: la cuenta {account_id} sigue existiendo"
            )


@pytest.mark.asyncio
async def test_same_account_two_portfolios_concurrent_ledger_sequence() -> None:
    """Dos carteras de la MISMA cuenta, depósitos concurrentes → ``executed_at`` estricto.

    Sin el ``lock_account``, dos escritores de carteras distintas de la misma cuenta pueden
    leer el mismo ``MAX(executed_at)`` y emitir asientos con idéntico instante. Este test
    repite varias ráfagas concurrentes y verifica que nunca ocurre.
    """
    async with _factory() as factory:
        tag = f"mp{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, p1_legacy, p1_inv, p2_legacy, p2_inv = await _create_account_two_portfolios(
                setup, tag
            )
            await setup.commit()

        try:
            for burst in range(_BURSTS):
                tasks = []
                for i in range(_OPS_PER_PORTFOLIO):
                    tasks.append(
                        _portfolio_deposit_worker(
                            factory, account_id, p1_legacy, p1_inv, 1.0,
                            f"mp-p1-{burst}-{i}-{uuid4().hex}",
                        )
                    )
                    tasks.append(
                        _portfolio_deposit_worker(
                            factory, account_id, p2_legacy, p2_inv, 1.0,
                            f"mp-p2-{burst}-{i}-{uuid4().hex}",
                        )
                    )
                await asyncio.gather(*tasks)
                async with factory() as check:
                    await _verify(check, account_id)
        finally:
            await _cleanup(factory, account_id)
