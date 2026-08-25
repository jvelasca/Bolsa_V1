"""M-7 (L-M5) — custodia: tras L-M3/M-5 el UNIQUE ya impide el re-cargo (tests-postcondición).

Hallazgo (mapeo read-only verificada): el único candidato de re-cobro de custodia era la
ventana time-only del mutex (`claim_custody_charge`, TTL ~48h + fallback de memoria) si dos
GET (summary/tax) entran tras un restart/R-expiry y ambas superan el guard da``ledger``
(`last_custody_charge_at`). Pero desde **L-M3/M-5** (migración `004_ledger_reference_unique`,
UNIQUE parcial `(account_id, reference_type, reference_id, type)`), `append_custody_fee`
(que escribe `reference_type="custody"`, `reference_id="custody-{period}"`, `type="fee"`)
colisiona si se re-cobra: la 2ª fila se rechaza con `IntegrityError`. Y como `deduct_cash` y
`append_custody_fee` comparten la misma `AsyncSession`, el `except` del use-case (release+raise)
+ el `rollback` del caller (`get_db_session` dependencies.py) revierten el descuento de cash.

M-7 queda entonces **CUBIERTA por F3**: el UNIQUE es el backstop real del re-cobro y la
transacción compartida garantiza que no queda cash descontado sin fila. Este test aporta la
evidencia como test-postcondición (decisión usuario: Opción A, sin tocar código de producción).

PostgreSQL real (patrón db_session). Los tests crean cuentas simuladas ``m7-uniq-*``/``m7-win-*``
y las limpian físicamente al final (``_cleanup_account``: ``close_account`` + ``delete_simulated_account``
+ commit, R000 post-v1.3.0) para no dejar residuos ``simulated`` en la DB compartida.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from bolsa_domain.account_settings import AccountSettings
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    InvestmentPortfolioRow,
    PortfolioRow,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
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
    session: AsyncSession,
    *,
    name: str,
    initial_deposit: float,
    settings: AccountSettings | None = None,
) -> str:
    """Cuenta simulada real (repo) con su cartera + seed deposit en ledger."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=name,
        initial_deposit=initial_deposit,
        settings=settings,
    )
    return scope.account.id


async def _cleanup_account(session: AsyncSession, account_id: str) -> None:
    """Cierra y borra físicamente una cuenta simulada creada por ``_new_account``.

    R000 (deuda post-v1.3.0): cada test que crea una cuenta simulada vía repo debe
    limpiarla (``close_account`` + ``delete_simulated_account``) y COMMITEAR el borrado,
    para que no queden filas ``simulated`` sobre la DB compartida entre ejecuciones de
    la suite (rompían el invariante A del verify). Canon: account_repository ``:431``/``:444``.
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    repo = SqlAlchemyAccountRepository(session)
    await repo.close_account(account_id)
    await repo.delete_simulated_account(account_id)
    await session.commit()


async def _account_total_cash(session: AsyncSession, account_id: str) -> Decimal:
    """Cash del account = Σ ``PortfolioRow.cash`` de sus legacy portfolios."""
    stmt = select(PortfolioRow.cash).join(
        InvestmentPortfolioRow,
        InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
    ).where(InvestmentPortfolioRow.account_id == account_id)
    cash_values = (await session.execute(stmt)).scalars().all()
    return sum((c for c in cash_values), Decimal("0"))


async def _assert_reconciled(
    session: AsyncSession, ledger_repo: Any, account_id: str
) -> None:
    """Postcondición M-2: Σ ledger (sum_cash_amounts) == cash del account."""
    ledger_total = await ledger_repo.sum_cash_amounts(account_id)
    cash_total = await _account_total_cash(session, account_id)
    assert ledger_total == cash_total, (
        f"Σ ledger={ledger_total} != Σ cash={cash_total} (account {account_id})"
    )


def _settings_with_custody(pct: float) -> AccountSettings:
    from bolsa_domain.account_settings import settings_from_dict

    return settings_from_dict(
        {"commission": {"custodyAnnualPct": pct}, "tax": {"costBasisMethod": "FIFO"}}
    )


@pytest.mark.asyncio
async def test_unique_rechaza_recargo_mismo_periodo(db_session: AsyncSession) -> None:
    """El UNIQUE de F3 impide una 2ª fila de custodia del mismo account+periodo.

    ``append_custody_fee`` (``reference_type="custody"``, ``reference_id="custody-<año>``,
    ``type="fee"``) es único por cuenta+periodo desde L-M3/M-5 → la segunda inserta
    ``IntegrityError`` (base del cierre de M-7).

    Limpieza (R000): tras el ``rollback`` la cuenta simulada se cierra y borra físicamente
    (``_cleanup_account`` + commit) para no dejar residuos ``simulated`` en la DB compartida.
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_id = await _new_account(
        db_session, name=f"m7-uniq-{uuid4().hex[:8]}", initial_deposit=100_000.0
    )
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    scope = await SqlAlchemyAccountRepository(db_session).resolve_scope(account_id)

    period = _now().strftime("%Y")
    await ledger_repo.append_custody_fee(
        account_id=account_id,
        portfolio_id=scope.portfolio.id,
        amount=123.0,
        currency="EUR",
        balance_after=99_877.0,
        reference_id=f"custody-{period}",
        description="Cargos custodia (1er)",
    )
    await db_session.commit()

    # 2º cargo del MISMO account+periodo → IntegrityError (UNIQUE activa).
    with pytest.raises(IntegrityError):
        await ledger_repo.append_custody_fee(
            account_id=account_id,
            portfolio_id=scope.portfolio.id,
            amount=456.0,
            currency="EUR",
            balance_after=99_421.0,
            reference_id=f"custody-{period}",
            description="Cargos custodia (2º, debe rechazarse)",
        )
    await db_session.rollback()
    # Limpieza R000: la cuenta se creó y commiteó antes, persiste tras el rollback →
    # ciérrala y bórrala físicamente para no dejar residuo `m7-uniq-*`.
    await _cleanup_account(db_session, account_id)


@pytest.mark.asyncio
async def test_recargo_forzado_no_deja_cash_descontado(db_session: AsyncSession) -> None:
    """Peor caso M-7: si la 2ª request descuenta cash y su append falla, no queda cash
    divergente (la transacción compartida revierte el descuento en el rollback).

    Reproduce la ventana real del mutex expirado: la 1ª request cobra y commitea
    (fila custodia persistida). La 2ª request entra con cash descontado (``deduct_cash``)
    pero su ``append_custody_fee`` del mismo periodo choca inmediatamente con el UNIQUE →
    el ``rollback`` del caller revierte el descuento, dejando ``Σ ledger == Σ cash``.

    Limpieza (R000): al final se cierra y borra físicamente la cuenta simulada
    (``_cleanup_account`` + commit) aunque el cuerpo hizo commits intermedios.
    """
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

    account_repo = SqlAlchemyAccountRepository(db_session)
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    portfolio_repo = SqlAlchemyPortfolioRepository(db_session)
    obligation_repo = CustodyObligationRepository(db_session)

    account_id = await _new_account(
        db_session,
        name=f"m7-win-{uuid4().hex[:8]}",
        initial_deposit=100_000.0,
        settings=_settings_with_custody(0.2),
    )
    scope = await account_repo.resolve_scope(account_id)

    # 1ª request: cargo real de custodia → fila persistida + cash descontado, commit.
    applied = await ApplyCustodyFees(
        account_repo,
        portfolio_repo,
        ledger_repo,
        custody_obligation_repo=obligation_repo,
    ).execute(scope)
    assert applied is True
    await db_session.commit()

    period = _now().strftime("%Y")
    # Estado esperado tras el 1er cargo (cash reconciliado con ledger).
    await _assert_reconciled(db_session, ledger_repo, account_id)

    # 2ª request (peor caso, mutex expirado): vuelve a pasar el guard del ledger y
    # descuenta cash ANTES de persistir, pero su append choca con el UNIQUE.
    legacy_id = scope.portfolio.legacy_portfolio_id
    assert legacy_id is not None  # la cartera de carga siempre tiene legacy id
    await portfolio_repo.deduct_cash(
        legacy_id,
        5000.0,
        allow_partial=True,
    )
    with pytest.raises(IntegrityError):
        await ledger_repo.append_custody_fee(
            account_id=account_id,
            portfolio_id=scope.portfolio.id,
            amount=99.0,
            currency="EUR",
            balance_after=100.0,
            reference_id=f"custody-{period}",
            description="Cargos custodia (2º, rechazado)",
        )
    # Equivale al `except: rollback()` de get_db_session → el descuento de cash de la 2ª
    # se revierte con la transacción fallida y el cash vuelve a reconciliarse (M-2).
    await db_session.rollback()
    await _assert_reconciled(db_session, ledger_repo, account_id)
    # Limpieza R000: cierra y borra físicamente la cuenta simulada (la 1ª request commiteó).
    await _cleanup_account(db_session, account_id)
