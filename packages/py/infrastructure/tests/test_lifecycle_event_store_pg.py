"""V1.86 — PostgreSQL lifecycle event store: POST→GET + fresh session ≡ snapshot.

Requires DATABASE_URL / bolsa-postgres. Fails (does not skip) when env
LIFECYCLE_PG_REQUIRED=1 is set (release-tag lifecycle-pg job).
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
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


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get("LIFECYCLE_PG_REQUIRED") == "1":
        raise AssertionError(
            f"lifecycle-pg required but PostgreSQL unavailable: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL no disponible: {exc}")


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
        _require_or_skip(exc)
        raise  # unreachable

    # Ensure migration table exists (best-effort create via metadata for CI)
    from bolsa_infrastructure.database.models.tables import LifecycleEventRow

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: LifecycleEventRow.__table__.create(
                sync_conn, checkfirst=True
            )
        )

    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


@pytest.mark.asyncio
async def test_pg_open_t1_close_fresh_session_same_snapshot(
    db_session: AsyncSession,
) -> None:
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_domain.lifecycle import LifecycleEventInput
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    pos = f"pos-pg-{uuid4().hex[:12]}"
    store = PostgresLifecycleEventStore(db_session)
    append = AppendLifecycleEvent(store)

    for kind in (
        "POSITION_OPENED",
        "T1_EXECUTED",
        "TRAIL_APPLIED",
        "EXIT_REQUIRED",
        "POSITION_CLOSED",
    ):
        result = await append.execute(
            LifecycleEventInput(kind=kind, position_id=pos)  # type: ignore[arg-type]
        )
        assert result.ok, getattr(result.error, "message", None)

    await db_session.commit()
    snap1 = await GetLifecycleSnapshot(store).execute(pos)
    assert snap1["stage"] == "closed"
    assert snap1["accounting"]["cash"] == 100_055
    assert snap1["accounting"]["totalEquity"] == 100_055
    assert abs(
        snap1["accounting"]["totalEquity"]
        - (
            snap1["accounting"]["initialEquity"]
            + snap1["accounting"]["realizedPnl"]
            + snap1["accounting"]["unrealizedPnl"]
        )
    ) < 1e-6

    # Fresh engine/session (= restart-session semantics without killing API process)
    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session2:
        store2 = PostgresLifecycleEventStore(session2)
        snap2 = await GetLifecycleSnapshot(store2).execute(pos)
        assert snap2["stage"] == snap1["stage"]
        assert snap2["accounting"] == snap1["accounting"]
        assert len(snap2["events"]) == len(snap1["events"])
    await engine.dispose()

    # Cleanup
    await db_session.execute(
        text("DELETE FROM lifecycle_events WHERE position_id = :p"),
        {"p": pos},
    )
    await db_session.commit()
