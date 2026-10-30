"""AUD-03 — carrera real asignación/borrado con dos transacciones PostgreSQL.

``test_investor_profile_delete_guard.py`` ya lanza dos sesiones concurrentes, pero con un
``asyncio.Event`` en el mismo punto: el orden de adquisición del lock cambia entre
ejecuciones, así que no puede demostrar *cuál* de los dos protocolos ganó ni que exista
bloqueo. Aquí el orden se impone desde fuera: la primera transacción bloquea, la segunda
se lanza, se verifica con ``pg_blocking_pids`` que está realmente esperando y solo
entonces se libera. Si una regresión elimina el ``SELECT … FOR UPDATE``, ``_wait_blocked``
falla con el estado real de ``pg_stat_activity`` en vez de pasar por casualidad.

Desenlaces cubiertos:

1. **Gana el borrado**: la asignación espera el lock, el perfil desaparece, la relectura
   da «Perfil no encontrado» y no se escribe nada (la cuenta sigue sin perfil).
2. **Gana la asignación**: el borrado espera, relee ya con la cuenta visible y devuelve
   ``(False, nombres)`` — el 409 ``profile_in_use`` — sin borrar ni desasignar.
3. **Backstop FK con escritores que ignoran el protocolo**, en ambos órdenes: el segundo
   comando bloquea y termina en ``IntegrityError``. Nunca queda un huérfano ni una
   desasignación implícita.

Gate: ``PROFILE_DELETE_RACE_PG_REQUIRED=1`` convierte el skip en fallo duro.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from _profile_pg_helpers import (
    database_url,
    load_env,
    orphan_accounts,
    require_or_skip,
)
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from bolsa_infrastructure.database.models import InvestmentAccountRow, InvestorProfileRow
from bolsa_infrastructure.database.repositories.investor_profile_repository import (
    SqlAlchemyInvestorProfileRepository,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

pytestmark = pytest.mark.asyncio

_REQUIRED_ENV = "PROFILE_DELETE_RACE_PG_REQUIRED"
_BLOCK_TIMEOUT_SECONDS = 10.0


# --------------------------------------------------------------------------- arnés


@asynccontextmanager
async def _race_env() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], str]]:
    """Engine ``NullPool`` (una conexión real por sesión) sobre la BD ya migrada."""
    load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated

    get_settings.cache_clear()
    settings = get_settings()
    url = settings.database_url
    if not url:
        raise RuntimeError("DATABASE_URL no configurado")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    engine = create_async_engine(
        url,
        poolclass=NullPool,
        # Tope POR SESIÓN: una regresión que deje de bloquear falla rápido en vez de
        # colgar el job de CI. ``NullPool`` descarta las conexiones, así que ``SET``
        # sobre una conexión suelta no serviría: tiene que ir en el connect.
        connect_args={
            "options": "-c lock_timeout=15000 -c statement_timeout=30000",
            # Un host inalcanzable no debe colgar el test (mismo criterio que session.py).
            **(
                {"connect_timeout": settings.db_connect_timeout_seconds}
                if settings.db_connect_timeout_seconds > 0
                else {}
            ),
        },
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - el llamante decide skip/fail
        await engine.dispose()
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="carrera asignación/borrado")
        raise

    try:
        await asyncio.to_thread(ensure_migrated)
        yield async_sessionmaker(engine, expire_on_commit=False), database_url()
    finally:
        await engine.dispose()


async def _pid(session: AsyncSession) -> int:
    return int((await session.execute(text("SELECT pg_backend_pid()"))).scalar_one())


def _lock_probe(dsn: str, pid: int) -> tuple[list[int], dict[str, Any]]:
    """``(blockers, estado)`` del backend ``pid`` — una conexión psycopg síncrona."""
    import psycopg

    # Tope de conexión: la sonda se repite cada 20 ms; sin él, un servidor caído a mitad
    # de la carrera colgaría el sondeo en vez de fallar.
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
        row = conn.execute("SELECT pg_blocking_pids(%s)", (pid,)).fetchone()
        blockers = [int(value) for value in (row[0] if row else [])]
        status_row = conn.execute(
            "SELECT state, wait_event_type, wait_event, left(query, 120) "
            "FROM pg_stat_activity WHERE pid = %s",
            (pid,),
        ).fetchone()
    status = (
        {"state": None, "wait_event_type": None, "wait_event": None, "query": None}
        if status_row is None
        else {
            "state": status_row[0],
            "wait_event_type": status_row[1],
            "wait_event": status_row[2],
            "query": status_row[3],
        }
    )
    return blockers, status


async def _wait_blocked(
    dsn: str,
    pid: int,
    *,
    timeout: float = _BLOCK_TIMEOUT_SECONDS,
    task: asyncio.Task[Any] | None = None,
) -> list[int]:
    """Espera a que ``pid`` esté esperando un lock. Falla con el estado real si no ocurre."""
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        if task is not None and task.done():
            error = task.exception()
            if error is not None:
                raise AssertionError(
                    f"la transacción {pid} terminó sin bloquearse: {error!r}"
                ) from error
            raise AssertionError(
                f"la transacción {pid} terminó sin bloquearse: resultado={task.result()!r}"
            )
        blockers, last = await asyncio.to_thread(_lock_probe, dsn, pid)
        if blockers:
            return blockers
        await asyncio.sleep(0.02)
    raise AssertionError(
        f"la transacción {pid} no llegó a bloquearse en {timeout}s "
        f"(¿se eliminó el SELECT … FOR UPDATE?); pg_stat_activity={last!r}"
    )


async def _new_account(session: AsyncSession, tag: str) -> str:
    account_id = f"acc_aud03race_{tag}_{uuid4().hex[:10]}"
    now = datetime.now(UTC)
    session.add(
        InvestmentAccountRow(
            id=account_id,
            user_id=None,
            name=f"AUD-03 race {tag}",
            type="simulated",
            status="active",
            currency="EUR",
            base_currency="EUR",
            initial_deposit=Decimal("0"),
            leverage=Decimal("1"),
            is_default=False,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    return account_id


async def _new_profile(session: AsyncSession, tag: str) -> str:
    profile_id = f"PROF-AUD03RACE-{tag}-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    session.add(
        InvestorProfileRow(
            id=profile_id,
            name=f"AUD-03 race {tag}",
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
            created_at=now,
            updated_at=now,
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


@asynccontextmanager
async def _seeded(tag: str) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], str, str, str]]:
    async with _race_env() as (factory, dsn):
        async with factory() as session:
            account_id = await _new_account(session, tag)
            profile_id = await _new_profile(session, tag)
            await session.commit()
        try:
            yield factory, dsn, account_id, profile_id
        finally:
            await _cleanup(factory, [account_id], [profile_id])


async def _assert_no_orphans(dsn: str) -> None:
    assert await asyncio.to_thread(orphan_accounts, dsn) == [], "quedó una cuenta huérfana"


# --------------------------------------------------------------- participantes


async def _assign_attempt(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    profile_id: str,
    *,
    started: asyncio.Event,
    holder: dict[str, Any],
) -> str:
    """Intenta asignar (protocolo del repositorio); 404 → ``"rejected"``."""
    async with factory() as session:
        holder["pid"] = await _pid(session)
        started.set()
        repo = SqlAlchemyInvestorProfileRepository(session)
        try:
            await repo.assign_to_account(account_id, profile_id)
        except ValueError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "assigned"


async def _assign_and_hold(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
    profile_id: str,
    *,
    assigned: asyncio.Event,
    release: asyncio.Event,
    holder: dict[str, Any],
) -> str:
    """Asigna y retiene la transacción (lock sobre el perfil) hasta ``release``."""
    async with factory() as session:
        repo = SqlAlchemyInvestorProfileRepository(session)
        holder["pid"] = await _pid(session)
        await repo.assign_to_account(account_id, profile_id)
        await session.flush()
        assigned.set()
        await release.wait()
        await session.commit()
        return "assigned"


async def _delete_attempt(
    factory: async_sessionmaker[AsyncSession],
    profile_id: str,
    *,
    started: asyncio.Event,
    holder: dict[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    async with factory() as session:
        repo = SqlAlchemyInvestorProfileRepository(session)
        holder["pid"] = await _pid(session)
        started.set()
        deleted, in_use = await repo.delete_if_unused(profile_id)
        await session.commit()
        return deleted, in_use


async def _raw_statement(
    factory: async_sessionmaker[AsyncSession],
    sql: str,
    params: dict[str, Any],
    *,
    started: asyncio.Event,
    holder: dict[str, Any],
    executed: asyncio.Event | None = None,
    hold: asyncio.Event | None = None,
) -> str:
    """Ejecuta SQL crudo (ignora el protocolo de lock); ``IntegrityError`` → marcador."""
    async with factory() as session:
        holder["pid"] = await _pid(session)
        started.set()
        try:
            await session.execute(text(sql), params)
        except IntegrityError:
            await session.rollback()
            return "fk_violation"
        if executed is not None:
            executed.set()
        if hold is not None:
            await hold.wait()
        await session.commit()
        return "ok"


# ----------------------------------------------------------------------- casos


async def test_delete_wins_and_assignment_is_rejected_without_writing() -> None:
    async with _seeded("delwins") as (factory, dsn, account_id, profile_id):
        started: asyncio.Event = asyncio.Event()
        holder: dict[str, Any] = {}

        async with factory() as session_a:
            repo_a = SqlAlchemyInvestorProfileRepository(session_a)
            # El mismo lock que toma ``delete_if_unused`` (``_lock_profile``).
            row = (
                await session_a.execute(
                    select(InvestorProfileRow)
                    .where(InvestorProfileRow.id == profile_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            assert row is not None

            task = asyncio.create_task(
                _assign_attempt(
                    factory, account_id, profile_id, started=started, holder=holder
                )
            )
            await started.wait()
            blockers = await _wait_blocked(dsn, holder["pid"], task=task)
            assert blockers, "la asignación debía esperar el lock del perfil"

            deleted, in_use = await repo_a.delete_if_unused(profile_id)
            assert deleted is True
            assert in_use == ()
            await session_a.commit()

            assert await task == "rejected", "la asignación debía recibir 404 al ganar el borrado"

        async with factory() as session:
            account = await session.get(InvestmentAccountRow, account_id)
            profile = await session.get(InvestorProfileRow, profile_id)
            assert account is not None
            assert account.active_profile_id is None, "la asignación rechazada escribió la cuenta"
            assert profile is None, "el perfil debía estar borrado"

        await _assert_no_orphans(dsn)


async def test_assignment_wins_and_delete_reports_the_account() -> None:
    async with _seeded("assignwins") as (factory, dsn, account_id, profile_id):
        assigned: asyncio.Event = asyncio.Event()
        release: asyncio.Event = asyncio.Event()
        assign_holder: dict[str, Any] = {}
        delete_started: asyncio.Event = asyncio.Event()
        delete_holder: dict[str, Any] = {}

        assign_task = asyncio.create_task(
            _assign_and_hold(
                factory,
                account_id,
                profile_id,
                assigned=assigned,
                release=release,
                holder=assign_holder,
            )
        )
        await assigned.wait()

        delete_task = asyncio.create_task(
            _delete_attempt(factory, profile_id, started=delete_started, holder=delete_holder)
        )
        await delete_started.wait()
        blockers = await _wait_blocked(dsn, delete_holder["pid"], task=delete_task)
        assert blockers, "el borrado debía esperar el lock del perfil"

        release.set()
        assert await assign_task == "assigned"

        deleted, in_use = await delete_task
        assert deleted is False, "el borrado no puede eliminar un perfil con cuentas"
        assert in_use == ("AUD-03 race assignwins",), in_use

        async with factory() as session:
            account = await session.get(InvestmentAccountRow, account_id)
            profile = await session.get(InvestorProfileRow, profile_id)
            assert profile is not None
            assert account is not None and account.active_profile_id == profile_id

        await _assert_no_orphans(dsn)


async def test_fk_backstop_when_the_assignment_ignores_the_lock() -> None:
    """UPDATE crudo sin commit, DELETE crudo: el DELETE bloquea y viola la FK."""
    async with _seeded("rawupdate") as (factory, dsn, account_id, profile_id):
        update_started: asyncio.Event = asyncio.Event()
        update_executed: asyncio.Event = asyncio.Event()
        update_release = asyncio.Event()
        update_holder: dict[str, Any] = {}
        delete_started: asyncio.Event = asyncio.Event()
        delete_holder: dict[str, Any] = {}

        update_task = asyncio.create_task(
            _raw_statement(
                factory,
                "UPDATE investment_accounts SET active_profile_id = :pid WHERE id = :acc",
                {"pid": profile_id, "acc": account_id},
                started=update_started,
                executed=update_executed,
                holder=update_holder,
                hold=update_release,
            )
        )
        await update_started.wait()
        # La escritura ha tomado la referencia (KEY SHARE sobre el perfil) y sigue SIN
        # commit: es lo que hace esperar al DELETE.
        await update_executed.wait()
        delete_task = asyncio.create_task(
            _raw_statement(
                factory,
                "DELETE FROM investor_profiles WHERE id = :pid",
                {"pid": profile_id},
                started=delete_started,
                holder=delete_holder,
            )
        )
        await delete_started.wait()
        await _wait_blocked(dsn, delete_holder["pid"], task=delete_task)

        update_release.set()
        assert await update_task == "ok"
        assert await delete_task == "fk_violation", "la FK RESTRICT debía abortar el DELETE"

        async with factory() as session:
            account = await session.get(InvestmentAccountRow, account_id)
            profile = await session.get(InvestorProfileRow, profile_id)
            assert profile is not None
            assert account is not None and account.active_profile_id == profile_id

        await _assert_no_orphans(dsn)


async def test_fk_backstop_when_the_delete_ignores_the_lock() -> None:
    """DELETE crudo sin commit, UPDATE crudo: el UPDATE bloquea y viola la FK."""
    async with _seeded("rawdelete") as (factory, dsn, account_id, profile_id):
        delete_started: asyncio.Event = asyncio.Event()
        delete_executed: asyncio.Event = asyncio.Event()
        delete_holder: dict[str, Any] = {}
        hold = asyncio.Event()
        update_started: asyncio.Event = asyncio.Event()
        update_holder: dict[str, Any] = {}

        delete_task = asyncio.create_task(
            _raw_statement(
                factory,
                "DELETE FROM investor_profiles WHERE id = :pid",
                {"pid": profile_id},
                started=delete_started,
                executed=delete_executed,
                holder=delete_holder,
                hold=hold,
            )
        )
        await delete_started.wait()
        await delete_executed.wait()

        update_task = asyncio.create_task(
            _raw_statement(
                factory,
                "UPDATE investment_accounts SET active_profile_id = :pid WHERE id = :acc",
                {"pid": profile_id, "acc": account_id},
                started=update_started,
                holder=update_holder,
            )
        )
        await update_started.wait()
        await _wait_blocked(dsn, update_holder["pid"], task=update_task)

        hold.set()
        assert await delete_task == "ok"
        assert await update_task == "fk_violation", "la FK debía rechazar una referencia muerta"

        async with factory() as session:
            account = await session.get(InvestmentAccountRow, account_id)
            profile = await session.get(InvestorProfileRow, profile_id)
            assert profile is None
            assert account is not None and account.active_profile_id is None

        await _assert_no_orphans(dsn)
