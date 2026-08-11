"""Tests F3a (P1.2) — migración de datos de cuentas fuera del path de petición.

Cubre:
- ``run_account_data_migration`` crea la cuenta demo + cartera legacy + depósito
  de forma **idempotente** (ejecutar dos veces no duplica ni falla).
- El repositorio YA NO expone ``ensure_migrated`` (ni el flag per-instancia):
  la migración es un paso de arranque, no una llamada por-request.
Requiere PostgreSQL (mismas convenciones que los tests de infraestructura).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from bolsa_infrastructure.database.account_migration import run_account_data_migration
from bolsa_infrastructure.database.models import (
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
)
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


@pytest.mark.asyncio
async def test_run_account_data_migration_crea_cuenta_demo_idempotente(
    db_session: AsyncSession,
) -> None:
    await db_session.commit()

    await run_account_data_migration(db_session)

    account = (
        await db_session.scalars(
            select(InvestmentAccountRow).where(
                InvestmentAccountRow.id == "default-account-seed",
            )
        )
    ).one_or_none()
    assert account is not None
    # is_default solo se activa si no había otra cuenta por defecto previa.
    if account.is_default:
        assert account.status == "active"

    inv_portfolios = (
        await db_session.scalars(
            select(InvestmentPortfolioRow).where(
                InvestmentPortfolioRow.account_id == account.id,
            )
        )
    ).all()
    assert len(inv_portfolios) >= 1

    deposits = (
        await db_session.scalars(
            select(LedgerEntryRow).where(
                LedgerEntryRow.account_id == account.id,
                LedgerEntryRow.reference_type == "migration",
            )
        )
    ).all()
    assert len(deposits) == 1
    assert deposits[0].type == "deposit"

    # Idempotencia: segunda ejecución no duplica el depósito ni falla.
    await run_account_data_migration(db_session)
    deposits_after = (
        await db_session.scalars(
            select(LedgerEntryRow).where(
                LedgerEntryRow.account_id == account.id,
                LedgerEntryRow.reference_type == "migration",
            )
        )
    ).all()
    assert len(deposits_after) == 1


def test_repositorio_no_expone_ensure_migrated() -> None:
    """P1.2: la migración ya no es un método por-request del repositorio."""
    assert not hasattr(SqlAlchemyAccountRepository, "ensure_migrated")
    assert not hasattr(SqlAlchemyAccountRepository, "_migration_done")
