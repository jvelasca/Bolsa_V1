"""Fase 4 (post-v1.3.0) — crash-consistency: atomicidad real bajo kill / cierre brusco.

Este es un test-espejo de la auditoría de crash-consistency contra PostgreSQL REAL
(docker ``bolsa-postgres``). Verifica los TRES "kill points" que la auditoría pidió,
usando los MISMOS repos reales de producción aislados en una cuenta simulada:

1. ``BEGIN → UPDATE cash (deduct 1000) → KILL/cierre brusco ANTES de INSERT ledger``
   → debe quedar ROLLBACK: cash vuelve al valor inicial y NO hay fila ledger extra.
2. ``BEGIN → UPDATE cash → INSERT ledger → KILL ANTES de COMMIT`` → ROLLBACK: cash
   inicial y sin fila ledger (ningún estado parcial / nada a medias).
3. ``BEGIN → UPDATE cash → INSERT ledger → COMMIT`` (control) → cash descontado y
   1 fila ledger persistida, cumpliendo las invariantes A (``Σ ledger == Σ cash``) y
   B (cadena ``balance_after`` secuencial).

Cómo se simula el "kill" (método elegido, ver cada test): con SQLAlchemy async +
psycopg la forma de producir atomicidad real es abandonar la transacción SIN ``commit``,
bien con ``session.rollback()`` explícito del work pendiente, bien cerrando la conexión
descartando el work (ROLLBACK implícito al desconectar). NO se mata el SO realmente
(no es un proceso externo): la tesis es que CUALQUIER ruta que abandone la transacción
sin commit no puede dejar estado parcial. Tras cada "kill" se reabre una SESIÓN LIMPIA
(distinta del motor/transacción que se "mató") para verificar el estado PERSISTIDO
(vale el invisibilidad del trabajo descartado: cash == valor inicial, count de ledger
del account == el que había, ``Σ ledger == Σ cash`` y cadena ``balance_after`` coherente).

Patrón heredado de ``test_custody_concurrency_chaos.py`` / ``test_concurrency_scenarios.py``:
``pytest.skip`` si no hay PostgreSQL, ``asyncio.WindowsSelectorEventLoopPolicy`` en
Windows (psycopg async no soporta Proactor), ``_factory()`` con engine/session-factory
aislados. Cada escenario limpia la cuenta simulada que crea vía ``close_account`` +
``delete_simulated_account`` (camino canónico) y borra el instrumento, best-effort.
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
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_infrastructure.database.models import (
    InstrumentRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


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
    """Engine nuevo + session_factory aislados para los escenarios.

    Abre el engine apuntando a ``DATABASE_URL`` (que en este paquete es la DB caótica
    ``bolsa_v1_chaos`` vía la variable de entorno, con prioridad sobre ``.env``). Hace
    ``pytest.skip`` si PostgreSQL no responde. El engine se cierra al salir.
    """
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
    try:
        yield factory
    finally:
        await engine.dispose()


def _now() -> datetime:
    return datetime.now(UTC)


async def _new_simulated(
    session: AsyncSession, tag: str, *, initial_deposit: float = 10_000.0
) -> tuple[str, str, str, str]:
    """Cuenta simulada real + instrumento. Devuelve (account, legacy_pf, inv_pf, inst)."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"CRASH {tag}",
        initial_deposit=initial_deposit,
    )
    legacy_pf_id = scope.portfolio.legacy_portfolio_id
    assert legacy_pf_id is not None

    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"CH{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"CH{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"CRASH {tag}",
        exchange="BMAD",
        country="ES",
        currency="EUR",
        type="stock",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(instrument)
    await session.flush()
    return scope.account.id, legacy_pf_id, scope.portfolio.id, instrument.id


async def _account_total_cash(session: AsyncSession, account_id: str) -> Decimal:
    """Cash del account = Σ ``PortfolioRow.cash`` de sus legacy portfolios."""
    stmt = (
        select(PortfolioRow.cash)
        .join(
            InvestmentPortfolioRow,
            InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
        )
        .where(InvestmentPortfolioRow.account_id == account_id)
    )
    cash_values = (await session.execute(stmt)).scalars().all()
    return sum((c for c in cash_values), Decimal("0"))


async def _count_ledger(session: AsyncSession, account_id: str) -> int:
    stmt = (
        select(func.count(LedgerEntryRow.id)).where(
            LedgerEntryRow.account_id == account_id,
        )
    )
    return int((await session.execute(stmt)).scalar_one())


def _check_ledger_chain(rows: list[LedgerEntryRow]) -> None:
    """Invariante ``balance_after`` secuencial por fila (B), desde ``prev_balance = 0``.

    ``balance_after[n] == balance_after[n-1] + amount[n]`` para TODA fila ordenada por
    ``executed_at, id``. Reutiliza la semántica de ``test_concurrency_scenarios``.
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


async def _load_sorted_rows(session: AsyncSession, account_id: str) -> list[LedgerEntryRow]:
    stmt = (
        select(LedgerEntryRow)
        .where(LedgerEntryRow.account_id == account_id)
        .order_by(LedgerEntryRow.executed_at, LedgerEntryRow.id)
    )
    return list((await session.execute(stmt)).scalars())


async def _cleanup(session: AsyncSession, account_id: str, instrument_id: str) -> None:
    """Borra la cuenta simulada (cierre+delete via repo) y el instrumento, best-effort."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    repo = SqlAlchemyAccountRepository(session)
    try:
        await repo.close_account(account_id)
        await repo.delete_simulated_account(account_id)
        await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
        await session.commit()
    except Exception:  # noqa: BLE001 - cleanup best-effort
        await session.rollback()


# ---------------------------------------------------------------------------
# Kill point 1: BEGIN → UPDATE cash → KILL antes de INSERT ledger.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kill_after_cash_deduct_before_ledger_insert() -> None:
    """Kill POINT 1: tras deducir cash SIN escribir ledger, el rollback anula TODO.

    Secuencia: ``BEGIN → deduct_cash(legacy, 1000) → KILL``. El KILL se simula con
    ``await session.rollback()`` (la misma operación que el driver psycopg emite al
    desconectarse/abandonar la transacción con work pendiente, es decir lo que pasa ante
    un kill O/S de la conexión). No hay COMMIT y, crucialmente, NO llegó a ejecutarse el
    ``INSERT`` de ledger: la única mutación fue el ``UPDATE`` de cash.

    Postcondición: en una sesión LIMPIA el estado PERSISTIDO es indistinguible de "nunca
    se intentó" — cash == 10000 (valor inicial, NO 9000) y ``count(ledger)`` == 1 (solo el
    seed de depósito, sin fila parcial). ``Σ ledger == Σ cash`` y la cadena encaja.
    """
    async with _factory() as factory:
        tag = f"k1{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, legacy_pf_id, _inv_pf_id, inst_id = await _new_simulated(
                setup, tag, initial_deposit=10_000.0
            )
            await setup.commit()

        # Transacción "operacional": mutamos cash con el repo REAL y la abandonamos.
        async with factory() as killing:
            from bolsa_infrastructure.database.repositories.portfolio_repository import (
                SqlAlchemyPortfolioRepository,
            )

            await SqlAlchemyPortfolioRepository(killing).deduct_cash(legacy_pf_id, 1000.0)
            assert await _account_total_cash(killing, account_id) == Decimal("9000")
            # KILL: cerrar sin commit → ROLLBACK implícito/explicito de todo el work.
            await killing.rollback()

        # Sesión limpia para verificar el estado real persistido (nada que ver).
        async with factory() as check:
            assert await _account_total_cash(check, account_id) == Decimal("10000")
            assert await _count_ledger(check, account_id) == 1
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            ledger_repo = SqlAlchemyLedgerRepository(check)
            ledger_total = await ledger_repo.sum_cash_amounts(account_id)
            cash_total = await _account_total_cash(check, account_id)
            assert ledger_total == cash_total == Decimal("10000"), (
                f"Σ ledger={ledger_total} != Σ cash={cash_total} tras el kill"
            )
            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)
            await _cleanup(check, account_id, inst_id)


# ---------------------------------------------------------------------------
# Kill point 2: BEGIN → UPDATE cash → INSERT ledger → KILL antes de COMMIT.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kill_after_ledger_insert_before_commit() -> None:
    """Kill POINT 2: tras escribir ledger SIN commit, el rollback no deja NADA a medias.

    Secuencia: ``BEGIN → deduct_cash(legacy, 1000) → append_trade → KILL``. Es el caso
    más crítico de atomicidad: hay DOS efectos (``UPDATE cash`` a 9000 + ``INSERT`` una
    fila ledger ``-1000``) escritos en la misma transacción, pero ninguno se confirmó. Se
    simula el kill con ``await session.rollback()`` (equivalente a que el O/S mate la
    conexión dejando la transacción abierta y pendiente → ROLLBACK al cerrar).

    Postcondición: en una sesión LIMPIA NO hay estado parcial — cash == 10000 (inicial) y
    ``count(ledger)`` == 1 (solo el seed; la fila ledger del trade no existe). No puede
    quedar cash descontado sin fila, ni fila sin cash descontado.
    """
    async with _factory() as factory:
        tag = f"k2{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, legacy_pf_id, inv_pf_id, inst_id = await _new_simulated(
                setup, tag, initial_deposit=10_000.0
            )
            await setup.commit()

        async with factory() as killing:
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )
            from bolsa_infrastructure.database.repositories.portfolio_repository import (
                SqlAlchemyPortfolioRepository,
            )

            tx_id = f"k2-{uuid4().hex}"
            await SqlAlchemyPortfolioRepository(killing).deduct_cash(legacy_pf_id, 1000.0)
            await SqlAlchemyLedgerRepository(killing).append_trade(
                account_id=account_id,
                portfolio_id=inv_pf_id,
                entry_type="trade",
                amount=-1000.0,
                currency="EUR",
                balance_after=9000.0,
                instrument_id=inst_id,
                quantity=10,
                price=100.0,
                reference_id=tx_id,
            )
            # Ambos efectos están en la transacción SIN commit → KILL = rollback.
            await killing.rollback()

        async with factory() as check:
            assert await _account_total_cash(check, account_id) == Decimal("10000")
            assert await _count_ledger(check, account_id) == 1
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            ledger_repo = SqlAlchemyLedgerRepository(check)
            ledger_total = await ledger_repo.sum_cash_amounts(account_id)
            cash_total = await _account_total_cash(check, account_id)
            assert ledger_total == cash_total == Decimal("10000"), (
                f"Σ ledger={ledger_total} != Σ cash={cash_total} tras el kill"
            )
            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)
            await _cleanup(check, account_id, inst_id)


# ---------------------------------------------------------------------------
# Kill point 3 (control): BEGIN → UPDATE cash → INSERT ledger → COMMIT.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_control_commit_persists_deduct_and_ledger() -> None:
    """Control (kill point 3): con COMMIT el efecto queda persistido y consistente.

    Misma secuencia que el punto 2 pero cerrada con ``await session.commit()``: deducir
    1000 de cash y escribir una fila ledger ``-1000``. La postcondición es la simétrica:
    cash == 9000 y ``count(ledger)`` == 2 (seed + trade persistido), y se cumplen las
    invariantes a nivel persistido — A ``Σ ledger == Σ cash == 9000`` y B la cadena
    ``balance_after`` encadena (deposit 10000 → trade 9000). Demuestra que la atomicidad
    observada en los puntos 1 y 2 es real: es el COMMIT el que hace visibles ambos lados.
    """
    async with _factory() as factory:
        tag = f"c3{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, legacy_pf_id, inv_pf_id, inst_id = await _new_simulated(
                setup, tag, initial_deposit=10_000.0
            )
            await setup.commit()

        async with factory() as tx:
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )
            from bolsa_infrastructure.database.repositories.portfolio_repository import (
                SqlAlchemyPortfolioRepository,
            )

            tx_id = f"c3-{uuid4().hex}"
            await SqlAlchemyPortfolioRepository(tx).deduct_cash(legacy_pf_id, 1000.0)
            await SqlAlchemyLedgerRepository(tx).append_trade(
                account_id=account_id,
                portfolio_id=inv_pf_id,
                entry_type="trade",
                amount=-1000.0,
                currency="EUR",
                balance_after=9000.0,
                instrument_id=inst_id,
                quantity=10,
                price=100.0,
                reference_id=tx_id,
            )
            await tx.commit()

        async with factory() as check:
            assert await _account_total_cash(check, account_id) == Decimal("9000")
            assert await _count_ledger(check, account_id) == 2
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            ledger_repo = SqlAlchemyLedgerRepository(check)
            ledger_total = await ledger_repo.sum_cash_amounts(account_id)
            cash_total = await _account_total_cash(check, account_id)
            assert ledger_total == cash_total == Decimal("9000"), (
                f"Σ ledger={ledger_total} != Σ cash={cash_total} (control)"
            )
            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)
            await _cleanup(check, account_id, inst_id)
