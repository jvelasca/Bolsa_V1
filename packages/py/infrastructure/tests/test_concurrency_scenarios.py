"""R-9.7 (F7) — suite de concurrencia e invariantes (escenarios de ataque) contra PG real.

Escenarios cubiertos (posgreSQL real, patrón ``db_session`` de
``test_r8a_idempotency_backstop.py``; ``pytest.skip`` si no hay DB):

- **Aislamiento A/B (misma key, distintas cuentas):** dos cuentas usan la MISMA
  ``idempotency_key``/``reference_id`` → cada cuenta ingresa su importe (una fila
  chacune). Verifica a nivel repo que hay 2 registros, uno por cuenta. La semántica
  F1 (lookup por cuenta+type alineado con el UNIQUE por-cuenta) hace LEGÍTIMA la misma
  key en otra cuenta.

- **Deposit+withdraw racing en la MISMA cuenta:** un depósito y un retiro lanzados con
  ``asyncio.gather`` sobre sits/sessions independientes que comparten la cuenta →
  en el final el saldo es coherente con las operaciones aplicadas y el ledger encadena
  (``balance_after``). Sin sleeps: la serialización la garantiza ``with_for_update``
  (M1) sobre la fila de cartera y el guard de idempotencia; si hubiera colisión
  idempotente, se acepta que se aplica UNA sola vez.

- **BUY+SELL racing sobre la MISMA posición:** dos trades simultáneos sobre el mismo
  instrumento/cuenta (uno buy, uno sell) → invariantes ``quantity >= 0`` y ``cash >= 0``
  tras ambos, sin doble-gasto, usando ``with_for_update`` sobre la fila de cartera (M1)
  como hace ``test_financial_invariants.py``.

- **Custody+trade racing:** se une al flujo real de custodia (``ApplyCustodyFees``) y a
  un trade de compra, lanzándolos concurrentes sobre el mismo cash. Verifica que NO hay
  doble cargo de custodia (lo blinda el UNIQUE ``(account_id, custody, custody-YYYY,
  fee)``) y que el estado queda coherente (``Σ ledger == Σ cash`` y la cadena
  ``balance_after`` encadena). Véase la nota en el test sobre por qué no se fuerza el
  timing exacto de la carrera.

Criterio global: NO se usa ``time.sleep`` salvo excepciones documentadas; se usan
barreras ``asyncio``/transacciones. El perdedor de cada carrera no deja efectos
laterales (nada a medias). Cada test limpia el estado que crea (cuentas/instrumentos).
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
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_domain.account_settings import AccountSettings
from bolsa_infrastructure.database.models import (
    InstrumentRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
    PositionRow,
    TransactionRow,
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


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Sesión aislada sobre PostgreSQL REAL; ``pytest.skip`` si no hay DB.

    Al cerrar hace ``rollback`` para no dejar estado (esquema limpio por test).
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
    async with factory() as session:
        try:
            yield session
            await session.rollback()
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


@asynccontextmanager
async def _factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Engine nuevo + session_factory para escenarios concurrentes reales.

    Necesario porque un escenario con ``asyncio.gather`` requiere sesiones/tasks
    INDEPENDIENTES (transacciones separadas) sobre el mismo engine. Comprueba que
    PostgreSQL responde y hace ``pytest.skip`` si no está disponible. El engine se
    cierra al salir del contexto.
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


async def _make_cuenta_cartera_instrumento(
    session: AsyncSession, tag: str
) -> tuple[str, str, str, str]:
    """Crea cuenta simulada + cartera seed + instrumento.

    Devuelve (account_id, legacy_pf_id, investment_pf_id, instrument_id). El ledger
    usa el ``investment_pf_id`` (FK a ``investment_portfolios``); el trade usa la
    ``legacy_pf_id``. El seed de cuenta deja una fila ``deposit`` de ``+initial_deposit``
    en el ledger (misma semántica que el repo de producción).
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"F7 {tag}",
        initial_deposit=100_000.0,
    )
    legacy_pf_id = scope.portfolio.legacy_portfolio_id
    if not legacy_pf_id:
        raise AssertionError("cartera seed sin legacy_portfolio_id")

    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"F7{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"F7{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"F7 {tag}",
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


def _settings_with_custody(pct: float) -> AccountSettings:
    from bolsa_domain.account_settings import settings_from_dict

    return settings_from_dict(
        {"commission": {"custodyAnnualPct": pct}, "tax": {"costBasisMethod": "FIFO"}}
    )


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


def _check_ledger_chain(rows: list[LedgerEntryRow]) -> None:
    """Invariante ``balance_after`` **secuencial por fila** sobre una secuencia ordenada.

    Regla (R-10 F3): ``balance_after[n] == balance_after[n-1] + amount[n]`` para TODA
    fila, arrancando desde ``prev_balance = 0``. Ya no hay grupos atómicos trade+fee
    que compartan balance_after: la fila ``trade`` escribe cash sin fee y la fila
    ``fee`` encadena el cash final (semántica ``ExecuteTrade``/``append_fee``).
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
    """Borra la cuenta simulada (cierre+delete via repo) y el instrumento creado.

    Best-effort dentro de un try/except para no enmascarar fallos del propio test.
    ``delete_simulated_account`` requiere la cuenta cerrada (conservación contable).
    """
    from sqlalchemy import delete

    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    repo = SqlAlchemyAccountRepository(session)
    try:
        await repo.close_account(account_id)
        await repo.delete_simulated_account(account_id)
        # El instrumento no queda referenciado tras borrar posiciones/transacciones.
        await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
        await session.commit()
    except Exception:  # noqa: BLE001 - cleanup best-effort
        await session.rollback()


async def _new_account_with_custody(
    session: AsyncSession, tag: str, pct: float
) -> tuple[str, str, str, str]:
    """Cuenta simulada con custodia habilitada + instrumento (para custody+trade)."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"F7 {tag}",
        initial_deposit=100_000.0,
        settings=_settings_with_custody(pct),
    )
    legacy_pf_id = scope.portfolio.legacy_portfolio_id
    assert legacy_pf_id is not None
    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"F7{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"F7{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"F7 {tag}",
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


# ---------------------------------------------------------------------------
# 1) Aislamiento A/B: la MISMA key en dos cuentas distintas es LEGÍTIMA.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_misma_key_distintas_cuentas_filas_independientes(
    db_session: AsyncSession,
) -> None:
    """La misma ``idempotency_key``/``reference_id`` en A y B produce 1 fila chacune.

    En deposit, la key se usa como ``reference_id='external'``. El UNIQUE es
    por-cuenta+type (migración 004) y el lookup F1 por cuenta+type → la misma key en
    otra cuenta es legítima y debe ingresar en ambas.
    """
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_a, _, pf_a, _ = await _make_cuenta_cartera_instrumento(db_session, "isoA")
    account_b, _, pf_b, _ = await _make_cuenta_cartera_instrumento(db_session, "isoB")
    repo = SqlAlchemyLedgerRepository(db_session)

    shared_key = "f7-isoar-shared-key-1"
    entry_a = await repo.append_cash_movement(
        account_id=account_a,
        portfolio_id=pf_a,
        entry_type="deposit",
        amount=500.0,
        currency="EUR",
        balance_after=100_500.0,
        reference_id=shared_key,
        reference_type="external",
        description="dep A",
    )
    entry_b = await repo.append_cash_movement(
        account_id=account_b,
        portfolio_id=pf_b,
        entry_type="deposit",
        amount=750.0,
        currency="EUR",
        balance_after=100_750.0,
        reference_id=shared_key,
        reference_type="external",
        description="dep B",
    )
    assert entry_a.id and entry_b.id

    # Lookup por cuenta+type (F1): cada cuenta encuentra SU movimiento original.
    found_a = await repo.find_cash_movement_by_reference(
        "external", shared_key, account_id=account_a, type="deposit"
    )
    found_b = await repo.find_cash_movement_by_reference(
        "external", shared_key, account_id=account_b, type="deposit"
    )
    assert found_a is not None and found_b is not None
    assert found_a.account_id == account_a
    assert found_b.account_id == account_b
    assert found_a.amount == 500.0 and found_b.amount == 750.0

    # Una fila por cuenta para la misma key → 2 registros en total.
    count = (
        await db_session.execute(
            select(func.count(LedgerEntryRow.id)).where(
                LedgerEntryRow.reference_type == "external",
                LedgerEntryRow.reference_id == shared_key,
                LedgerEntryRow.type == "deposit",
            )
        )
    ).scalar_one()
    assert int(count) == 2, f"esperaba 2 filas (una por cuenta), obtuve {count}"


# ---------------------------------------------------------------------------
# 2) Deposit + withdraw racing en la MISMA cuenta.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_deposit_withdraw_racing_misma_cuenta() -> None:
    """Depósito y retiro concurrentes sobre la misma cuenta → saldo final coherente.

    Dos tasks independientes (``asyncio.gather``) depositan y retiran usando los
    use-cases reales ``DepositCashToAccount`` y ``WithdrawCashFromAccount``. Cada uno
    abre su propia sesión y serializa sobre la fila de cartera con ``with_for_update``
    (M1), sin sleeps. Cualquiera que sea el orden, el saldo final y la cadena
    ``balance_after`` del ledger son coherentes (sin dinero fantasma).

    Usamos keys distintas (deposit vs withdrawal son ``type`` distintos → no colisionan
    con el UNIQUE). Si ambas intentaran la MISMA key en el mismo ``type``, el guard de
    idempotencia + UNIQUE aplicaría UNA sola vez; aquí el interés es la coherencia entre
    dos operaciones distintas que compiten por el cash.
    """
    async with _factory() as factory:
        tag = f"dw{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, _, _, instrument_id = await _make_cuenta_cartera_instrumento(
                setup, tag
            )
            await setup.commit()

        from bolsa_application.accounts import (
            DepositCashToAccount,
            WithdrawCashFromAccount,
        )
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )
        from bolsa_infrastructure.database.repositories.ledger_repository import (
            SqlAlchemyLedgerRepository,
        )
        from bolsa_infrastructure.database.repositories.portfolio_repository import (
            SqlAlchemyPortfolioRepository,
        )

        async def _deposit() -> float:
            async with factory() as s:
                uc = DepositCashToAccount(
                    SqlAlchemyAccountRepository(s),
                    SqlAlchemyPortfolioRepository(s),
                    SqlAlchemyLedgerRepository(s),
                )
                res = await uc.execute(
                    account_id,
                    amount=10_000.0,
                    idempotency_key=f"{tag}-dep",
                )
                await s.commit()
                return res.balance_after

        async def _withdraw() -> float:
            async with factory() as s:
                uc = WithdrawCashFromAccount(
                    SqlAlchemyAccountRepository(s),
                    SqlAlchemyPortfolioRepository(s),
                    SqlAlchemyLedgerRepository(s),
                )
                res = await uc.execute(
                    account_id,
                    amount=5_000.0,
                    idempotency_key=f"{tag}-wd",
                )
                await s.commit()
                return res.balance_after

        bal_dep, bal_wd = await asyncio.gather(_deposit(), _withdraw())

        # El FINAL es orden-independiente: seed 100_000 + dep 10_000 − wd 5_000 = 105_000.
        # Los balance_after individuales devueltos dependen del intercalado real:
        #   - dep primero → bal_dep=110_000, bal_wd=105_000
        #   - wd primero → bal_dep=105_000, bal_wd=95_000
        # Ambos casos cumplen que al menos una operación deja el balance en 105_000 y
        # ninguna bal_after es negativa. Lo robusto es validar el estado FINAL.
        assert bal_dep in (110_000.0, 105_000.0), f"deposit balance inesperado: {bal_dep}"
        assert bal_wd in (95_000.0, 105_000.0), f"withdraw balance inesperado: {bal_wd}"

        async with factory() as check:
            ledger_repo = SqlAlchemyLedgerRepository(check)
            # Σ ledger == Σ cash (M-2): no hay dinero fantasma.
            ledger_total = await ledger_repo.sum_cash_amounts(account_id)
            cash_total = await _account_total_cash(check, account_id)
            assert ledger_total == cash_total == Decimal("105000"), (
                f"Σ ledger={ledger_total} != Σ cash={cash_total}"
            )
            # La cadena balance_after encadena (grupos atómicos).
            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)
            assert rows[-1].balance_after == Decimal("105000")
            await _cleanup(check, account_id, instrument_id)


# ---------------------------------------------------------------------------
# 3) BUY + SELL racing sobre la MISMA posición.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_buy_sell_racing_misma_posicion() -> None:
    """Dos trades simultáneos (buy + sell) sobre la misma posición/cartera.

    Se siembra una posición (buy 10@1000) para que el sell tenga saldo. Luego se lanzan
    en paralelo un buy 20@1000 y un sell 8@1000. Ambos usan ``with_for_update`` sobre la
    fila de cartera y la de posición (M1), por lo que se serializan: el estado final es
    orden-independiente (buy→sell o sell→buy convergen a qty 22 / cash 78000), sin
    doble-gasto y con ``quantity >= 0`` y ``cash >= 0``.
    """
    async with _factory() as factory:
        tag = f"bs{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, legacy_pf_id, _, instrument_id = await _make_cuenta_cartera_instrumento(
                setup, tag
            )
            from bolsa_infrastructure.database.repositories.portfolio_repository import (
                SqlAlchemyPortfolioRepository,
            )

            seed = await SqlAlchemyPortfolioRepository(setup).execute_trade(
                instrument_id=instrument_id,
                trade_type="buy",
                quantity=10,
                price=1000.0,
                legacy_portfolio_id=legacy_pf_id,
            )
            assert seed.transaction.id
            await setup.commit()

        from bolsa_infrastructure.database.repositories.portfolio_repository import (
            SqlAlchemyPortfolioRepository,
        )

        async def _buy() -> None:
            async with factory() as s:
                await SqlAlchemyPortfolioRepository(s).execute_trade(
                    instrument_id=instrument_id,
                    trade_type="buy",
                    quantity=20,
                    price=1000.0,
                    legacy_portfolio_id=legacy_pf_id,
                    idempotency_key=f"{tag}-buy",
                )
                await s.commit()

        async def _sell() -> None:
            async with factory() as s:
                await SqlAlchemyPortfolioRepository(s).execute_trade(
                    instrument_id=instrument_id,
                    trade_type="sell",
                    quantity=8,
                    price=1000.0,
                    legacy_portfolio_id=legacy_pf_id,
                    idempotency_key=f"{tag}-sell",
                )
                await s.commit()

        await asyncio.gather(_buy(), _sell())

        async with factory() as check:
            portfolio_row = await check.get(PortfolioRow, legacy_pf_id)
            assert portfolio_row is not None
            pos_row = (
                await check.execute(
                    select(PositionRow).where(
                        PositionRow.portfolio_id == legacy_pf_id,
                        PositionRow.instrument_id == instrument_id,
                    )
                )
            ).scalar_one_or_none()
            qty = float(pos_row.quantity) if pos_row is not None else 0.0
            cash = float(portfolio_row.cash)
            assert qty == 22.0, f"qty final inesperada: {qty}"
            assert cash == 78_000.0, f"cash final inesperado: {cash}"
            assert qty >= 0.0 and cash >= 0.0
            # Ambos trades se aplicaron UNA sola vez (2 transacciones de la race).
            count = (
                await check.execute(
                    select(func.count(TransactionRow.id)).where(
                        TransactionRow.portfolio_id == legacy_pf_id,
                        TransactionRow.idempotency_key.in_([f"{tag}-buy", f"{tag}-sell"]),
                    )
                )
            ).scalar_one()
            assert int(count) == 2, f"esperaba 2 transacciones, obtuve {count}"
            await _cleanup(check, account_id, instrument_id)


# ---------------------------------------------------------------------------
# 4) Custody + trade racing.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_custody_trade_racing_no_doble_cargo() -> None:
    """Un GET de custodia y un trade chocan por el cash; sin doble cargo ni incoherencia.

    Se lanzan de forma concurrente (``asyncio.gather``) el flujo real de custodia
    (``ApplyCustodyFees.execute``) y un trade buque (``ExecuteTrade``) sobre la misma
    cuenta/cartera. Ambos mutan el mismo ``PortfolioRow`` (``with_for_update``).

    # Nota de carrera: no forzamos el timing exacto para que custodia y trade lleguen
    # a la vez al SAVEPOINT (haría el test determinista a costa de acoplarse al
    # intercalado interno). En su lugar, garantizamos la POSTCONDICIÓN: la custodia del
    # periodo se aplica a lo sumo UNA vez (lo blinda el UNIQUE por-cuenta+periodo y el
    # guard durable del ledger), el trade aplica una vez, y el estado queda coherente
    # (``Σ ledger == Σ cash`` + cadena ``balance_after`` encadena sin dinero fantasma).
    # La propia atomicidad (mismo AsyncSession por request) garantiza que el perdedor
    # de cualquier colisión de custodia no deja cash descontado sin fila.
    """
    async with _factory() as factory:
        tag = f"ct{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, legacy_pf_id, _, instrument_id = await _new_account_with_custody(
                setup, tag, 0.2
            )
            await setup.commit()

        from bolsa_application.accounts import ApplyCustodyFees, ExecuteTrade
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )
        from bolsa_infrastructure.database.repositories.ledger_repository import (
            SqlAlchemyLedgerRepository,
        )
        from bolsa_infrastructure.database.repositories.portfolio_repository import (
            SqlAlchemyPortfolioRepository,
        )

        async def _custody() -> bool:
            async with factory() as s:
                acc = SqlAlchemyAccountRepository(s)
                scope = await acc.resolve_scope(account_id)
                applied = await ApplyCustodyFees(
                    acc,
                    SqlAlchemyPortfolioRepository(s),
                    SqlAlchemyLedgerRepository(s),
                ).execute(scope)
                await s.commit()
                return applied

        async def _trade() -> None:
            async with factory() as s:
                acc = SqlAlchemyAccountRepository(s)
                await ExecuteTrade(
                    acc,
                    SqlAlchemyPortfolioRepository(s),
                    SqlAlchemyLedgerRepository(s),
                ).execute(
                    instrument_id=instrument_id,
                    trade_type="buy",
                    quantity=10,
                    price=500.0,
                    account_id=account_id,
                    idempotency_key=f"{tag}-trade",
                )
                await s.commit()

        gathered = await asyncio.gather(_custody(), _trade())
        custody_applied = gathered[0]
        assert custody_applied is True, "la custodia debería haberse aplicado en el periodo"

        async with factory() as check:
            ledger_repo = SqlAlchemyLedgerRepository(check)
            period = _now().strftime("%Y")

            # Custodia del periodo: exactamente 1 fila (UNIQUE blinda el doble cargo).
            cust_count = (
                await check.execute(
                    select(func.count(LedgerEntryRow.id)).where(
                        LedgerEntryRow.account_id == account_id,
                        LedgerEntryRow.reference_type == "custody",
                        LedgerEntryRow.reference_id == f"custody-{period}",
                    )
                )
            ).scalar_one()
            assert int(cust_count) == 1, f"cargo de custodia duplicado: {cust_count}"

            # Coherencia: Σ ledger == Σ cash + cadena balance_after encadena.
            ledger_total = await ledger_repo.sum_cash_amounts(account_id)
            cash_total = await _account_total_cash(check, account_id)
            assert ledger_total == cash_total, (
                f"Σ ledger={ledger_total} != Σ cash={cash_total}"
            )
            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)

            # qty del trade >= 0.
            pos_row = (
                await check.execute(
                    select(PositionRow).where(
                        PositionRow.portfolio_id == legacy_pf_id,
                        PositionRow.instrument_id == instrument_id,
                    )
                )
            ).scalar_one_or_none()
            qty = float(pos_row.quantity) if pos_row is not None else 0.0
            assert qty == 10.0, f"qty final del trade inesperada: {qty}"
            assert qty >= 0.0
            await _cleanup(check, account_id, instrument_id)
