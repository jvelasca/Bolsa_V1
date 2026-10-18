"""P2/v111 — persistencia durable de la verificación DÍA-D enlazada a un ciclo (PG, gated).

Cubre la tabla aditiva ``dia_d_cycle_verifications`` y su repositorio:

* la tabla/índices están en head y la head es ``056_auto_ops_jobs``;
* ``upsert`` es idempotente y ATÓMICO por ``(account_id, cycle_id, dia_d, end_date, mode)``;
* ``list_verifications`` acota por cuenta y por ciclo;
* el ciclo ya verificado por OTRA cuenta se RECHAZA (nunca se reasigna ni se duplica);
* los huecos de identidad se persisten como ``NULL`` («Sin dato todavía»), nunca ``""``;
* el ``downgrade``/``upgrade`` de la 054 y de la 055 dejan el esquema como estaba (roundtrip).

Requiere PostgreSQL. Es GATE cuando ``DIA_D_CYCLE_VERIFICATION_PG_REQUIRED=1``; si no, ``pytest.skip``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.repositories.dia_d_cycle_verification_repository import (
    DiaDCycleVerificationOwnershipConflictError,
    SqlAlchemyDiaDCycleVerificationRepository,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED = "DIA_D_CYCLE_VERIFICATION_PG_REQUIRED"
_ALEMBIC_HEAD = "056_auto_ops_jobs"
_TABLE = "dia_d_cycle_verifications"
_CYCLE_PREFIX = "itest-p2-"


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def pg_session() -> AsyncIterator[AsyncSession]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        if os.environ.get(_REQUIRED) == "1":
            raise AssertionError(f"PG required but unavailable: {exc}") from exc
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_table_and_indexes_exist_at_head(pg_session: AsyncSession) -> None:
    exists = (
        await pg_session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=:t"
            ),
            {"t": _TABLE},
        )
    ).scalar_one_or_none()
    assert exists is not None
    for index in (
        "dia_d_cycle_verifications_cycle_id_idx",
        "dia_d_cycle_verifications_cycle_key",
    ):
        found = (
            await pg_session.execute(
                text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
                {"n": index},
            )
        ).scalar_one_or_none()
        assert found is not None, index


@pytest.mark.asyncio
async def test_upsert_is_idempotent_by_natural_key(pg_session: AsyncSession) -> None:
    repo = SqlAlchemyDiaDCycleVerificationRepository(pg_session)
    cycle = f"{_CYCLE_PREFIX}idem"
    first = await repo.upsert(
        cycle_id=cycle,
        instrument_id="inst-1",
        symbol="ACS",
        dia_d="2026-04-01",
        end_date="2026-04-02",
        mode="auto",
        account_id="acc-p2",
        band="favorable",
        result={"band": "favorable"},
    )
    await pg_session.flush()
    second = await repo.upsert(
        cycle_id=cycle,
        instrument_id="inst-1",
        symbol="ACS",
        dia_d="2026-04-01",
        end_date="2026-04-02",
        mode="auto",
        account_id="acc-p2",
        band="mixed",
        result={"band": "mixed"},
    )
    assert first.id == second.id
    assert second.band == "mixed"
    rows = await repo.list_verifications(account_id="acc-p2", cycle_id=cycle)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_upsert_declares_gaps_as_null(pg_session: AsyncSession) -> None:
    repo = SqlAlchemyDiaDCycleVerificationRepository(pg_session)
    cycle = f"{_CYCLE_PREFIX}gaps"
    row = await repo.upsert(
        cycle_id=cycle,
        instrument_id="inst-2",
        symbol="ITX",
        dia_d="2026-05-01",
        end_date="2026-05-02",
        mode="auto",
        account_id="acc-p2",
    )
    assert row.strategy_preset_key is None
    assert row.strategy_version is None
    assert row.result == {}


@pytest.mark.asyncio
async def test_upsert_persists_identity_gap_as_null(pg_session: AsyncSession) -> None:
    """Instrumento/símbolo ausentes viajan como ``NULL`` (hueco declarado), nunca ``""``.

    Falsable: con la coerción ``facts.instrument_id or ""`` el repositorio recibía ``""`` y la
    fila guardaba cadena vacía — indistinguible de «se resolvió y está vacío».
    """
    repo = SqlAlchemyDiaDCycleVerificationRepository(pg_session)
    cycle = f"{_CYCLE_PREFIX}gap-identity"
    row = await repo.upsert(
        cycle_id=cycle,
        instrument_id=None,
        symbol=None,
        dia_d="2026-08-01",
        end_date="2026-08-02",
        mode="auto",
        account_id="acc-p2",
    )
    await pg_session.flush()
    assert row.instrument_id is None
    assert row.symbol is None
    stored = (
        await pg_session.execute(
            text(
                "SELECT instrument_id, symbol FROM dia_d_cycle_verifications "
                "WHERE cycle_id=:c AND account_id=:a"
            ),
            {"c": cycle, "a": "acc-p2"},
        )
    ).one()
    assert stored == (None, None)
    # La columna es NULLABLE en head (migración 055).
    nullable = (
        await pg_session.execute(
            text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t "
                "AND column_name IN ('instrument_id','symbol')"
            ),
            {"t": _TABLE},
        )
    ).all()
    assert sorted(nullable) == [("instrument_id", "YES"), ("symbol", "YES")]


@pytest.mark.asyncio
async def test_list_scopes_by_account_and_cycle(pg_session: AsyncSession) -> None:
    repo = SqlAlchemyDiaDCycleVerificationRepository(pg_session)
    cycle_a = f"{_CYCLE_PREFIX}a"
    cycle_b = f"{_CYCLE_PREFIX}b"
    await repo.upsert(
        cycle_id=cycle_a,
        instrument_id="i",
        symbol="A",
        dia_d="2026-06-01",
        end_date="2026-06-02",
        mode="auto",
        account_id="acc-1",
    )
    await repo.upsert(
        cycle_id=cycle_b,
        instrument_id="i",
        symbol="B",
        dia_d="2026-06-01",
        end_date="2026-06-02",
        mode="auto",
        account_id="acc-2",
    )
    await pg_session.flush()
    only_a = await repo.list_verifications(account_id="acc-1", cycle_id=cycle_a)
    assert [r.symbol for r in only_a] == ["A"]
    other_account = await repo.list_verifications(account_id="acc-2", cycle_id=cycle_a)
    assert other_account == []
    both_for_acc1 = await repo.list_verifications(account_id="acc-1")
    assert {r.cycle_id for r in both_for_acc1} >= {cycle_a}


@pytest.mark.asyncio
async def test_same_cycle_from_another_account_is_rejected_not_reassigned(
    pg_session: AsyncSession,
) -> None:
    """Un ``cycleId`` ya verificado por OTRA cuenta se declara en conflicto (409), no se pisa.

    Hallazgo 2 (endurecimiento defensivo, multi-cuenta): el defecto era ``_find`` sin
    ``account_id`` + ``SET account_id`` ⇒ la cuenta B «robaba» la fila de A. Con la clave natural
    acotada por ``account_id`` el ``ON CONFLICT`` ya no puede tocar la fila ajena; la guarda
    explícita convierte el caso en un conflicto declarado en vez de crear una verificación fantasma.
    """
    repo = SqlAlchemyDiaDCycleVerificationRepository(pg_session)
    cycle = f"{_CYCLE_PREFIX}cross"
    row_a = await repo.upsert(
        cycle_id=cycle,
        instrument_id="i",
        symbol="A",
        dia_d="2026-07-01",
        end_date="2026-07-02",
        mode="auto",
        account_id="acc-a",
        band="favorable",
    )
    await pg_session.flush()
    with pytest.raises(DiaDCycleVerificationOwnershipConflictError):
        await repo.upsert(
            cycle_id=cycle,
            instrument_id="i",
            symbol="B",
            dia_d="2026-07-01",
            end_date="2026-07-02",
            mode="auto",
            account_id="acc-b",
            band="mixed",
        )
    # La fila de A sigue siendo de A y CONSERVA su banda: no hubo reasignación.
    rows_a = await repo.list_verifications(account_id="acc-a", cycle_id=cycle)
    assert [r.id for r in rows_a] == [row_a.id]
    assert [r.band for r in rows_a] == ["favorable"]
    assert await repo.list_verifications(account_id="acc-b", cycle_id=cycle) == []


@pytest.mark.asyncio
async def test_migration_054_roundtrip(pg_session: AsyncSession) -> None:
    """``downgrade``/``upgrade`` de la 054 dejan la tabla como estaba."""
    pytest.importorskip("alembic")
    from alembic import command
    from sqlalchemy import create_engine

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import _alembic_config, alembic_head

    settings = get_settings()
    url = settings.database_url
    assert url is not None
    url = url.replace("postgresql://", "postgresql+psycopg://", 1).split("?", 1)[0]
    engine = create_engine(url)
    cfg = _alembic_config()

    def _has_facts_hash(connection: object) -> bool:
        row = connection.execute(  # type: ignore[attr-defined]
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t AND column_name='facts_hash'"
            ),
            {"t": _TABLE},
        ).scalar_one_or_none()
        return row is not None

    try:
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, "053_dia_d_cycle_verifications")
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            assert _has_facts_hash(connection) is False

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            assert _has_facts_hash(connection) is True
        assert alembic_head() == _ALEMBIC_HEAD
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_migration_055_identity_nullable_roundtrip(pg_session: AsyncSession) -> None:
    """``downgrade``/``upgrade`` de la 055 conmutan la nulabilidad de la identidad."""
    pytest.importorskip("alembic")
    from alembic import command
    from sqlalchemy import create_engine

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import _alembic_config, alembic_head

    settings = get_settings()
    url = settings.database_url
    assert url is not None
    url = url.replace("postgresql://", "postgresql+psycopg://", 1).split("?", 1)[0]
    engine = create_engine(url)
    cfg = _alembic_config()

    def _identity_nullable(connection: object) -> dict[str, str]:
        rows = connection.execute(  # type: ignore[attr-defined]
            text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t "
                "AND column_name IN ('instrument_id','symbol')"
            ),
            {"t": _TABLE},
        ).all()
        return {name: nullable for name, nullable in rows}

    try:
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, "054_dia_d_verified_and_alerts")
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            assert _identity_nullable(connection) == {
                "instrument_id": "NO",
                "symbol": "NO",
            }

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            assert _identity_nullable(connection) == {
                "instrument_id": "YES",
                "symbol": "YES",
            }
        assert alembic_head() == _ALEMBIC_HEAD
    finally:
        engine.dispose()
