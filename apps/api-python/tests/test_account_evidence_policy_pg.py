"""066 — política de evidencia por cuenta contra PostgreSQL REAL.

Certifica lo que sólo se puede medir con base de datos:

1. La head es ``066_account_evidence_policy`` y la tabla existe con sus 10 ``CHECK`` y la
   FK a ``investment_accounts(id)`` con ``ON DELETE CASCADE``.
2. Sin fila rige el default ESTRICTO (fail-closed): la ausencia nunca relaja un umbral.
3. ``save`` es un upsert real: la primera escritura INSERTA y la segunda VERSIONA (version=2).
4. Un valor fuera de rango se rechaza en la aplicación antes de tocar la base (422 del contrato).
5. El ``CHECK`` de la base es una segunda barrera: un ``UPDATE`` crudo fuera de rango falla.
6. La FK CASCADE se lleva la política cuando se borra la cuenta.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``ACCOUNT_EVIDENCE_POLICY_PG_REQUIRED=1`` un skip silencioso es un FALLO duro.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.account_evidence_policy import (
    PostgresAccountEvidencePolicyStore,
    default_evidence_policy,
    policy_from_dict,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "ACCOUNT_EVIDENCE_POLICY_PG_REQUIRED"
_ACCOUNT = "acc-066-evidence-pg"
_HEAD = "066_account_evidence_policy"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la política de evidencia (066) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (política de evidencia 066) no disponible: {exc}")


def _now() -> datetime:
    return datetime.now(UTC)


async def _cleanup(factory: async_sessionmaker[AsyncSession]) -> None:
    from bolsa_infrastructure.database.models.tables import (
        AccountEvidencePolicyRow,
        InvestmentAccountRow,
    )

    async with factory() as session:
        await session.execute(
            delete(AccountEvidencePolicyRow).where(AccountEvidencePolicyRow.account_id == _ACCOUNT)
        )
        await session.execute(delete(InvestmentAccountRow).where(InvestmentAccountRow.id == _ACCOUNT))
        await session.commit()


async def _seed_account(factory: async_sessionmaker[AsyncSession]) -> None:
    from bolsa_infrastructure.database.models.tables import InvestmentAccountRow

    async with factory() as session:
        session.add(
            InvestmentAccountRow(
                id=_ACCOUNT,
                user_id=None,
                name="política 066",
                type="simulated",
                status="active",
                currency="EUR",
                base_currency="EUR",
                initial_deposit=Decimal("1000"),
                leverage=Decimal("1"),
                is_default=False,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.commit()


@pytest_asyncio.fixture
async def policy_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        await _cleanup(factory)
        await _seed_account(factory)
        yield factory
    finally:
        await _cleanup(factory)
        await engine.dispose()


@pytest.mark.asyncio
async def test_head_and_schema_are_the_ones_the_store_needs(
    policy_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_infrastructure.database.migrations import alembic_head

    assert alembic_head() == _HEAD
    async with policy_pg_factory() as session:
        checks = (
            await session.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'account_evidence_policy'::regclass AND contype = 'c' "
                    "ORDER BY conname"
                )
            )
        ).scalars().all()
        assert len(checks) == 10, checks
        fk = (
            await session.execute(
                text(
                    "SELECT confdeltype FROM pg_constraint "
                    "WHERE conrelid = 'account_evidence_policy'::regclass AND contype = 'f'"
                )
            )
        ).scalars().all()
    assert fk == ["c"], "la FK debe ser ON DELETE CASCADE"


@pytest.mark.asyncio
async def test_absent_row_means_strict_defaults(
    policy_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with policy_pg_factory() as session:
        policy = await PostgresAccountEvidencePolicyStore(session).load(_ACCOUNT)
    assert policy.is_default is True
    assert (policy.min_windows, policy.min_trades_total) == (30, 100)
    assert policy.min_round_trip_cost_bps == 22.0


@pytest.mark.asyncio
async def test_upsert_versions_and_survives_another_session(
    policy_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with policy_pg_factory() as session:
        store = PostgresAccountEvidencePolicyStore(session)
        assert await store.save(policy_from_dict(_ACCOUNT, {"minWindows": 60})) is True
        assert await store.save(policy_from_dict(_ACCOUNT, {"minWindows": 80})) is False

    # Otra sesión = otro proceso: sólo queda la fila durable.
    async with policy_pg_factory() as session:
        loaded = await PostgresAccountEvidencePolicyStore(session).load(_ACCOUNT)
    assert (loaded.min_windows, loaded.version, loaded.is_default) == (80, 2, False)
    assert loaded.min_trades_total == 100, "lo no enviado conserva el valor previo"


@pytest.mark.asyncio
async def test_application_validation_never_reaches_the_database(
    policy_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with policy_pg_factory() as session:
        store = PostgresAccountEvidencePolicyStore(session)
        for payload in ({"minSlippageBps": 0}, {"minWindows": 2}):
            with pytest.raises(ValueError):
                await store.save(policy_from_dict(_ACCOUNT, payload))
    async with policy_pg_factory() as session:
        assert (await PostgresAccountEvidencePolicyStore(session).load(_ACCOUNT)).is_default is True


@pytest.mark.asyncio
async def test_database_check_is_the_second_barrier(
    policy_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with policy_pg_factory() as session:
        await PostgresAccountEvidencePolicyStore(session).save(
            policy_from_dict(_ACCOUNT, {"minWindows": 60})
        )

    async with policy_pg_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "UPDATE account_evidence_policy SET holdout_pct = 5 "
                    "WHERE account_id = :account"
                ),
                {"account": _ACCOUNT},
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_deleting_the_account_cascades_the_policy(
    policy_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_infrastructure.database.models.tables import InvestmentAccountRow

    async with policy_pg_factory() as session:
        await PostgresAccountEvidencePolicyStore(session).save(
            policy_from_dict(_ACCOUNT, {"minWindows": 60})
        )
        row = await session.get(InvestmentAccountRow, _ACCOUNT)
        assert row is not None
        await session.delete(row)
        await session.commit()

    async with policy_pg_factory() as session:
        remaining = (
            await session.execute(
                text("SELECT count(*) FROM account_evidence_policy WHERE account_id = :account"),
                {"account": _ACCOUNT},
            )
        ).scalar_one()
    assert remaining == 0


def test_default_policy_is_the_documented_contract() -> None:
    """Ancla de contrato: los defaults del código son los que publica la nota de ingeniería."""
    policy: Any = default_evidence_policy("acc-1")
    assert policy.min_windows == 30
    assert policy.min_trades_total == 100
    assert policy.min_positive_window_pct == 60.0
    assert policy.min_net_return_pct == 0.0
    assert policy.max_drawdown_pct == 15.0
    assert policy.min_excess_vs_buy_hold_pct == 0.0
    assert policy.holdout_pct == 30.0
    assert policy.min_round_trip_cost_bps == 22.0
