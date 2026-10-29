"""PostgreSQL real — configuración de proveedores (migración 059).

Gate ``MARKET_PROVIDERS_PG_REQUIRED=1`` (un skip es fallo duro en el job PG). Todo el
test corre dentro de una transacción que se revierte al final: la BD del operador no
queda modificada, pero las restricciones y el SQL sí son los reales.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from bolsa_domain.entities.market_provider import PROVIDER_XTB, PROVIDER_YAHOO
from bolsa_infrastructure.database.models import MarketProviderSettingsRow
from bolsa_infrastructure.database.repositories.market_provider_settings_repository import (
    SqlAlchemyMarketProviderSettingsRepository,
)
from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED_ENV = "MARKET_PROVIDERS_PG_REQUIRED"


@pytest_asyncio.fixture
async def pg_factory() -> AsyncIterator[Any]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="configuración de proveedores")
        return
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seeding_is_idempotent(pg_factory: Any) -> None:
    """PRV-2: la primera lectura siembra el registro una sola vez.

    El test parte de tabla vacía **dentro de la transacción** (se revierte al final):
    sin esto dependería de lo que el operador tenga configurado en su BD y dejaría de
    probar el sembrado.
    """
    async with pg_factory() as session:
        await session.execute(delete(MarketProviderSettingsRow))
        await session.flush()
        repo = SqlAlchemyMarketProviderSettingsRepository(session)
        first = await repo.list_all()
        second = await repo.list_all()
        await session.rollback()

    assert [record.id for record in first] == [PROVIDER_YAHOO, PROVIDER_XTB]
    assert [record.id for record in second] == [PROVIDER_YAHOO, PROVIDER_XTB]
    assert first[0].priority == 10
    assert first[0].min_interval_seconds == 2
    assert first[1].priority == 20
    assert first[1].min_interval_seconds == 0
    assert first[1].base_url is None
    assert first[1].last_check_at is None


@pytest.mark.asyncio
async def test_round_trip_of_settings(pg_factory: Any) -> None:
    """PRV-3: update persiste, get lo devuelve y record_check deja last_check_*."""
    async with pg_factory() as session:
        repo = SqlAlchemyMarketProviderSettingsRepository(session)
        await repo.list_all()  # siembra

        updated = await repo.update(
            PROVIDER_XTB,
            enabled=False,
            priority=5,
            min_interval_seconds=7,
            base_url="http://127.0.0.1:3002",
        )
        assert updated is not None
        assert updated.enabled is False
        assert updated.priority == 5
        assert updated.min_interval_seconds == 7
        assert updated.base_url == "http://127.0.0.1:3002"

        past = datetime(2026, 10, 29, 10, 5, tzinfo=UTC)
        checked = await repo.record_check(
            PROVIDER_XTB, ok=True, message="Bridge mock listo", at=past
        )
        assert checked is not None
        assert checked.last_check_ok is True
        assert checked.last_check_message == "Bridge mock listo"
        assert checked.last_check_at is not None

        reread = await repo.get(PROVIDER_XTB)
        await session.rollback()

    assert reread is not None
    assert reread.enabled is False
    assert reread.last_check_ok is True


@pytest.mark.asyncio
async def test_clearing_base_url_sets_null(pg_factory: Any) -> None:
    async with pg_factory() as session:
        repo = SqlAlchemyMarketProviderSettingsRepository(session)
        await repo.list_all()
        await repo.update(PROVIDER_XTB, base_url="http://127.0.0.1:3002")
        cleared = await repo.clear_base_url(PROVIDER_XTB)
        await session.rollback()

    assert cleared is not None
    assert cleared.base_url is None


@pytest.mark.asyncio
async def test_database_check_is_the_last_defense(pg_factory: Any) -> None:
    """La BD rechaza un valor fuera de rango escrito sin pasar por el caso de uso."""
    async with pg_factory() as session:
        row = MarketProviderSettingsRow(
            id="pg-check-probe",
            enabled=True,
            priority=101,  # fuera de [0, 100]
            min_interval_seconds=0,
            base_url=None,
            options={},
            last_check_at=None,
            last_check_ok=None,
            last_check_message=None,
            updated_at=datetime.now(UTC),
        )
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_provider_check_policy_round_trip_and_check_constraint(pg_factory: Any) -> None:
    """060: la política ON/OFF + intervalo se persiste y la BD rechaza fuera de rango."""
    from sqlalchemy import update as sa_update

    from bolsa_infrastructure.database.models import SyncSettingsRow
    from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
        DEFAULT_SETTINGS_ID,
        SqlAlchemySyncSchedulerRepository,
    )

    async with pg_factory() as session:
        repo = SqlAlchemySyncSchedulerRepository(session)
        initial = await repo.get_settings()
        # El defecto de la migración es ON + 60 s; una fila existente ya válida se respeta.
        assert isinstance(initial.provider_check_enabled, bool)
        assert 15 <= initial.provider_check_interval_seconds <= 3600

        updated = await repo.update_settings(
            provider_check_enabled=False, provider_check_interval_seconds=300
        )
        assert updated.provider_check_enabled is False
        assert updated.provider_check_interval_seconds == 300

        reread = await repo.get_settings()
        assert reread.provider_check_enabled is False
        assert reread.provider_check_interval_seconds == 300

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    sa_update(SyncSettingsRow)
                    .where(SyncSettingsRow.id == DEFAULT_SETTINGS_ID)
                    .values(provider_check_interval_seconds=5)
                )
                await session.flush()
        await session.rollback()
