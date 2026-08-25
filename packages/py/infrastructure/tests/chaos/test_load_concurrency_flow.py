"""Fase 5 (post-v1.3.0) — concurrencia masiva / carga contra PostgreSQL REAL aislado.

Conjunto de tests de ESTRÉS de carga sobre la DB aislada ``bolsa_v1_chaos`` (
NUNCA la dev real). Cada escenario lanza un GRAN número de operaciones
``asyncio.gather`` (sesiones/transacciones INDEPENDIENTES) sobre la MISMA cuenta y,
tras cada uno, verifica las invariantes:

- **Invariante A** (M-2): ``Σ ledger.amount == cash`` (sin dinero fantasma).
- **Invariante B** (cadena ``balance_after``): encadenado ESTRICTO
  ``balance_after[n] == balance_after[n-1] + amount[n]`` vía ``_check_ledger_chain`` /
  ``_assert_chain_concurrent`` (alias post EXEC-B-CONC). Deposit/withdraw y
  ``ExecuteTrade`` escriben ``balance_after`` desde cash bajo lock (post-lock /
  summary); ``executed_at`` se genera con el lock de cartera aún retenido hasta
  commit → orden ``(executed_at, id)`` alineado con el orden de aplicación.
- **cash >= 0** y **quantity >= 0** siempre.

Se usa el patrón real (no dobles del código): los use-cases de ``bolsa_application``
sobre los repos SQLAlchemy reales, exactamente igual que ``test_custody_concurrency_chaos.py``.
La serialización NO usa ``time.sleep``: la dan los ``with_for_update`` (M1) sobre la
fila de cartera/posición + el guard de idempotencia + UNIQUE.

Escenarios cubiertos (cifras documentadas en el docstring de cada test):

1. **500 depósitos simultáneos** sobre la misma cuenta (misma cartera, una fila compartida).
2. **500 retiradas simultáneas** que NO pueden caber todas → el guard
   ``allow_partial=False``/efectivo insuficiente rechaza (``ValueError``) las que no
   quepan; cash NUNCA negativa.
3. **500 BUY + 500 SELL simultáneos** sobre la misma posición → ``cash >= 0`` y
   ``quantity >= 0`` siempre.
4. **BUY+SELL simultáneos** y **custodia+BUY simultáneos** (combinación de 2 operaciones
   distintas concurrentes) → invariantes A/B, sin doble cargo de custodia.

Patrón heredado de ``test_custody_concurrency_chaos.py``: ``pytest.skip`` si no hay
PostgreSQL, ``asyncio.WindowsSelectorEventLoopPolicy`` en Windows (psycopg async no
soporta Proactor), ``_factory()`` con engine/session-factory aislados. Cada test crea
cuentas simuladas y las limpia SIEMPRE al final (``close_account`` +
``delete_simulated_account``, camino canónico) para no dejar residuos en ``bolsa_v1_chaos``.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from bolsa_domain.account_settings import AccountSettings
from bolsa_infrastructure.database.models import (
    InstrumentRow,
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
    PositionRow,
)

if TYPE_CHECKING:
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )


# psycopg async no soporta ProactorEventLoop en Windows (convención de infra).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# Cifras "masivas pero ejecutables". Cada test se ejecuta contra PostgreSQL real y
# todas las operaciones de un escenario se serializan sobre UNA fila de cartera/posición
# (with_for_update M1). 500 × operación en una sola fila ≈ unos pocos segundos reales.
# En caso de hardware lento se puede rebajar aplicando la misma resta a todas las
# constantes, pero no por debajo de un umbral que deje de demostrar estrés (>= 200).
_DEPOSIT_COUNT = 500
_WITHDRAW_COUNT = 500
_TRADE_COUNT = 500  # 500 BUY + 500 SELL
_MIX_COUNT = 100  # combo BUY+SELL / custodia+BUY


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
    """Engine nuevo + session_factory aislados para escenarios concurrentes reales.

    Necesario porque un escenario con ``asyncio.gather`` requiere sesiones/tasks
    INDEPENDIENTES (transacciones separadas) sobre el mismo engine. Apunta a
    ``DATABASE_URL`` (DB aislada ``bolsa_v1_chaos`` de este paquete, prioridad sobre
    ``.env``) y hace ``pytest.skip`` si PostgreSQL no está disponible. Se cierra al salir.

    Usa un pool AMPLIO (``pool_size=64``, ``max_overflow=0``) a diferencia del engine de
    producción (default 5+10): las ráfagas de -- cientos-filas-``asyncio.gather`` de este
    test (p.ej. 500 BUY + 500 SELL) abren cientos de sesiones a la vez y con el default
    agotarían el pool (``QueuePool limit reached``). Un pool amplio es la configuración
    razonable para un test de estrés; el número de conexiones a PostgreSQL sigue siendo
    finito y acotado por ``pool_size``.
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
        pool_size=64,
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


async def _assert_reconciled(
    session: AsyncSession,
    ledger_repo: SqlAlchemyLedgerRepository,
    account_id: str,
    *,
    expected_cash: Decimal | None = None,
) -> None:
    """Invariante A (M-2): ``Σ ledger (sum_cash_amounts) == cash`` del account."""
    ledger_total = await ledger_repo.sum_cash_amounts(account_id)
    cash_total = await _account_total_cash(session, account_id)
    if expected_cash is not None:
        assert cash_total == expected_cash, (
            f"cash={cash_total} != expected={expected_cash}"
        )
    assert ledger_total == cash_total, (
        f"Σ ledger={ledger_total} != Σ cash={cash_total} (account {account_id})"
    )


def _check_ledger_chain(rows: list[LedgerEntryRow]) -> None:
    """Invariante B: ``balance_after`` secuencial por fila, desde ``prev_balance = 0``.

    ``balance_after[n] == balance_after[n-1] + amount[n]`` para TODA fila ordenada por
    ``(executed_at, id)``. Reutiliza la semántica de ``test_custody_concurrency_chaos``.
    Válida en escenarios concurrentes porque ``executed_at`` se genera SIEMPRE tras
    adquirir el lock ``with_for_update`` de la fila → monótono con el orden de aplicación.
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


def _assert_chain_concurrent(rows: list[LedgerEntryRow]) -> None:
    """Invariante B estricta tras EXEC-B-CONC (antes: variante debilitada).

    Pre-fix: ``ExecuteTrade`` leía ``cash_before`` PRE-lock → bajo concurrencia la
    cadena ``order_by(executed_at,id)`` podía descuadrar en O(N) sin violar M-2; este
    helper solo comprobaba ``balance_after >= 0``.

    Post EXEC-B-CONC: ``balance_after`` se deriva del cash post-lock
    (``result.summary.portfolio.cash``) dentro de la misma transacción que retiene
    ``with_for_update`` hasta commit. Misma postcondición que deposit/withdraw →
    delega en ``_check_ledger_chain`` (``balance_after[n] == prev + amount[n]``).
    M-2 se sigue comprobando aparte con ``_assert_reconciled``.
    """
    _check_ledger_chain(rows)


async def _cleanup(session: AsyncSession, account_id: str, instrument_id: str) -> None:
    """Borra la cuenta simulada (cierre+delete via repo) y el instrumento, best-effort.

    No traga fallos en silencio: tras borrar verifica que la cuenta ya no existe y
    re-lanza la excepción real si algo falla, para que un residuo NUNCA pase en verde
    sin avisar (es una postcondición de los chaos tests: ``bolsa_v1_chaos`` debe quedar
    siempre limpia).
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    repo = SqlAlchemyAccountRepository(session)
    await repo.close_account(account_id)
    await repo.delete_simulated_account(account_id)
    await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
    await session.commit()
    # Postcondición: verificación real de que no queda la cuenta.
    remaining = await session.get(
        InvestmentAccountRow,
        account_id,
    )
    if remaining is not None:
        raise AssertionError(
            f"cleanup incompleto: la cuenta simulada {account_id} sigue existiendo"
        )


async def _cleanup_guaranteed(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    instrument_id: str | None,
) -> None:
    """Limpia la cuenta SIEMPRE, incluso si un assert falló antes (sesión limpia nueva).

    Los tests ejecutan ``_cleanup`` dentro de un ``try/finally``: si una verificación
    (assert de invariante) falla, el estado de la sesión de check puede quedar sucio;
    esta rutina abre una SESIÓN NUEVA (``factory()``) para no dejar residuos en
    ``bolsa_v1_chaos``. Si la limpieza NO consigue borrar la cuenta, re-lanza la
    excepción (hace fallar el test) en lugar de dejar un residuo silencioso.
    """
    if instrument_id is None:
        return
    async with factory() as session:
        await _cleanup(session, account_id, instrument_id)


async def _new_account(
    session: AsyncSession,
    tag: str,
    *,
    initial_deposit: float = 0.0,
    custody_pct: float | None = None,
) -> tuple[str, str, str, str]:
    """Cuenta simulada real (+ instrumento). Devuelve (account, legacy_pf, inv_pf, inst).

    ``custody_pct`` si se indica habilita el cobro de custodia anual (escenario 4).
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    settings: AccountSettings | None = None
    if custody_pct is not None:
        settings = _settings_with_custody(custody_pct)

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"LOAD {tag}",
        initial_deposit=initial_deposit,
        settings=settings,
    )
    legacy_pf_id = scope.portfolio.legacy_portfolio_id
    assert legacy_pf_id is not None

    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"LD{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"LD{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"LOAD {tag}",
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


async def _count_ledger_type(
    session: AsyncSession,
    account_id: str,
    entry_type: str,
    reference_type: str = "external",
) -> int:
    stmt = (
        select(func.count(LedgerEntryRow.id))
        .where(
            LedgerEntryRow.account_id == account_id,
            LedgerEntryRow.type == entry_type,
            LedgerEntryRow.reference_type == reference_type,
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def _deposit_worker(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    amount: float,
    key: str,
) -> None:
    """Un depósito real en sesión/transacción independiente."""
    from bolsa_application.accounts import DepositCashToAccount
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
        await DepositCashToAccount(
            SqlAlchemyAccountRepository(s),
            SqlAlchemyPortfolioRepository(s),
            SqlAlchemyLedgerRepository(s),
        ).execute(account_id, amount=amount, idempotency_key=key)
        await s.commit()


async def _withdraw_worker(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    amount: float,
    key: str,
) -> bool:
    """Un retiro real en sesión independiente. Devuelve True si se aplicó, False si se
    rechazó por efectivo insuficiente (``ValueError``) — nunca deja cash negativa."""
    from bolsa_application.accounts import WithdrawCashFromAccount
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
        try:
            await WithdrawCashFromAccount(
                SqlAlchemyAccountRepository(s),
                SqlAlchemyPortfolioRepository(s),
                SqlAlchemyLedgerRepository(s),
            ).execute(account_id, amount=amount, idempotency_key=key)
        except ValueError as exc:
            if "insuficiente" in str(exc).lower():
                await s.rollback()
                return False
            raise
        await s.commit()
        return True


async def _trade_worker(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    instrument_id: str,
    trade_type: str,
    quantity: int,
    price: float,
    key: str,
) -> None:
    """Un trade real (``ExecuteTrade``) en sesión/transacción independiente."""
    from bolsa_application.accounts import ExecuteTrade
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
        await ExecuteTrade(
            SqlAlchemyAccountRepository(s),
            SqlAlchemyPortfolioRepository(s),
            SqlAlchemyLedgerRepository(s),
        ).execute(
            instrument_id=instrument_id,
            trade_type=trade_type,
            quantity=quantity,
            price=price,
            account_id=account_id,
            idempotency_key=key,
        )
        await s.commit()


async def _seed_buy(
    session: AsyncSession,
    account_id: str,
    instrument_id: str,
    quantity: int,
    price: float,
    tag: str,
) -> None:
    """Compra de siembra vía use-case ``ExecuteTrade`` (escribe ledger, mantiene Σ==cash)."""
    from bolsa_application.accounts import ExecuteTrade
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    await ExecuteTrade(
        SqlAlchemyAccountRepository(session),
        SqlAlchemyPortfolioRepository(session),
        SqlAlchemyLedgerRepository(session),
    ).execute(
        instrument_id=instrument_id,
        trade_type="buy",
        quantity=quantity,
        price=price,
        account_id=account_id,
        idempotency_key=f"{tag}-{uuid4().hex}",
    )
    await session.flush()


async def _position_quantity(
    session: AsyncSession, legacy_pf_id: str, instrument_id: str
) -> Decimal:
    stmt = (
        select(PositionRow.quantity)
        .where(
            PositionRow.portfolio_id == legacy_pf_id,
            PositionRow.instrument_id == instrument_id,
        )
    )
    qty = (await session.execute(stmt)).scalar_one_or_none()
    return qty if qty is not None else Decimal("0")


async def _custody_worker(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
) -> bool:
    """Ejecuta ``ApplyCustodyFees.execute`` en una sesión independiente (devuelve applied)."""
    from bolsa_application.accounts import ApplyCustodyFees
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.custody_obligation_repository import (
        CustodyObligationRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    async with factory() as s:
        acc = SqlAlchemyAccountRepository(s)
        scope = await acc.resolve_scope(account_id)
        applied = await ApplyCustodyFees(
            acc,
            SqlAlchemyPortfolioRepository(s),
            SqlAlchemyLedgerRepository(s),
            custody_obligation_repo=CustodyObligationRepository(s),
        ).execute(scope)
        await s.commit()
        return applied


async def _count_custody_entries(session: AsyncSession, account_id: str, period: str) -> int:
    stmt = (
        select(func.count(LedgerEntryRow.id))
        .where(
            LedgerEntryRow.account_id == account_id,
            LedgerEntryRow.reference_type == "custody",
            LedgerEntryRow.reference_id == f"custody-{period}",
        )
    )
    return int((await session.execute(stmt)).scalar_one())


# ---------------------------------------------------------------------------
# Helper de carga en lotes: evita saturar el pool de conexiones del engine.
# ---------------------------------------------------------------------------
_BATCH_SIZE = 200


async def _gather_deposit_batch(
    factory: async_sessionmaker[AsyncSession],
    acc: str,
    keys: list[str],
    amount: float,
) -> None:
    for start in range(0, len(keys), _BATCH_SIZE):
        batch = keys[start : start + _BATCH_SIZE]
        await asyncio.gather(
            *(_deposit_worker(factory, acc, amount, k) for k in batch),
        )


async def _gather_withdraw_batch(
    factory: async_sessionmaker[AsyncSession],
    acc: str,
    keys: list[str],
    amount: float,
) -> list[bool]:
    outcomes: list[bool] = []
    for start in range(0, len(keys), _BATCH_SIZE):
        batch = keys[start : start + _BATCH_SIZE]
        outcomes.extend(await asyncio.gather(*(_withdraw_worker(factory, acc, amount, k) for k in batch)))
    return outcomes


async def _gather_trade_batch(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    instrument_id: str,
    trade_type: str,
    quantity: int,
    price: float,
    keys: list[str],
) -> None:
    for start in range(0, len(keys), _BATCH_SIZE):
        batch = keys[start : start + _BATCH_SIZE]
        await asyncio.gather(
            *(_trade_worker(factory, account_id, instrument_id, trade_type, quantity, price, k) for k in batch),
        )


# ---------------------------------------------------------------------------
# 1) 500 depósitos simultáneos sobre la misma cuenta.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_load_500_simultaneous_deposits() -> None:
    """Escenario 1 — 500 depósitos ``asyncio.gather`` sobre la MISMA cuenta.

    Se crea una cuenta con ``initial_deposit=0`` y se lanzan ``_DEPOSIT_COUNT``
    depósitos de 100 EUR cada uno, cada operación con su ``idempotency_key`` distinta y
    SU PROPIA sesión/transacción independiente (``asyncio.gather``). Sin ``time.sleep``:
    la serialización la da ``add_cash`` con ``with_for_update`` (M1) sobre la única fila
    de cartera + el guard de idempotencia + UNIQUE.

    Postcondiciones (todas verificadas):
    - ``cash == 0 + 500*100 == 50_000`` (cada depósito entra exactamente una vez);
    - Invariante A: ``Σ ledger == Σ cash``;
    - Invariante B: la cadena ``balance_after`` encadena;
    - exactamente 500 filas ledger de tipo ``deposit`` (external).
    """
    async with _factory() as factory:
        tag = f"dep{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, _legacy, _inv, inst_id = await _new_account(
                setup, tag, initial_deposit=0.0
            )
            await setup.commit()

        keys = [f"{tag}-{i}-{uuid4().hex}" for i in range(_DEPOSIT_COUNT)]
        try:
            # Gather dentro del try/finally (ver escenario 3): limpieza garantizada.
            await _gather_deposit_batch(factory, account_id, keys, 100.0)

            async with factory() as check:
                from bolsa_infrastructure.database.repositories.ledger_repository import (
                    SqlAlchemyLedgerRepository,
                )

                ledger_repo = SqlAlchemyLedgerRepository(check)
                # cash == seed (0) + 500*100 == 50_000.
                await _assert_reconciled(
                    check,
                    ledger_repo,
                    account_id,
                    expected_cash=Decimal(str(50_000)),
                )
                assert await _count_ledger_type(
                    check, account_id, "deposit", "external"
                ) == (_DEPOSIT_COUNT)
                rows = await _load_sorted_rows(check, account_id)
                _check_ledger_chain(rows)
        finally:
            await _cleanup_guaranteed(factory, account_id, inst_id)


# ---------------------------------------------------------------------------
# 2) 500 retiradas simultáneas: el guard rechaza las que no caben.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_load_500_simultaneous_withdrawals_never_negative_cash() -> None:
    """Escenario 2 — 500 retiradas simultáneas; cash NUNCA negativa.

    Cuenta con seed 100_000 y 500 retiros de 250 EUR cada uno, con ``asyncio.gather``
    y sesiones independientes. Como 500*250 = 125_000 > seed, NO todos caben: el guard
    ``allow_partial=False`` de ``deduct_cash`` (con ``with_for_update``) y la validación
    previa de ``WithdrawCashFromAccount`` rechazan con ``ValueError`` los retiros que
    dejarían cash negativa → cash queda exactamente en 0 con ``floor(100_000/250) = 400``
    retiros aplicados y ``500 - 400 = 100`` rechazados.

    Postcondiciones:
    - cada intento termina en "aplicado" o "rechazado" (nunca en cash < 0);
    - ``cash == 100_000 - 250*400 == 0`` (>= 0) y ``Σ ledger == Σ cash`` (inv. A);
    - cadena ``balance_after`` encadena (inv. B);
    - filas ledger de retirada == nº de retiros aplicados == 400.
    """
    async with _factory() as factory:
        tag = f"wd{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, _legacy, _inv, inst_id = await _new_account(
                setup, tag, initial_deposit=100_000.0
            )
            await setup.commit()

        amount = 250.0
        keys = [f"{tag}-{i}-{uuid4().hex}" for i in range(_WITHDRAW_COUNT)]
        try:
            # Gather dentro del try/finally (ver escenario 3): limpieza garantizada.
            outcomes = await _gather_withdraw_batch(factory, account_id, keys, amount)
            successes = sum(1 for ok in outcomes if ok)
            failures = _WITHDRAW_COUNT - successes

            # Solo caben floor(100_000/250) = 400 retiros; el resto se rechaza.
            assert successes == 400, f"retiros aplicados esperados 400, obtuve {successes}"
            assert failures == 100, f"retiros rechazados esperados 100, obtuve {failures}"

            async with factory() as check:
                from bolsa_infrastructure.database.repositories.ledger_repository import (
                    SqlAlchemyLedgerRepository,
                )

                ledger_repo = SqlAlchemyLedgerRepository(check)
                # cash final == seed − 400*250 == 0 (≥ 0) e invariante A.
                await _assert_reconciled(
                    check,
                    ledger_repo,
                    account_id,
                    expected_cash=Decimal("0"),
                )
                # Fila ledger de retirada por cada retiro aplicado (los rechazados no escriben).
                assert await _count_ledger_type(
                    check, account_id, "withdrawal", "external"
                ) == successes
                rows = await _load_sorted_rows(check, account_id)
                _check_ledger_chain(rows)
        finally:
            await _cleanup_guaranteed(factory, account_id, inst_id)


# ---------------------------------------------------------------------------
# 3) 500 BUY + 500 SELL simultáneos sobre la misma posición.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_load_500_buys_and_500_sells_same_position() -> None:
    """Escenario 3 — 500 BUY + 500 SELL simultáneos sobre la misma posición.

    Se siembra una posición de 10_000 uds y suficiente cash, y se lanzan en paralelo
    (``asyncio.gather``, sesiones independientes) ``_TRADE_COUNT`` compras y ``_TRADE_COUNT``
    ventas de 1 ud. a 1 EUR sobre la MISMA posición/instrumento. ``execute_trade`` serializa
    cartera y posición con ``with_for_update`` (M1) y valida: buy solo si ``cash >= total+fee``
    y sell solo si ``quantity >= quantity`` → NUNCA ``cash < 0`` ni ``quantity < 0``.

    Postcondiciones:
    - todos los trades aplican (cash suficiente y 10_000 de siembra >> 500 ventas);
    - ``quantity == 10_000 + 500 - 500 == 10_000`` y ``quantity >= 0``;
    - ``cash >= 0`` e invariante A ``Σ ledger == Σ cash`` (exacta);
    - invariante B estricta (EXEC-B-CONC: ``balance_after`` post-lock → ``_assert_chain_concurrent``).
    """
    async with _factory() as factory:
        tag = f"tr{uuid4().hex[:4]}"
        seed_qty = 10_000
        async with factory() as setup:
            account_id, legacy_pf_id, _inv, inst_id = await _new_account(
                setup, tag, initial_deposit=5_000_000.0
            )
            await _seed_buy(setup, account_id, inst_id, seed_qty, 1.0, tag)
            await setup.commit()

        buy_keys = [f"{tag}-B{i}-{uuid4().hex}" for i in range(_TRADE_COUNT)]
        sell_keys = [f"{tag}-S{i}-{uuid4().hex}" for i in range(_TRADE_COUNT)]
        try:
            # Gathers dentro del try/finally: si una tarea falla (p.ej. timeout de pool),
            # la limpieza garantizada sigue ejecutándose y no queda cuenta residual.
            await _gather_trade_batch(factory, account_id, inst_id, "buy", 1, 1.0, buy_keys)
            await _gather_trade_batch(factory, account_id, inst_id, "sell", 1, 1.0, sell_keys)

            async with factory() as check:
                from bolsa_infrastructure.database.repositories.ledger_repository import (
                    SqlAlchemyLedgerRepository,
                )

                ledger_repo = SqlAlchemyLedgerRepository(check)
                cash_total = await _account_total_cash(check, account_id)
                qty = await _position_quantity(check, legacy_pf_id, inst_id)
                # Invariantes principales del escenario.
                assert cash_total >= 0, f"cash negativo: {cash_total}"
                assert qty >= 0, f"quantity negativo: {qty}"
                assert qty == Decimal(str(seed_qty)), (
                    f"quantity final esperada {seed_qty}, obtuve {qty}"
                )
                await _assert_reconciled(check, ledger_repo, account_id)
                rows = await _load_sorted_rows(check, account_id)
                _assert_chain_concurrent(rows)
        finally:
            await _cleanup_guaranteed(factory, account_id, inst_id)


# ---------------------------------------------------------------------------
# 4a) BUY + SELL simultáneos (combinación de 2 operaciones distintas).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_load_buy_and_sell_concurrent_mixed() -> None:
    """    Escenario 4a — BUY + SELL simultáneos sobre la misma posición.

    Combina DOS operaciones distintas (compra y venta) lanzadas concurrentes sobre la
    misma cuenta/posición (``asyncio.gather``). Con cash y siembra suficientes todas
    aplican y el estado final cumple ``quantity >= 0``, ``cash >= 0``, invariante A
    ``Σ ledger == Σ cash`` e invariante B estricta (EXEC-B-CONC / ``_assert_chain_concurrent``).
    """
    async with _factory() as factory:
        tag = f"bs{uuid4().hex[:4]}"
        seed_qty = 1_000
        async with factory() as setup:
            account_id, legacy_pf_id, _inv, inst_id = await _new_account(
                setup, tag, initial_deposit=1_000_000.0
            )
            await _seed_buy(setup, account_id, inst_id, seed_qty, 1.0, tag)
            await setup.commit()

        buy_keys = [f"{tag}-B{i}-{uuid4().hex}" for i in range(_MIX_COUNT)]
        sell_keys = [f"{tag}-S{i}-{uuid4().hex}" for i in range(_MIX_COUNT)]
        try:
            # Gathers dentro del try/finally (ver escenario 3): limpieza garantizada
            # incluso si una tarea falla.
            await _gather_trade_batch(factory, account_id, inst_id, "buy", 1, 1.0, buy_keys)
            await _gather_trade_batch(factory, account_id, inst_id, "sell", 1, 1.0, sell_keys)

            async with factory() as check:
                from bolsa_infrastructure.database.repositories.ledger_repository import (
                    SqlAlchemyLedgerRepository,
                )

                ledger_repo = SqlAlchemyLedgerRepository(check)
                cash_total = await _account_total_cash(check, account_id)
                qty = await _position_quantity(check, legacy_pf_id, inst_id)
                assert cash_total >= 0, f"cash negativo: {cash_total}"
                assert qty >= 0, f"quantity negativo: {qty}"
                assert qty == Decimal(str(seed_qty)), (
                    f"quantity final esperada {seed_qty}, obtuve {qty}"
                )
                await _assert_reconciled(check, ledger_repo, account_id)
                rows = await _load_sorted_rows(check, account_id)
                _assert_chain_concurrent(rows)
        finally:
            await _cleanup_guaranteed(factory, account_id, inst_id)


# ---------------------------------------------------------------------------
# 4b) Custodia + BUY simultáneos: custodia aplica una sola vez (sin doble cargo).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_load_custody_and_buy_concurrent_no_double_charge() -> None:
    """Escenario 4b — custodia + BUY simultáneos; sin doble cargo de custodia.

    Combina DOS operaciones distintas (flujo real de custodia ``ApplyCustodyFees`` y
    trades de compra ``ExecuteTrade``) lanzadas concurrentes sobre la misma cuenta
    (``asyncio.gather``). La custodia del periodo se cobra a lo sumo UNA vez (lo blinda el
    mutex ``claim_custody_charge`` con fallback a memoria + el guard durable del ledger +
    UNIQUE), nunca ``cash - 2*fee``. Tras todo: ``Σ ledger == Σ cash``, ``quantity >= 0`` y
    la invariante B estricta (EXEC-B-CONC / ``_assert_chain_concurrent``).

    Sin ``time.sleep``: la serialización la dan ``with_for_update`` (M1) y el guard
    anti doble-cobro de custodia (misma restricción de entorno que
    ``test_custody_concurrency_chaos``: se usa ``ApplyCustodyFees``, no ``RunCustodyJob``).
    """
    async with _factory() as factory:
        tag = f"ct{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, legacy_pf_id, _inv, inst_id = await _new_account(
                setup, tag, initial_deposit=500_000.0, custody_pct=0.2
            )
            await _seed_buy(setup, account_id, inst_id, 100, 10.0, tag)
            await setup.commit()

        buy_keys = [f"{tag}-B{i}-{uuid4().hex}" for i in range(_MIX_COUNT)]
        period = _now().strftime("%Y")
        try:
            # Gathers dentro del try/finally (ver escenario 3): limpieza garantizada
            # incluso si una tarea falla.
            await _gather_trade_batch(factory, account_id, inst_id, "buy", 1, 1.0, buy_keys)
            await asyncio.gather(
                _custody_worker(factory, account_id),
                _custody_worker(factory, account_id),
            )
            async with factory() as check:
                from bolsa_infrastructure.database.repositories.ledger_repository import (
                    SqlAlchemyLedgerRepository,
                )

                ledger_repo = SqlAlchemyLedgerRepository(check)
                # La custodia del periodo aplicó UNA sola vez (nunca 2) → sin doble cargo.
                assert await _count_custody_entries(check, account_id, period) == 1, (
                    "los workers de custodia duplicaron el cargo del periodo"
                )
                cash_total = await _account_total_cash(check, account_id)
                qty = await _position_quantity(check, legacy_pf_id, inst_id)
                assert cash_total >= 0, f"cash negativo: {cash_total}"
                assert qty >= 0, f"quantity negativo: {qty}"
                await _assert_reconciled(check, ledger_repo, account_id)
                rows = await _load_sorted_rows(check, account_id)
                _assert_chain_concurrent(rows)
        finally:
            await _cleanup_guaranteed(factory, account_id, inst_id)
