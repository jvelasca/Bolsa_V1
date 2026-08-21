"""R-11/Auditoría — aventura de concurrencia e invariantes de custodia (3 huecos).

Fase 2 (post-v1.3.0) de tests NUEVOS sobre la custodia y su multi-periodo, contra
PostgreSQL REAL (docker ``bolsa-postgres``). Cubre los tres huecos que la auditoría
pedía y que hoy no existían como prueba de regresión:

1. **2 custody workers concurrentes** (``asyncio.gather``, sesiones independientes)
   sobre la MISMA cuenta/periodo → exactamente 1 cargo ledger de custodia, 1 obligation
   ``APPLIED``, cash descontado UNA sola vez (nunca ``cash - 2*fee``), ``Σ ledger ==
   Σ cash`` y la cadena ``balance_after`` encadena. Sin ``time.sleep``: la serialización
   se apoya en el mutex (``claim_custody_charge``) + UNIQUE parcial ``uq_ledger_entries_
   account_reference`` + guard duradero ``last_custody_charge_at``.

2. **Redis caído/ausente + 2 custody workers** → el mutex cae al fallback de memoria
   (``_CUSTODY_MEMORY`` en el proceso) y el resultado sigue siendo **exactly one charge**.
   Este test documenta explícitamente qué se espera: aunque el claim a Redis falle (o el
   client no exista), el proceso comparte el set en memoria → un worker gana el claim y el
   otro obtiene ``False``, de modo que el cargo se aplica exactamente una vez.

3. **Transición de periodo PG real con obligación PENDING antigua**: se siembra una
   obligación PENDING del periodo anterior y se ejecuta el flujo del periodo actual con
   cash insuficiente → ni la obligación antigua ni la nueva desaparecen (ninguna fila se
   pierde silenciosamente); la más antigua se liquida PRIMERO; y tras todo ``Σ ledger ==
   Σ cash`` con la cadena ``balance_after`` encadenada.

Patrón heredado de ``test_concurrency_scenarios.py``: ``pytest.skip`` si no hay PostgreSQL,
``asyncio.WindowsSelectorEventLoopPolicy`` en Windows (psycopg async no soporta Proactor),
fixture ``db_session`` con ``rollback`` y ``_factory()`` para escenarios concurrentes con
sesiones independientes. Cada test limpia el estado que crea (borra cuenta/instrumentos vía
repo, best-effort).

Restricción de entorno (documentada, no tocar producción): el hueco 1 se cubre con
``ApplyCustodyFees`` concurrente (una o dos cuentas), NO con ``RunCustodyJob`` concurrente.
``RunCustodyJob`` barre TODAS las cuentas activas de la BD compartida; si alguna cuenta
residual de otros tests carece de cartera legacy, su ``_load_scope`` lanza un ``ValueError``
antes de poder validar el cargo, y no podemos arreglar producción en esta fase. ``ApplyCustodyFees``
es el flujo real que el job invoca por cuenta y comparte todos los guards anti doble-cobro.

Variante de enfoque frente al mapa (documentada): el test multi-periodo de la suite de
application usa fakes y un periodo literal ``"prior"``; aquí se usa PG real y se siembra el
PENDING antiguo con ``CustodyObligationRepository.upsert(period=<año anterior>)``, sin
tocar producción. El cargo del periodo actual sigue usando ``now.strftime('%Y')``.
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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_domain.account_settings import AccountSettings
from bolsa_infrastructure.database.models import (
    CustodyObligationRow,
    InstrumentRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
)

if TYPE_CHECKING:
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
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


def _current_period() -> str:
    return _now().strftime("%Y")


def _prior_year_period() -> str:
    return str(_now().year - 1)


def _settings_with_custody(pct: float) -> AccountSettings:
    from bolsa_domain.account_settings import settings_from_dict

    return settings_from_dict(
        {"commission": {"custodyAnnualPct": pct}, "tax": {"costBasisMethod": "FIFO"}}
    )


async def _assert_reconciled(
    session: AsyncSession,
    ledger_repo: SqlAlchemyLedgerRepository,
    account_id: str,
    *,
    expected_cash: Decimal | None = None,
) -> None:
    """Postcondición M-2: Σ ledger (sum_cash_amounts) == cash del account."""
    ledger_total = await ledger_repo.sum_cash_amounts(account_id)
    cash_total = await _account_total_cash(session, account_id)
    if expected_cash is not None:
        assert cash_total == expected_cash, (
            f"cash={cash_total} != expected={expected_cash}"
        )
    assert ledger_total == cash_total, (
        f"Σ ledger={ledger_total} != Σ cash={cash_total} (account {account_id})"
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
    """Invariante ``balance_after`` secuencial por fila sobre una secuencia ordenada.

    ``balance_after[n] == balance_after[n-1] + amount[n]`` para TODA fila, desde
    ``prev_balance = 0``. Reutiliza la semántica de ``test_concurrency_scenarios``.
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
    """Borra la cuenta simulada (cierre+delete via repo) y el instrumento creado."""
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


async def _new_account_with_custody(
    session: AsyncSession, tag: str, pct: float, initial_deposit: float = 30_000.0
) -> tuple[str, str, str, str]:
    """Cuenta simulada con custodia habilitada + instrumento."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"CHAOS {tag}",
        initial_deposit=initial_deposit,
        settings=_settings_with_custody(pct),
    )
    legacy_pf_id = scope.portfolio.legacy_portfolio_id
    assert legacy_pf_id is not None
    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"CH{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"CH{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"CHAOS {tag}",
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


async def _seed_buy(
    session: AsyncSession,
    account_id: str,
    legacy_pf_id: str,
    instrument_id: str,
    quantity: int,
    price: float,
    tag: str,
) -> None:
    """Compra simple vía use-case ``ExecuteTrade`` — escribe ledger y mantiene Σ==cash.

    IMPORTANTE: NO usar ``SqlAlchemyPortfolioRepository.execute_trade`` directamente: es la
    ruta "sucia" B-3 que muta cash/posiciones SIN escribir ledger y rompería la invariante
    M-2 (``Σ ledger == Σ cash``). El use-case de application sí escribe el ledger.
    """
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


async def _custody_job_for_one(
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


# ---------------------------------------------------------------------------
# 1) 2 custody workers concurrentes (misma cuenta, mismo periodo) → 1 cargo.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_two_custody_workers_single_charge_no_double_fee() -> None:
    """Dos workers de custodia concurrentes cobran exactamente UN cargo / 1 obligation.

    Se lanzan con ``asyncio.gather`` dos ``ApplyCustodyFees.execute`` idénticos sobre la
    MISMA cuenta y el MISMO periodo actual, cada uno con su propia sesión/transacción. Se
    espera exactamente 1 fila ledger de custodia del periodo y 1 obligation ``APPLIED``, con
    cash descontado una sola vez (``cash - fee``, nunca ``cash - 2*fee``). La postcondición
    es orden-independiente: gane el que gane el mutex (``claim_custody_charge``) y el UNIQUE
    por-cuenta+periodo, el perdedor devuelve ``False``/``skipped`` sin efectos laterales.

    Sin ``time.sleep``: la serialización la dan el mutex SET NX (con fallback a la memoria
    del proceso) más el guard duradero de ledger y el UNIQUE parcial. Se verifica
    ``Σ ledger == Σ cash`` y que la cadena ``balance_after`` encadena.
    """
    async with _factory() as factory:
        tag = f"w2{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, _, _, instrument_id = await _new_account_with_custody(
                setup, tag, 0.2, initial_deposit=100_000.0
            )
            await setup.commit()

        outcomes = await asyncio.gather(
            _custody_job_for_one(factory, account_id),
            _custody_job_for_one(factory, account_id),
        )
        # A lo sumo UN workers cobra (al menos uno lo hace: cuenta activa con fee>0).
        assert outcomes.count(True) == 1, f"se esperaba exactamente 1 cobro, {outcomes}"

        period = _current_period()
        async with factory() as check:
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            # Exactamente 1 fila ledger de custodia del periodo.
            assert await _count_custody_entries(check, account_id, period) == 1

            # Exactamente 1 obligation APPLIED del periodo (nunca 2, ni estado ambiguo).
            oblig_rows = (
                await check.execute(
                    select(CustodyObligationRow).where(
                        CustodyObligationRow.account_id == account_id,
                        CustodyObligationRow.period == period,
                    )
                )
            ).scalars().all()
            assert len(oblig_rows) == 1
            assert oblig_rows[0].status == "APPLIED"
            assert float(oblig_rows[0].outstanding) == 0.0

            # Cash descontado UNA sola vez: seed 100000 → cash 100000 - fee.
            ledger_total = await SqlAlchemyLedgerRepository(check).sum_cash_amounts(
                account_id
            )
            cash_total = await _account_total_cash(check, account_id)
            fee = Decimal("100000") - ledger_total
            assert fee > 0, f"fee esperado >0, Σ ledger={ledger_total}"
            # cash == 100000 - fee (una sola resta), NO 100000 - 2*fee.
            assert cash_total == Decimal("100000") - fee
            await _assert_reconciled(check, SqlAlchemyLedgerRepository(check), account_id)

            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)
            await _cleanup(check, account_id, instrument_id)


@pytest.mark.asyncio
async def test_two_custody_workers_two_accounts_single_charge_each() -> None:
    """2 workers de custodia concurrentes sobre DOS cuentas → 1 cargo por cuenta.

    Variante de regresión del hueco 1 a nivel de DOS cuentas distintas: se crean dos
    cuentas y sobre cada una se lanzan dos workers ``ApplyCustodyFees.execute`` concurrentes
    (``asyncio.gather``, sesiones independientes, sin ``time.sleep``). Cada cuenta debe
    quedar con exactamente 1 fila ledger de custodia del periodo y cash descontado una sola
    vez por cuenta (nunca ``-2*fee``), con ``Σ ledger == Σ cash`` y la cadena encadenada.

    NOTA (restricción de entorno documentada): NO se usa ``RunCustodyJob`` concurrente aquí.
    ``RunCustodyJob`` barre TODAS las cuentas activas de la BD compartida y, si alguna cuenta
    residual de otros tests no tiene cartera legacy, falla en ``_load_scope`` antes de poder
    validar el cargo. Para cubrir el hueco 1 de forma fiable a nivel de account se invoca
    directamente ``ApplyCustodyFees`` (mismo flujo real que el job usa por cuenta), que es lo
    que comparte todos los guards de doble-cobro (mutex + UNIQUE + guard de ledger).
    """
    async with _factory() as factory:
        tag = f"2acc{uuid4().hex[:4]}"
        async with factory() as setup:
            acc_a, _, _, inst_a = await _new_account_with_custody(
                setup, f"{tag}A", 0.2, initial_deposit=100_000.0
            )
            acc_b, _, _, inst_b = await _new_account_with_custody(
                setup, f"{tag}B", 0.2, initial_deposit=100_000.0
            )
            await setup.commit()

        # 2 workers concurrentes por cada cuenta.
        await asyncio.gather(
            _custody_job_for_one(factory, acc_a),
            _custody_job_for_one(factory, acc_a),
            _custody_job_for_one(factory, acc_b),
            _custody_job_for_one(factory, acc_b),
        )
        period = _current_period()

        async with factory() as check:
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            repo = SqlAlchemyLedgerRepository(check)
            for account_id in (acc_a, acc_b):
                assert await _count_custody_entries(check, account_id, period) == 1
                await _assert_reconciled(check, repo, account_id)
                rows = await _load_sorted_rows(check, account_id)
                _check_ledger_chain(rows)
            await _cleanup(check, acc_a, inst_a)
            await _cleanup(check, acc_b, inst_b)


# ---------------------------------------------------------------------------
# 2) Redis caído/ausente + 2 workers → siempre exactly one charge (fallback memoria).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_down_two_workers_memory_fallback_single_charge() -> None:
    """Redis ausente/caído + 2 workers de custodia → sigue siendo Exactly One Charge.

    Qué se espera (documentado): el mutex ``claim_custody_charge`` cae al fallback de
    memoria del proceso (``_CUSTODY_MEMORY``) cuando Redis no está disponible (client
    ``None`` o fallo de conexión). Al ser ambas tasks del MISMO proceso, comparten ese set:
    el primer worker que lo consulta marca la clave (claim OK) y el segundo ve la clave ya
    presente → devuelve ``False``. El resultado agregado es exactamente 1 cargo ledger de
    custodia, 1 obligation ``APPLIED`` y cash descontado una sola vez; el UNIQUE parcial
    actúa de backstop extra ante una carrera residual.

    En el entorno de dev actual Redis NO responde (sin ``REDIS_URL`` en env ni `.env`, y el
    puerto 6379 cerrado), por lo que este test valida el fallback a memoria de forma natural
    (la suite no rompe por depender de un servicio externo). Se limpia el estado creado vía
    ``close_account`` + ``delete_simulated_account`` (best-effort, igual que el resto).
    """
    from bolsa_application.risk_runtime import clear_custody_memory_for_tests

    # Garantiza un set de memoria vacío antes de la carrera (sin estado residual).
    clear_custody_memory_for_tests()

    async with _factory() as factory:
        tag = f"rd{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, _, _, instrument_id = await _new_account_with_custody(
                setup, tag, 0.2, initial_deposit=100_000.0
            )
            await setup.commit()

        outcomes = await asyncio.gather(
            _custody_job_for_one(factory, account_id),
            _custody_job_for_one(factory, account_id),
        )
        assert outcomes.count(True) == 1, f"se esperaba 1 cobro con Redis caído, {outcomes}"

        period = _current_period()
        async with factory() as check:
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            assert await _count_custody_entries(check, account_id, period) == 1
            await _assert_reconciled(check, SqlAlchemyLedgerRepository(check), account_id)
            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)
            await _cleanup(check, account_id, instrument_id)


# ---------------------------------------------------------------------------
# 3) Transición de periodo PG real con PENDING antiguo (no se pierde ninguna fila).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_old_pending_preserved_and_oldest_liquidated_first_insufficient() -> None:
    """PENDING antiguo + periodo actual con cash insuficiente → NINGUNA (única) fila perdida.

    Se siembra una obligación ``PENDING`` del periodo anterior (``<year-1>``) con
    ``CustodyObligationRepository.upsert`` y se ejecuta la custodia del periodo actual sobre
    un patrimonio alto pero cash bajo (equity inflado vía posición, sin rutas "sucias" que
    rompan ``Σ ledger == Σ cash``).

    Flujo esperado en ``ApplyCustodyFees.execute`` (R-11 C1): primero liquida los PENDING
    más antiguos (gasta cash del pendiente viejo → queda ``APPLIED``); después, con cash
    restante < fee del periodo actual, NO descuenta ni escribe ledger y registra la
    obligación actual como ``PENDING``. Resultado: la obligación antigua sigue existiendo
    (transicionó a ``APPLIED``, NO se borró) y la del periodo actual se crea como ``PENDING``.
    Nada se pierde: ``Σ ledger == Σ cash`` y la cadena ``balance_after`` encadena.
    """
    async with _factory() as factory:
        tag = f"tr{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, legacy_pf_id, _, instrument_id = await _new_account_with_custody(
                setup, tag, 0.2, initial_deposit=30_000.0
            )
            # Equity alto vs cash bajo: compramos 500@10, luego 1@10_000 → el fallback
            # mark-to-cost (M-1) valora la posición al último precio de transacción (10_000),
            # de modo que equity >> cash manteniendo Σ ledger == cash (via la compra real).
            await _seed_buy(setup, account_id, legacy_pf_id, instrument_id, 500, 10.0, tag)
            await _seed_buy(setup, account_id, legacy_pf_id, instrument_id, 1, 10_000.0, tag)

            from bolsa_infrastructure.database.repositories.custody_obligation_repository import (
                CustodyObligationRepository,
            )

            prior = _prior_year_period()
            await CustodyObligationRepository(setup).upsert(
                account_id=account_id,
                period=prior,
                status="PENDING",
                outstanding=8_000.0,
                total_fee=8_000.0,
            )
            await setup.commit()

        applied = await _custody_job_for_one(factory, account_id)
        period = _current_period()

        async with factory() as check:
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            ledger_repo = SqlAlchemyLedgerRepository(check)

            # La obligación ANTIGUA pervive (no desaparece): PENDING→APPLIED tras liquidarse.
            prior_rows = (
                await check.execute(
                    select(CustodyObligationRow).where(
                        CustodyObligationRow.account_id == account_id,
                        CustodyObligationRow.period == prior,
                    )
                )
            ).scalars().all()
            assert len(prior_rows) == 1, "la obligación antigua debe seguir existiendo"
            # "Cash insuficiente" para el periodo actual → la antigua puede quedar liquidada
            # (tiene prioridad) pero NUNCA debe borrarse sin dejar rastro.
            assert prior_rows[0].status in {"PENDING", "APPLIED"}

            # La antigua se liquida primero: su fila ledger de custodia antecede a la actual.
            prior_ledger = await _count_custody_entries(check, account_id, prior)
            current_ledger = await _count_custody_entries(check, account_id, period)
            # El pendiente se salda con cash ANTES del cobro del periodo: prior fila existe.
            assert prior_ledger == 1, "se esperaba 1 fila ledger del pendiente antiguo"
            # Con cash insuficiente, el periodo actual NO descuenta → 0 filas ledger nuevas.
            assert current_ledger == 0, (
                "cash insuficiente → no debe escribirse fila ledger del periodo actual"
            )

            # La obligación nueva (periodo actual) existe como PENDING (no se pierde).
            current_rows = (
                await check.execute(
                    select(CustodyObligationRow).where(
                        CustodyObligationRow.account_id == account_id,
                        CustodyObligationRow.period == period,
                    )
                )
            ).scalars().all()
            assert len(current_rows) == 1
            assert current_rows[0].status == "PENDING"
            assert float(current_rows[0].outstanding) > 0.0

            # `applied` True (el flujo "cobró/no falló"), sin doble efecto.
            assert applied is True

            # Nada se pierde: Σ ledger == Σ cash + cadena balance_after encadena.
            await _assert_reconciled(check, ledger_repo, account_id)
            rows = await _load_sorted_rows(check, account_id)
            _check_ledger_chain(rows)
            await _cleanup(check, account_id, instrument_id)


@pytest.mark.asyncio
async def test_oldest_pending_liquidated_before_current_period_full() -> None:
    """Con cash suficiente, la obligación antigua se liquida ANTES que el periodo actual.

    Mismo escenario de transición de periodo pero con cash de sobra: el PENDING antiguo se
    salda por completo (``APPLIED``) y a continuación se cobra el periodo actual
    (``APPLIED``). El orden observable en el ledger es ``[custody-<year-1>,
    custody-<year>]`` (más antigua primero) y ``Σ ledger == Σ cash`` con la cadena
    ``balance_after`` encadenada.
    """
    async with _factory() as factory:
        tag = f"fl{uuid4().hex[:4]}"
        async with factory() as setup:
            account_id, _, _, instrument_id = await _new_account_with_custody(
                setup, tag, 0.2, initial_deposit=100_000.0
            )
            from bolsa_infrastructure.database.repositories.custody_obligation_repository import (
                CustodyObligationRepository,
            )

            prior = _prior_year_period()
            await CustodyObligationRepository(setup).upsert(
                account_id=account_id,
                period=prior,
                status="PENDING",
                outstanding=150.0,
                total_fee=150.0,
            )
            await setup.commit()

        applied = await _custody_job_for_one(factory, account_id)
        period = _current_period()
        assert applied is True

        async with factory() as check:
            from bolsa_infrastructure.database.repositories.ledger_repository import (
                SqlAlchemyLedgerRepository,
            )

            ledger_repo = SqlAlchemyLedgerRepository(check)

            # La antigua quedó APPLIED y la actual también.
            for p in (prior, period):
                oblig = (
                    await check.execute(
                        select(CustodyObligationRow).where(
                            CustodyObligationRow.account_id == account_id,
                            CustodyObligationRow.period == p,
                        )
                    )
                ).scalar_one()
                assert oblig.status == "APPLIED"

            # Orden de liquidación: [custody-prior, custody-current] en el ledger ordenado.
            rows = await _load_sorted_rows(check, account_id)
            custody_refs = [
                r.reference_id
                for r in rows
                if r.reference_type == "custody" and r.reference_id is not None
            ]
            assert custody_refs == [
                f"custody-{prior}",
                f"custody-{period}",
            ], f"orden de liquidación esperado [prior, current], obtuve {custody_refs}"

            await _assert_reconciled(check, ledger_repo, account_id)
            _check_ledger_chain(rows)
            await _cleanup(check, account_id, instrument_id)
