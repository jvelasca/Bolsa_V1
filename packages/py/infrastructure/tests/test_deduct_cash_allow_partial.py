"""F1/M2 — `deduct_cash` never truncates balance silently.

- `allow_partial=False` (usuario/trade): si amount > cash → ValueError, sin truncar.
- `allow_partial=True` (solo custodia): descuenta lo que haya (mínimo) de forma
  explícita y devuelve el nuevo balance sin error.

Requiere PostgreSQL + migración (patrón `db_session` de infra).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from bolsa_infrastructure.database.models import PortfolioRow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_env() -> None:
    env_path = _repo_root() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def db_session():
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


async def _new_portfolio(db_session, *, cash: float) -> str:
    from bolsa_infrastructure.ids import new_id

    now = datetime.now(UTC)
    pid = new_id()
    db_session.add(
        PortfolioRow(
            id=pid,
            name=f"deduct-test-{uuid.uuid4().hex[:8]}",
            currency="EUR",
            cash=cash,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()
    return pid


@pytest.mark.asyncio
async def test_deduct_cash_enough_is_normal(db_session) -> None:
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    pid = await _new_portfolio(db_session, cash=1000.0)
    repo = SqlAlchemyPortfolioRepository(db_session)
    balance = await repo.deduct_cash(pid, 300.0)
    assert balance == 700.0


@pytest.mark.asyncio
async def test_deduct_cash_insufficient_without_partial_raises(db_session) -> None:
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    pid = await _new_portfolio(db_session, cash=100.0)
    repo = SqlAlchemyPortfolioRepository(db_session)
    with pytest.raises(ValueError, match="Efectivo insuficiente"):
        await repo.deduct_cash(pid, 500.0)
    # La transacción se revierte: no debe quedar un descuento silencioso.


@pytest.mark.asyncio
async def test_deduct_cash_partial_exhausts_available(db_session) -> None:
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    pid = await _new_portfolio(db_session, cash=100.0)
    repo = SqlAlchemyPortfolioRepository(db_session)
    balance = await repo.deduct_cash(pid, 500.0, allow_partial=True)
    assert balance == 0.0
