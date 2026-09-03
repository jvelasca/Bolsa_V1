"""V1.92 — Certify LifecycleOutboxWorker real against PostgreSQL.

Happy path · fail/retry · stale reclaim · two workers same position FIFO.
Requires DATABASE_URL. Fails hard when LIFECYCLE_PG_REQUIRED=1.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


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
        raise

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    pg_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    from bolsa_infrastructure.database.session import create_session_factory

    return create_session_factory(pg_engine)


def _direct(
    *,
    kind: str,
    position_id: str,
    account_id: str,
    event_id: str,
    at: str,
) -> dict[str, Any]:
    # Omit qty/price — domain fills fixture defaults (avoids remaining mismatch).
    return {
        "direct_input": {
            "kind": kind,
            "positionId": position_id,
            "accountId": account_id,
            "eventId": event_id,
            "at": at,
            "instrumentId": "inst-w",
        }
    }


async def _enqueue(
    factory: async_sessionmaker[AsyncSession],
    *,
    position_id: str,
    account_id: str,
    transaction_id: str,
    kind: str,
    payload: dict[str, Any],
    created_at: datetime | None = None,
) -> str:
    from bolsa_application.lifecycle_outbox import PostgresLifecycleOutboxStore
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    async with factory() as session:
        store = PostgresLifecycleOutboxStore(session)
        row = await store.enqueue(
            position_id=position_id,
            account_id=account_id,
            transaction_id=transaction_id,
            kind=kind,
            payload=payload,
        )
        if created_at is not None:
            db_row = await session.get(LifecycleOutboxRow, row.id)
            assert db_row is not None
            db_row.created_at = created_at
            db_row.updated_at = created_at
        await session.commit()
        return row.id


async def _status(
    factory: async_sessionmaker[AsyncSession], outbox_id: str
) -> str | None:
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    async with factory() as session:
        row = await session.get(LifecycleOutboxRow, outbox_id)
        return None if row is None else row.status


async def _wait_status(
    factory: async_sessionmaker[AsyncSession],
    outbox_id: str,
    expected: str,
    *,
    timeout: float = 5.0,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if await _status(factory, outbox_id) == expected:
            return
        await asyncio.sleep(0.05)
    got = await _status(factory, outbox_id)
    raise AssertionError(f"outbox {outbox_id} status={got!r} expected={expected!r}")


async def _cleanup(
    factory: async_sessionmaker[AsyncSession], *, position_id: str
) -> None:
    async with factory() as session:
        await session.execute(
            text("DELETE FROM lifecycle_outbox WHERE position_id = :p"),
            {"p": position_id},
        )
        await session.execute(
            text("DELETE FROM lifecycle_events WHERE position_id = :p"),
            {"p": position_id},
        )
        await session.execute(
            text("DELETE FROM lifecycle_aggregates WHERE position_id = :p"),
            {"p": position_id},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_worker_pending_to_applied(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )

    pos = f"pos-w-happy-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-open-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )
    task = start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
    assert task is not None
    try:
        await _wait_status(session_factory, oid, "applied")
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
        assert snap["stage"] == "open"
        assert snap["events"][0]["kind"] == "POSITION_OPENED"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_worker_fail_backoff_retry(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import AppendLifecycleEvent

    calls = {"n": 0}
    real_execute = AppendLifecycleEvent.execute

    async def _fail_once(self: AppendLifecycleEvent, input_event: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            from bolsa_application.lifecycle_event_store import AppendLifecycleResult
            from bolsa_domain.lifecycle import LifecycleAppendError

            return AppendLifecycleResult(
                ok=False,
                error=LifecycleAppendError(code="invalid_payload", message="injected"),
            )
        return await real_execute(self, input_event)

    monkeypatch.setattr(AppendLifecycleEvent, "execute", _fail_once)
    monkeypatch.setattr(
        "bolsa_application.lifecycle_outbox._backoff_seconds",
        lambda attempts: 0,
    )

    pos = f"pos-w-retry-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-retry-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )
    task = start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
    assert task is not None
    try:
        await _wait_status(session_factory, oid, "applied", timeout=8.0)
        assert calls["n"] >= 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_worker_stale_reclaim_after_crash(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_outbox import OUTBOX_STALE_PROCESSING_SECONDS
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-stale-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-stale-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )
    # Simulate crashed worker: row stuck in processing with old claimed_at.
    async with session_factory() as session:
        row = await session.get(LifecycleOutboxRow, oid)
        assert row is not None
        row.status = "processing"
        row.claimed_at = datetime.now(UTC) - timedelta(
            seconds=OUTBOX_STALE_PROCESSING_SECONDS + 5
        )
        await session.commit()

    task = start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
    assert task is not None
    try:
        await _wait_status(session_factory, oid, "applied")
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_two_workers_same_position_fifo_open_t1_exit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-fifo-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    base = datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)
    events = [
        ("tx-open", "POSITION_OPENED", "2026-09-03T12:00:00.000Z", base),
        ("tx-t1", "T1_EXECUTED", "2026-09-03T12:30:00.000Z", base + timedelta(seconds=1)),
        (
            "tx-exit",
            "POSITION_CLOSED",
            "2026-09-03T13:00:00.000Z",
            base + timedelta(seconds=2),
        ),
    ]
    ids: list[str] = []
    for tx, kind, at, created in events:
        oid = await _enqueue(
            session_factory,
            position_id=pos,
            account_id=acc,
            transaction_id=tx,
            kind=kind,
            payload=_direct(
                kind=kind,
                position_id=pos,
                account_id=acc,
                event_id=tx,
                at=at,
            ),
            created_at=created,
        )
        ids.append(oid)

    task_a = start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
    task_b = start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
    assert task_a is not None and task_b is not None
    try:
        for oid in ids:
            await _wait_status(session_factory, oid, "applied", timeout=10.0)
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
            dead = (
                await session.execute(
                    select(LifecycleOutboxRow).where(
                        LifecycleOutboxRow.position_id == pos,
                        LifecycleOutboxRow.status == "dead",
                    )
                )
            ).scalars().all()
        assert snap["stage"] == "closed"
        kinds = [e["kind"] for e in snap["events"]]
        assert kinds == ["POSITION_OPENED", "T1_EXECUTED", "POSITION_CLOSED"]
        assert dead == []
    finally:
        task_a.cancel()
        task_b.cancel()
        await asyncio.gather(task_a, task_b, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_crash_after_claim_then_stale_reclaim(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V1.93 — TX1 commits processing; crash before apply; stale reclaim → applied."""
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_application.lifecycle_outbox import OUTBOX_STALE_PROCESSING_SECONDS
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-crash-claim-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-crash-claim-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )

    boom = {"n": 0}

    async def _after_claim(claimed: list[Any]) -> None:
        boom["n"] += 1
        if boom["n"] == 1:
            raise RuntimeError("injected crash after claim")

    task = start_lifecycle_outbox_worker(
        session_factory,
        tick_seconds=0.05,
        on_after_claim=_after_claim,
    )
    assert task is not None
    try:
        await _wait_status(session_factory, oid, "processing", timeout=5.0)
        async with session_factory() as session:
            row = await session.get(LifecycleOutboxRow, oid)
            assert row is not None
            row.claimed_at = datetime.now(UTC) - timedelta(
                seconds=OUTBOX_STALE_PROCESSING_SECONDS + 5
            )
            await session.commit()
        await _wait_status(session_factory, oid, "applied", timeout=8.0)
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
        assert [e["kind"] for e in snap["events"]] == ["POSITION_OPENED"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_crash_mid_apply_before_commit_then_reclaim(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V1.93 — append in session then raise before TX2 commit → reclaim → 1 event."""
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_application.lifecycle_outbox import OUTBOX_STALE_PROCESSING_SECONDS
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-crash-mid-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-crash-mid-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )

    boom = {"n": 0}

    async def _before_commit(_outbox_id: str) -> None:
        boom["n"] += 1
        if boom["n"] == 1:
            raise RuntimeError("injected crash before apply commit")

    task = start_lifecycle_outbox_worker(
        session_factory,
        tick_seconds=0.05,
        on_before_apply_commit=_before_commit,
    )
    assert task is not None
    try:
        await _wait_status(session_factory, oid, "processing", timeout=5.0)
        async with session_factory() as session:
            row = await session.get(LifecycleOutboxRow, oid)
            assert row is not None
            row.claimed_at = datetime.now(UTC) - timedelta(
                seconds=OUTBOX_STALE_PROCESSING_SECONDS + 5
            )
            await session.commit()
        await _wait_status(session_factory, oid, "applied", timeout=8.0)
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
        assert [e["kind"] for e in snap["events"]] == ["POSITION_OPENED"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_idempotent_reclaim_after_append_without_mark(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V1.93 — event already in store + processing row → reclaim → applied, 1 event."""
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
        input_from_body,
    )
    from bolsa_application.lifecycle_outbox import OUTBOX_STALE_PROCESSING_SECONDS
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-idem-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-idem-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )
    async with session_factory() as session:
        result = await AppendLifecycleEvent(
            PostgresLifecycleEventStore(session)
        ).execute(
            input_from_body(
                _direct(
                    kind="POSITION_OPENED",
                    position_id=pos,
                    account_id=acc,
                    event_id=tx,
                    at="2026-09-03T10:00:00.000Z",
                )["direct_input"]
            )
        )
        assert result.ok
        row = await session.get(LifecycleOutboxRow, oid)
        assert row is not None
        row.status = "processing"
        row.claimed_at = datetime.now(UTC) - timedelta(
            seconds=OUTBOX_STALE_PROCESSING_SECONDS + 5
        )
        await session.commit()

    task = start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
    assert task is not None
    try:
        await _wait_status(session_factory, oid, "applied", timeout=8.0)
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
        assert [e["kind"] for e in snap["events"]] == ["POSITION_OPENED"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_three_workers_same_position_fifo(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-3w-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    base = datetime(2026, 9, 3, 14, 0, 0, tzinfo=UTC)
    events = [
        ("tx-open", "POSITION_OPENED", "2026-09-03T14:00:00.000Z", base),
        ("tx-t1", "T1_EXECUTED", "2026-09-03T14:30:00.000Z", base + timedelta(seconds=1)),
        (
            "tx-exit",
            "POSITION_CLOSED",
            "2026-09-03T15:00:00.000Z",
            base + timedelta(seconds=2),
        ),
    ]
    ids: list[str] = []
    for tx, kind, at, created in events:
        oid = await _enqueue(
            session_factory,
            position_id=pos,
            account_id=acc,
            transaction_id=tx,
            kind=kind,
            payload=_direct(
                kind=kind,
                position_id=pos,
                account_id=acc,
                event_id=tx,
                at=at,
            ),
            created_at=created,
        )
        ids.append(oid)

    tasks = [
        start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
        for _ in range(3)
    ]
    assert all(t is not None for t in tasks)
    try:
        for oid in ids:
            await _wait_status(session_factory, oid, "applied", timeout=12.0)
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
            dead = (
                await session.execute(
                    select(LifecycleOutboxRow).where(
                        LifecycleOutboxRow.position_id == pos,
                        LifecycleOutboxRow.status == "dead",
                    )
                )
            ).scalars().all()
        assert [e["kind"] for e in snap["events"]] == [
            "POSITION_OPENED",
            "T1_EXECUTED",
            "POSITION_CLOSED",
        ]
        assert dead == []
    finally:
        for t in tasks:
            assert t is not None
            t.cancel()
        await asyncio.gather(*[t for t in tasks if t is not None], return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_worker_reconnect_after_engine_dispose(
    session_factory: async_sessionmaker[AsyncSession],
    pg_engine: AsyncEngine,
) -> None:
    """V1.93 — dispose engine mid-flight; new factory continues to apply."""
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_infrastructure.database.session import create_session_factory

    pos = f"pos-w-reconn-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-reconn-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )

    holder: dict[str, async_sessionmaker[AsyncSession]] = {"factory": session_factory}

    class _ProxyFactory:
        def __call__(self) -> Any:
            return holder["factory"]()

    task = start_lifecycle_outbox_worker(_ProxyFactory(), tick_seconds=0.05)  # type: ignore[arg-type]
    assert task is not None
    try:
        await asyncio.sleep(0.08)
        await pg_engine.dispose()
        holder["factory"] = create_session_factory(pg_engine)
        await _wait_status(holder["factory"], oid, "applied", timeout=10.0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(holder["factory"], position_id=pos)


@pytest.mark.asyncio
async def test_kick_and_worker_concurrent_single_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V1.93 — HTTP kick drain + worker race → exactly one event, no dead."""
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_application.lifecycle_outbox import (
        PostgresLifecycleOutboxStore,
        drain_lifecycle_outbox,
    )
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-kick-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx = f"tx-w-kick-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)
    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx,
        kind="POSITION_OPENED",
        payload=_direct(
            kind="POSITION_OPENED",
            position_id=pos,
            account_id=acc,
            event_id=tx,
            at="2026-09-03T10:00:00.000Z",
        ),
    )

    task = start_lifecycle_outbox_worker(session_factory, tick_seconds=0.05)
    assert task is not None
    try:

        async def _kick() -> None:
            async with session_factory() as session:
                await drain_lifecycle_outbox(
                    PostgresLifecycleOutboxStore(session),
                    AppendLifecycleEvent(PostgresLifecycleEventStore(session)),
                )
                await session.commit()

        await asyncio.gather(_kick(), _kick(), _kick())
        await _wait_status(session_factory, oid, "applied", timeout=8.0)
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
            dead = (
                await session.execute(
                    select(LifecycleOutboxRow).where(
                        LifecycleOutboxRow.position_id == pos,
                        LifecycleOutboxRow.status == "dead",
                    )
                )
            ).scalars().all()
        assert [e["kind"] for e in snap["events"]] == ["POSITION_OPENED"]
        assert dead == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)


@pytest.mark.asyncio
async def test_t2_crash_mid_pair_then_reclaim_exactly_one_each(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V1.97 — crash after T2_TRIGGERED inside append_many → reclaim → 1+1 events."""
    from bolsa_api.background.lifecycle_outbox_worker import (
        start_lifecycle_outbox_worker,
    )
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
    )
    from bolsa_application.lifecycle_outbox import OUTBOX_STALE_PROCESSING_SECONDS
    from bolsa_domain.lifecycle import LifecycleEventInput
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    pos = f"pos-w-t2-atom-{uuid4().hex[:10]}"
    acc = f"acc-w-{uuid4().hex[:8]}"
    tx_t2 = f"tx-w-t2-{uuid4().hex[:8]}"
    await _cleanup(session_factory, position_id=pos)

    async with session_factory() as session:
        append = AppendLifecycleEvent(PostgresLifecycleEventStore(session))
        for kind, at, eid, extra in (
            (
                "POSITION_OPENED",
                "2026-09-03T10:00:00.000Z",
                f"{pos}-open",
                {},
            ),
            (
                "T1_EXECUTED",
                "2026-09-03T11:00:00.000Z",
                f"{pos}-t1",
                {"fill_id": f"{pos}-t1", "quantity": 5, "price": 105, "fees": 0},
            ),
        ):
            result = await append.execute(
                LifecycleEventInput(
                    kind=kind,  # type: ignore[arg-type]
                    position_id=pos,
                    account_id=acc,
                    at=at,
                    event_id=eid,
                    instrument_id="inst-w",
                    **extra,
                )
            )
            assert result.ok, getattr(result.error, "message", None)
        await session.commit()

    oid = await _enqueue(
        session_factory,
        position_id=pos,
        account_id=acc,
        transaction_id=tx_t2,
        kind="T2_EXECUTED",
        payload={
            "direct_input": {
                "kind": "T2_EXECUTED",
                "positionId": pos,
                "accountId": acc,
                "eventId": tx_t2,
                "at": "2026-09-03T12:00:00.000Z",
                "instrumentId": "inst-w",
                "fillId": tx_t2,
                "quantity": 3,
                "price": 110,
                "fees": 0,
                "reason": "TARGET_2",
            }
        },
    )

    boom = {"n": 0}
    inject_armed = {"on": True}

    async def _crash_after_trigger(index: int, _event: Any) -> None:
        if inject_armed["on"] and index == 0:
            boom["n"] += 1
            if boom["n"] == 1:
                raise RuntimeError("injected crash after T2_TRIGGERED")

    task = start_lifecycle_outbox_worker(
        session_factory,
        tick_seconds=0.05,
        on_after_append_index=_crash_after_trigger,
    )
    assert task is not None
    try:
        await _wait_status(session_factory, oid, "processing", timeout=5.0)
        # Confirm orphan trigger was NOT committed.
        async with session_factory() as session:
            snap_mid = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
        kinds_mid = [e["kind"] for e in snap_mid["events"]]
        assert "T2_TRIGGERED" not in kinds_mid
        assert "T2_EXECUTED" not in kinds_mid

        inject_armed["on"] = False
        async with session_factory() as session:
            row = await session.get(LifecycleOutboxRow, oid)
            assert row is not None
            row.claimed_at = datetime.now(UTC) - timedelta(
                seconds=OUTBOX_STALE_PROCESSING_SECONDS + 5
            )
            await session.commit()

        await _wait_status(session_factory, oid, "applied", timeout=8.0)
        async with session_factory() as session:
            snap = await GetLifecycleSnapshot(
                PostgresLifecycleEventStore(session)
            ).execute(pos)
        kinds = [e["kind"] for e in snap["events"]]
        assert kinds.count("T2_TRIGGERED") == 1
        assert kinds.count("T2_EXECUTED") == 1
        assert kinds == [
            "POSITION_OPENED",
            "T1_EXECUTED",
            "T2_TRIGGERED",
            "T2_EXECUTED",
        ]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _cleanup(session_factory, position_id=pos)
