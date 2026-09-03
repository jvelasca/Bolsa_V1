"""V1.87 — PostgreSQL lifecycle event store: Alembic schema + snapshot + concurrency.

Requires DATABASE_URL / bolsa-postgres. Fails (does not skip) when env
LIFECYCLE_PG_REQUIRED=1 is set (release-tag lifecycle-pg job).
Does NOT create tables from SQLAlchemy metadata — Alembic must have run.
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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

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
            f"lifecycle-pg required but PostgreSQL/Alembic unavailable: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic no disponible: {exc}")


@pytest_asyncio.fixture
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
            events = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'lifecycle_events'"
                )
            )
            if events.scalar() is None:
                raise RuntimeError(
                    "lifecycle_events missing — run alembic upgrade head"
                )
            seq = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'lifecycle_events' "
                    "AND column_name = 'sequence_no'"
                )
            )
            if seq.scalar() is None:
                raise RuntimeError(
                    "lifecycle_events.sequence_no missing — Alembic 016 required"
                )
            version = await conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            versions = {row[0] for row in version}
            if "019_outbox_position_fifo" not in versions:
                raise RuntimeError(
                    f"alembic_version is {versions!r}; "
                    "expected 019_outbox_position_fifo"
                )
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        _require_or_skip(exc)
        raise  # unreachable

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(pg_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    from bolsa_infrastructure.database.session import create_session_factory

    factory = create_session_factory(pg_engine)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _cleanup(session: AsyncSession, pos: str) -> None:
    await session.execute(
        text("DELETE FROM lifecycle_events WHERE position_id = :p"),
        {"p": pos},
    )
    await session.execute(
        text("DELETE FROM lifecycle_aggregates WHERE position_id = :p"),
        {"p": pos},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_alembic_head_has_sequence_and_aggregates(
    db_session: AsyncSession,
) -> None:
    version = (
        await db_session.execute(text("SELECT version_num FROM alembic_version"))
    ).scalar_one()
    assert str(version).startswith("019")
    seq = (
        await db_session.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'lifecycle_events' AND column_name = 'sequence_no'"
            )
        )
    ).scalar()
    assert seq == 1
    agg = (
        await db_session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'lifecycle_aggregates'"
            )
        )
    ).scalar()
    assert agg == 1
    uidx = (
        await db_session.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE indexname = 'lifecycle_events_position_seq_uidx'"
            )
        )
    ).scalar()
    assert uidx == 1


@pytest.mark.asyncio
async def test_pg_open_t1_close_fresh_session_same_snapshot(
    db_session: AsyncSession,
    pg_engine: AsyncEngine,
) -> None:
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_domain.lifecycle import LifecycleEventInput
    from bolsa_infrastructure.database.session import create_session_factory

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
    seqs = [ev["sequenceNo"] for ev in snap1["events"]]
    assert seqs == list(range(1, len(seqs) + 1))
    assert abs(
        snap1["accounting"]["totalEquity"]
        - (
            snap1["accounting"]["initialEquity"]
            + snap1["accounting"]["realizedPnl"]
            + snap1["accounting"]["unrealizedPnl"]
        )
    ) < 1e-6

    factory = create_session_factory(pg_engine)
    async with factory() as session2:
        store2 = PostgresLifecycleEventStore(session2)
        snap2 = await GetLifecycleSnapshot(store2).execute(pos)
        assert snap2["stage"] == snap1["stage"]
        assert snap2["accounting"] == snap1["accounting"]
        assert len(snap2["events"]) == len(snap1["events"])
        assert [e["sequenceNo"] for e in snap2["events"]] == seqs

    await _cleanup(db_session, pos)


@pytest.mark.asyncio
async def test_pg_concurrent_duplicate_t1_one_wins(
    db_session: AsyncSession,
    pg_engine: AsyncEngine,
) -> None:
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_domain.lifecycle import LifecycleEventInput
    from bolsa_infrastructure.database.session import create_session_factory

    pos = f"pos-race-{uuid4().hex[:12]}"
    store = PostgresLifecycleEventStore(db_session)
    opened = await AppendLifecycleEvent(store).execute(
        LifecycleEventInput(kind="POSITION_OPENED", position_id=pos)  # type: ignore[arg-type]
    )
    assert opened.ok, getattr(opened.error, "message", None)
    await db_session.commit()

    factory: async_sessionmaker[AsyncSession] = create_session_factory(pg_engine)

    async def _worker(fill_id: str, event_id: str):
        async with factory() as session:
            uc = AppendLifecycleEvent(PostgresLifecycleEventStore(session))
            result = await uc.execute(
                LifecycleEventInput(
                    kind="T1_EXECUTED",
                    position_id=pos,
                    fill_id=fill_id,
                    event_id=event_id,
                    quantity=5,
                    price=105,
                )
            )
            if result.ok:
                await session.commit()
            else:
                await session.rollback()
            return result

    r1, r2 = await asyncio.gather(
        _worker("fill-race-a", "evt-race-a"),
        _worker("fill-race-b", "evt-race-b"),
    )
    oks = [r1.ok, r2.ok]
    assert oks.count(True) == 1, (
        getattr(r1.error, "message", None),
        getattr(r2.error, "message", None),
    )
    assert oks.count(False) == 1
    loser = r1 if not r1.ok else r2
    assert loser.error is not None
    assert loser.error.code == "illegal_transition"

    snap = await GetLifecycleSnapshot(store).execute(pos)
    seqs = [ev["sequenceNo"] for ev in snap["events"]]
    assert seqs == [1, 2]
    kinds = [ev["kind"] for ev in snap["events"]]
    assert kinds == ["POSITION_OPENED", "T1_EXECUTED"]

    await _cleanup(db_session, pos)


@pytest.mark.asyncio
async def test_pg_t2_append_many_crash_mid_pair_rolls_back(
    db_session: AsyncSession,
) -> None:
    """V1.97 — inject after T2_TRIGGERED inside one savepoint → 0 orphan trigger."""
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_domain.lifecycle import LifecycleEventInput

    pos = f"pos-t2-atom-{uuid4().hex[:12]}"
    boom = {"n": 0}

    async def _crash(index: int, _event: object) -> None:
        if index == 0:
            boom["n"] += 1
            if boom["n"] == 1:
                raise RuntimeError("injected crash after T2_TRIGGERED")

    store = PostgresLifecycleEventStore(db_session)
    append = AppendLifecycleEvent(store)
    for kind, at, eid in (
        ("POSITION_OPENED", "2026-09-03T10:00:00.000Z", f"{pos}-open"),
        ("T1_EXECUTED", "2026-09-03T11:00:00.000Z", f"{pos}-t1"),
    ):
        kwargs: dict = {"kind": kind, "position_id": pos, "at": at, "event_id": eid}
        if kind == "T1_EXECUTED":
            kwargs.update(fill_id=eid, quantity=5, price=105, fees=0)
        result = await append.execute(LifecycleEventInput(**kwargs))  # type: ignore[arg-type]
        assert result.ok, getattr(result.error, "message", None)

    store.on_after_append_index = _crash
    with pytest.raises(RuntimeError, match="injected crash"):
        await append.execute(
            LifecycleEventInput(
                kind="T2_EXECUTED",
                position_id=pos,
                at="2026-09-03T12:00:00.000Z",
                event_id=f"{pos}-t2",
                fill_id=f"{pos}-t2",
                quantity=3,
                price=110,
                fees=0,
                reason="TARGET_2",
            )
        )

    # Outer TX may still be open; rollback nested left no new events.
    snap = await GetLifecycleSnapshot(store).execute(pos)
    kinds = [e["kind"] for e in snap["events"]]
    assert kinds == ["POSITION_OPENED", "T1_EXECUTED"]
    assert "T2_TRIGGERED" not in kinds

    store.on_after_append_index = None
    ok = await append.execute(
        LifecycleEventInput(
            kind="T2_EXECUTED",
            position_id=pos,
            at="2026-09-03T12:00:00.000Z",
            event_id=f"{pos}-t2",
            fill_id=f"{pos}-t2",
            quantity=3,
            price=110,
            fees=0,
            reason="TARGET_2",
        )
    )
    assert ok.ok, getattr(ok.error, "message", None)
    await db_session.commit()
    snap2 = await GetLifecycleSnapshot(store).execute(pos)
    kinds2 = [e["kind"] for e in snap2["events"]]
    assert kinds2.count("T2_TRIGGERED") == 1
    assert kinds2.count("T2_EXECUTED") == 1

    await _cleanup(db_session, pos)
