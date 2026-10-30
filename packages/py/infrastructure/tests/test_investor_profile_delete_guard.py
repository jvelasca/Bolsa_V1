"""AUD-03 — ningún camino de borrado puede eliminar un perfil todavía asignado.

Contra PostgreSQL real (``DATABASE_URL`` del ``.env``), sin pasar por la ruta HTTP:

1. **Acceso directo al repositorio** sobre un perfil asignado: ``delete_if_unused``
   devuelve ``(False, nombres)`` y no toca ni la cuenta ni el perfil (antes el
   ``delete()`` del repositorio desasignaba en silencio).
2. **Tras desasignar explícitamente**, el borrado del repositorio sí elimina.
3. **SQL crudo**: un ``DELETE FROM investor_profiles`` sobre un perfil asignado falla
   con ``IntegrityError`` (FK ``ON DELETE RESTRICT``), y la cuenta conserva su perfil.
4. **Concurrencia** (``asyncio.Event`` como barrera + sesiones independientes): en
   cualquier orden entre «asignar» y «borrar», o gana la asignación y el borrado ve uso,
   o gana el borrado y la asignación recibe 404. Nunca queda una cuenta apuntando a un
   perfil inexistente ni una cuenta desasignada sin un ``PUT`` explícito.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_infrastructure.database.models import InvestmentAccountRow, InvestorProfileRow
from bolsa_infrastructure.database.repositories.investor_profile_repository import (
    SqlAlchemyInvestorProfileRepository,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

pytestmark = pytest.mark.asyncio

_FK = "investment_accounts_active_profile_id_fkey"


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _now() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def _factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Engine + session_factory propios (sesiones independientes para la carrera)."""
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        # La FK RESTRICT la pone la 061; sin migrar, la prueba mediría otro esquema.
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL no disponible (AUD-03): {exc}")
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _new_account(session: AsyncSession, tag: str) -> str:
    account_id = f"acc_aud03_{tag}_{uuid4().hex[:10]}"
    session.add(
        InvestmentAccountRow(
            id=account_id,
            user_id=None,
            name=f"AUD-03 {tag}",
            type="simulated",
            status="active",
            currency="EUR",
            base_currency="EUR",
            initial_deposit=Decimal("0"),
            leverage=Decimal("1"),
            is_default=False,
            created_at=_now(),
            updated_at=_now(),
        )
    )
    await session.flush()
    return account_id


async def _new_profile(session: AsyncSession, tag: str) -> str:
    profile_id = f"PROF-AUD03-{tag}-{uuid4().hex[:8]}"
    session.add(
        InvestorProfileRow(
            id=profile_id,
            name=f"AUD-03 {tag}",
            version="1.0.0",
            user_id=None,
            horizon="swing",
            objectives=["growth"],
            risk_tolerance="moderate",
            experience="intermediate",
            suggested_policy_template_id="moderate",
            selected_policy_template_id="moderate",
            observed_json=None,
            updated_by="user",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    await session.flush()
    return profile_id


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    account_ids: list[str],
    profile_ids: list[str],
) -> None:
    async with factory() as session:
        if account_ids:
            await session.execute(
                delete(InvestmentAccountRow).where(InvestmentAccountRow.id.in_(account_ids))
            )
        if profile_ids:
            await session.execute(
                delete(InvestorProfileRow).where(InvestorProfileRow.id.in_(profile_ids))
            )
        await session.commit()


async def test_repository_never_unassigns_accounts_on_delete() -> None:
    async with _factory() as factory:
        async with factory() as session:
            account_id = await _new_account(session, "dir")
            profile_id = await _new_profile(session, "dir")
            await session.commit()

        try:
            async with factory() as session:
                repo = SqlAlchemyInvestorProfileRepository(session)
                assert await repo.assign_to_account(account_id, profile_id) == profile_id
                await session.commit()

            async with factory() as session:
                repo = SqlAlchemyInvestorProfileRepository(session)
                deleted, in_use_by = await repo.delete_if_unused(profile_id)
                await session.commit()

            assert deleted is False
            assert in_use_by == ("AUD-03 dir",)

            async with factory() as session:
                account = await session.get(InvestmentAccountRow, account_id)
                profile = await session.get(InvestorProfileRow, profile_id)
                assert account is not None
                # El repositorio ya NO desasigna: la cuenta conserva su perfil.
                assert account.active_profile_id == profile_id
                assert profile is not None

            async with factory() as session:
                repo = SqlAlchemyInvestorProfileRepository(session)
                assert await repo.assign_to_account(account_id, None) is None
                await session.commit()

            async with factory() as session:
                repo = SqlAlchemyInvestorProfileRepository(session)
                deleted, in_use_by = await repo.delete_if_unused(profile_id)
                await session.commit()

            assert deleted is True
            assert in_use_by == ()
        finally:
            await _cleanup(factory, [account_id], [profile_id])


async def test_raw_sql_delete_is_blocked_by_restrict_fk() -> None:
    async with _factory() as factory:
        async with factory() as session:
            account_id = await _new_account(session, "raw")
            profile_id = await _new_profile(session, "raw")
            await session.commit()

        try:
            async with factory() as session:
                await session.execute(
                    text(
                        "UPDATE investment_accounts SET active_profile_id = :pid WHERE id = :acc"
                    ),
                    {"pid": profile_id, "acc": account_id},
                )
                await session.commit()

            action = None
            async with factory() as session:
                action = await session.scalar(
                    text(
                        "SELECT confdeltype FROM pg_constraint WHERE conname = :fk"
                    ),
                    {"fk": _FK},
                )
            assert action == "r", f"la FK debe ser RESTRICT, es {action!r} (¿061 sin aplicar?)"

            with pytest.raises(IntegrityError):
                async with factory() as session:
                    await session.execute(
                        text("DELETE FROM investor_profiles WHERE id = :pid"),
                        {"pid": profile_id},
                    )
                    await session.commit()

            async with factory() as session:
                account = await session.get(InvestmentAccountRow, account_id)
                profile = await session.get(InvestorProfileRow, profile_id)
                assert account is not None and account.active_profile_id == profile_id
                assert profile is not None
        finally:
            await _cleanup(factory, [account_id], [profile_id])


async def _race_assign(
    factory: async_sessionmaker[AsyncSession],
    barrier: asyncio.Event,
    account_id: str,
    profile_id: str,
) -> str:
    """Intenta asignar tras la barrera; 404 (perfil borrado) → ``"rejected"``."""
    async with factory() as session:
        repo = SqlAlchemyInvestorProfileRepository(session)
        await barrier.wait()
        try:
            await repo.assign_to_account(account_id, profile_id)
        except ValueError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "assigned"


async def _race_delete(
    factory: async_sessionmaker[AsyncSession],
    barrier: asyncio.Event,
    profile_id: str,
) -> str:
    """Intenta borrar tras la barrera; ``"in_use"`` si la asignación ganó."""
    async with factory() as session:
        repo = SqlAlchemyInvestorProfileRepository(session)
        await barrier.wait()
        deleted, _in_use = await repo.delete_if_unused(profile_id)
        await session.commit()
        return "deleted" if deleted else "in_use"


async def test_concurrent_assign_and_delete_never_leave_inconsistent_state() -> None:
    """Asignar y borrar a la vez: o 409 (asignación ganó) o 404 (borrado ganó).

    Se repite el escenario varias veces con la barrera en el mismo punto; el orden del
    lock cambia entre ejecuciones, así que ambos desenlaces se cubren sin ``sleep``.
    """
    outcomes: set[str] = set()
    for _ in range(6):
        async with _factory() as factory:
            async with factory() as session:
                account_id = await _new_account(session, "race")
                profile_id = await _new_profile(session, "race")
                await session.commit()

            barrier = asyncio.Event()
            assign_task = asyncio.create_task(
                _race_assign(factory, barrier, account_id, profile_id)
            )
            delete_task = asyncio.create_task(_race_delete(factory, barrier, profile_id))
            barrier.set()
            assign_outcome, delete_outcome = await asyncio.gather(assign_task, delete_task)

            async with factory() as session:
                account = await session.get(InvestmentAccountRow, account_id)
                profile = await session.get(InvestorProfileRow, profile_id)
                assert account is not None
                if assign_outcome == "assigned":
                    # La asignación ganó: el perfil sigue vivo y la cuenta lo apunta.
                    assert profile is not None
                    assert account.active_profile_id == profile_id
                    assert delete_outcome == "in_use"
                    outcomes.add("assign-won")
                else:
                    # El borrado ganó: la asignación recibió 404 y no escribió nada.
                    assert delete_outcome == "deleted"
                    assert profile is None
                    assert account.active_profile_id is None
                    outcomes.add("delete-won")

            await _cleanup(factory, [account_id], [profile_id])

    assert outcomes, "el escenario no produjo ningún desenlace medible"
