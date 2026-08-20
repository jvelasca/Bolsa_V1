"""Fase 3 (L-M3/M-5) — UNIQUE parcial en ``ledger_entries`` (account_id, reference_type, reference_id, type).

Verifica contra PostgreSQL REAL (mismas convenciones que ``test_f3b_alembic_data_epoch``):
- ``ensure_migrated`` llega al nuevo head y el índice único existe.
- Duplicado ``(account_id, reference_type, reference_id, type)`` → IntegrityError.
- trade+fee (mismo tx, type ``buy``/``fee``) en la misma cuenta → OK (no colisiona).
- custodia ``("custody","custody-2026")`` en DOS cuentas distintas → OK.
- filas con ``reference_type IS NULL`` → OK (el parcial las excluye).

Los tests crean FKs de ``ledger_entries`` (account + portfolio) bajo nombres únicos.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.migrations import _alembic_config, ensure_migrated
from bolsa_infrastructure.database.models import (
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_INDEX_NAME = "uq_ledger_entries_account_reference"
_HEAD = "004_ledger_reference_unique"


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


async def _make_account_portfolio(
    session: AsyncSession, tag: str
) -> tuple[InvestmentAccountRow, InvestmentPortfolioRow]:
    account = InvestmentAccountRow(
        id=f"acc_{tag}_{uuid4().hex[:12]}",
        name=f"Acc {tag}",
        type="simulated",
        status="active",
        currency="EUR",
        base_currency="EUR",
        initial_deposit=Decimal("100000"),
        leverage=Decimal("1"),
        is_default=False,
        created_at=_now(),
        updated_at=_now(),
    )
    portfolio = InvestmentPortfolioRow(
        id=f"pf_{tag}_{uuid4().hex[:12]}",
        account_id=account.id,
        name=f"Portfolio {tag}",
        is_default=True,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([account, portfolio])
    await session.flush()
    return account, portfolio


async def _entry(**overrides: object) -> LedgerEntryRow:
    defaults: dict[str, object] = {
        "id": f"le_{uuid4().hex}",
        "account_id": "",  # se rellena por el caller
        "portfolio_id": None,
        "type": "deposit",
        "amount": Decimal("100"),
        "currency": "EUR",
        "balance_after": Decimal("100"),
        "instrument_id": None,
        "quantity": None,
        "price": None,
        "reference_type": None,
        "reference_id": None,
        "description": "test",
        "executed_at": _now(),
        "created_at": _now(),
    }
    defaults.update(overrides)
    return LedgerEntryRow(**defaults)


def test_alembic_head_es_el_nuevo() -> None:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, heads
    assert heads[0] == _HEAD


@pytest.mark.asyncio
async def test_ensure_migrated_carga_el_indice_unico(db_session: AsyncSession) -> None:
    """ensure_migrated lleva a head y el índice único parcial está en ledger_entries."""
    assert ensure_migrated() is True

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine

    engine = create_engine(get_settings())
    try:
        async with engine.connect() as conn:
            version = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalars().one()
            assert version == _HEAD

            idx = (
                await conn.execute(
                    text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE schemaname='public' AND tablename='ledger_entries' "
                        "AND indexname=:n"
                    ),
                    {"n": _INDEX_NAME},
                )
            ).first()
            assert idx is not None, f"índice {_INDEX_NAME} no existe"
            indexdef = idx[1]
            assert "UNIQUE" in indexdef.upper()
            assert "reference_type IS NOT NULL" in indexdef
            assert "reference_id IS NOT NULL" in indexdef
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_insertar_duplicado_falla(db_session: AsyncSession) -> None:
    """El mismo (account_id, reference_type, reference_id, type) → IntegrityError."""
    assert ensure_migrated() is True
    account, portfolio = await _make_account_portfolio(db_session, "dup")
    tx_id = f"tx_{uuid4().hex[:12]}"

    db_session.add(
        await _entry(
            account_id=account.id,
            portfolio_id=portfolio.id,
            type="buy",
            reference_type="transaction",
            reference_id=tx_id,
        )
    )
    await db_session.flush()

    db_session.add(
        await _entry(
            account_id=account.id,
            portfolio_id=portfolio.id,
            type="buy",
            reference_type="transaction",
            reference_id=tx_id,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_trade_y_fee_mismo_tx_no_colisiona(db_session: AsyncSession) -> None:
    """trade (``buy``) + fee (``fee``) mismo account/tx → OK (difieren en ``type``)."""
    assert ensure_migrated() is True
    account, portfolio = await _make_account_portfolio(db_session, "tradefee")
    tx_id = f"tx_{uuid4().hex[:12]}"

    db_session.add(
        await _entry(
            account_id=account.id,
            portfolio_id=portfolio.id,
            type="buy",
            amount=Decimal("100"),
            balance_after=Decimal("100"),
            reference_type="transaction",
            reference_id=tx_id,
        )
    )
    db_session.add(
        await _entry(
            account_id=account.id,
            portfolio_id=portfolio.id,
            type="fee",
            amount=Decimal("-1"),
            balance_after=Decimal("99"),
            reference_type="transaction",
            reference_id=tx_id,
        )
    )
    await db_session.flush()
    assert (
        await db_session.scalars(
            select(LedgerEntryRow).where(LedgerEntryRow.reference_id == tx_id)
        )
    ).first() is not None


@pytest.mark.asyncio
async def test_custodia_multi_cuenta_mismo_anno_no_colisiona(db_session: AsyncSession) -> None:
    """``("custody","custody-2026")`` en DOS cuentas → OK (por-cuenta)."""
    assert ensure_migrated() is True
    account_a, portfolio_a = await _make_account_portfolio(db_session, "custA")
    account_b, portfolio_b = await _make_account_portfolio(db_session, "custB")

    db_session.add(
        await _entry(
            account_id=account_a.id,
            portfolio_id=portfolio_a.id,
            type="fee",
            reference_type="custody",
            reference_id="custody-2026",
        )
    )
    db_session.add(
        await _entry(
            account_id=account_b.id,
            portfolio_id=portfolio_b.id,
            type="fee",
            reference_type="custody",
            reference_id="custody-2026",
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_reference_null_ok(db_session: AsyncSession) -> None:
    """Filas con reference_type IS NULL (o reference_id NULL) no rompen el parcial."""
    assert ensure_migrated() is True
    account, portfolio = await _make_account_portfolio(db_session, "nullref")

    # Dos filas sin reference (NULL,NULL): el parcial las excluye → no deben chocar.
    db_session.add(
        await _entry(
            account_id=account.id,
            portfolio_id=portfolio.id,
            type="deposit",
            reference_type=None,
            reference_id=None,
        )
    )
    db_session.add(
        await _entry(
            account_id=account.id,
            portfolio_id=portfolio.id,
            type="withdrawal",
            reference_type=None,
            reference_id=None,
        )
    )
    await db_session.flush()
