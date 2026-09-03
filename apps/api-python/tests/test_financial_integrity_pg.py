"""V1.94 — Financial integrity detect/report against PostgreSQL.

Orphan lifecycle · dead_head vs dead_non_head · open_tx mismatch.
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
    return async_sessionmaker(pg_engine, expire_on_commit=False)


def _outbox_adapter(session: AsyncSession) -> Any:
    from bolsa_application.reconcile_lifecycle_integrity import OutboxSnap
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    class _Adapter:
        async def list_for_account(self, acc: str) -> list[OutboxSnap]:
            rows = (
                await session.execute(
                    select(LifecycleOutboxRow).where(
                        LifecycleOutboxRow.account_id == acc,
                        LifecycleOutboxRow.status.in_(
                            ("pending", "processing", "dead")
                        ),
                    )
                )
            ).scalars().all()
            return [
                OutboxSnap(
                    position_id=r.position_id,
                    kind=r.kind,
                    status=r.status,
                    created_at=r.created_at,
                    id=r.id,
                )
                for r in rows
            ]

    return _Adapter()


@pytest.mark.asyncio
async def test_orphan_lifecycle_is_drift(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        GetLifecycleSnapshot,
        PostgresLifecycleEventStore,
        input_from_body,
    )
    from bolsa_application.reconcile_lifecycle_integrity import (
        ReconcileLifecycleIntegrity,
        ReconcileLifecycleIntegrityInput,
    )
    from bolsa_infrastructure.database.repositories.position_state_repository import (
        SqlAlchemyPositionStateRepository,
    )

    account_id = f"fi-acc-{uuid4().hex[:10]}"
    position_id = f"fi-orphan-{uuid4().hex[:10]}"
    async with session_factory() as session:
        store = PostgresLifecycleEventStore(session)
        append = AppendLifecycleEvent(store)
        body = {
            "kind": "POSITION_OPENED",
            "at": "2026-09-01T10:00:00.000Z",
            "eventId": f"ev-{uuid4().hex[:12]}",
            "positionId": position_id,
            "accountId": account_id,
            "instrumentId": "inst-fi-1",
            "decisionId": "dec-1",
            "tradePlanId": "tp-1",
            "symbol": "TEST",
            "fillId": f"tx-{uuid4().hex[:12]}",
            "quantity": 10,
            "price": 100,
            "venue": "PAPER",
        }
        result = await append.execute(input_from_body(body))
        assert result.ok
        await session.commit()

    async with session_factory() as session:
        report = await ReconcileLifecycleIntegrity(
            positions=SqlAlchemyPositionStateRepository(session),
            snapshots=GetLifecycleSnapshot(PostgresLifecycleEventStore(session)),
            outbox=_outbox_adapter(session),
        ).reconcile(ReconcileLifecycleIntegrityInput(account_id=account_id))
        assert report is not None
        assert report.status == "drift"
        assert any(i.code == "orphan_lifecycle" for i in report.issues)


@pytest.mark.asyncio
async def test_dead_head_vs_dead_non_head(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_application.lifecycle_outbox import PostgresLifecycleOutboxStore
    from bolsa_application.reconcile_lifecycle_integrity import (
        PositionStateSnap,
        build_lifecycle_reconciliation,
        OutboxSnap,
    )
    from bolsa_infrastructure.database.models.tables import LifecycleOutboxRow

    account_id = f"fi-dead-{uuid4().hex[:10]}"
    position_id = f"fi-pos-{uuid4().hex[:10]}"
    t0 = datetime.now(UTC) - timedelta(minutes=3)
    t1 = datetime.now(UTC) - timedelta(minutes=2)

    async with session_factory() as session:
        store = PostgresLifecycleOutboxStore(session)
        # Head dead → blocked
        await store.enqueue(
            position_id=position_id,
            account_id=account_id,
            transaction_id=f"tx-dead-head-{uuid4().hex[:8]}",
            kind="POSITION_CLOSED",
            payload={},
        )
        await session.commit()

    async with session_factory() as session:
        row = (
            await session.execute(
                select(LifecycleOutboxRow).where(
                    LifecycleOutboxRow.account_id == account_id,
                    LifecycleOutboxRow.position_id == position_id,
                )
            )
        ).scalar_one()
        row.status = "dead"
        row.created_at = t0
        await session.commit()

        snaps = [
            OutboxSnap(
                position_id=position_id,
                kind=row.kind,
                status="dead",
                created_at=t0,
                id=row.id,
            )
        ]
        report = build_lifecycle_reconciliation(
            account_id=account_id,
            positions=[
                PositionStateSnap(
                    position_id=position_id, status="OPEN", remaining=10.0
                )
            ],
            snapshots_by_position={
                position_id: {
                    "events": [
                        {"kind": "POSITION_OPENED"},
                        {"kind": "T1_EXECUTED"},
                    ],
                    "accounting": {"remaining": 10.0},
                }
            },
            outbox=snaps,
        )
        assert report.status == "blocked"
        assert any(i.code == "dead_head" for i in report.issues)

    # Non-head dead: pending head + later dead
    pos2 = f"fi-pos2-{uuid4().hex[:10]}"
    report2 = build_lifecycle_reconciliation(
        account_id=account_id,
        positions=[
            PositionStateSnap(position_id=pos2, status="OPEN", remaining=5.0)
        ],
        snapshots_by_position={
            pos2: {
                "events": [{"kind": "POSITION_OPENED"}, {"kind": "T1_EXECUTED"}],
                "accounting": {"remaining": 5.0},
            }
        },
        outbox=[
            OutboxSnap(
                position_id=pos2,
                kind="T1_EXECUTED",
                status="pending",
                created_at=t0,
                id="ox-head",
            ),
            OutboxSnap(
                position_id=pos2,
                kind="POSITION_CLOSED",
                status="dead",
                created_at=t1,
                id="ox-dead",
            ),
        ],
    )
    assert report2.status != "blocked"
    assert any(i.code == "dead_non_head" for i in report2.issues)


@pytest.mark.asyncio
async def test_open_tx_mismatch_is_fill_drift() -> None:
    from bolsa_application.reconcile_financial_integrity import (
        build_fill_link_issues,
        compose_financial_integrity,
    )
    from bolsa_application.reconcile_lifecycle_integrity import (
        LifecycleReconciliation,
        PositionStateSnap,
    )

    fill_issues = build_fill_link_issues(
        positions=[
            PositionStateSnap(
                position_id="pos-m",
                status="OPEN",
                remaining=10.0,
                open_transaction_id="tx-a",
            )
        ],
        snapshots_by_position={
            "pos-m": {
                "events": [{"kind": "POSITION_OPENED", "fillId": "tx-b"}],
            }
        },
        ledger_reference_ids={"tx-a", "tx-b"},
    )
    assert any(i.code == "open_tx_mismatch" for i in fill_issues)
    report = compose_financial_integrity(
        account_id="acc",
        lifecycle=LifecycleReconciliation(
            account_id="acc",
            status="clean",
            checked=1,
            drift_count=0,
            lag_count=0,
            blocked_count=0,
        ),
        fill_link_issues=fill_issues,
    )
    assert report.status == "drift"
    assert report.operational_state == "BLOCKED"


@pytest.mark.asyncio
async def test_lifecycle_opening_veto_on_drift() -> None:
    from bolsa_application.reconciliation_opening_gate import (
        reconciliation_opening_veto_reason,
    )
    from bolsa_application.risk_engine import check_opening

    assert (
        reconciliation_opening_veto_reason(lifecycle_recon_status="drift")
        == "reconciliation:lifecycle_drift"
    )
    decision = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="TEST",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="recommend_long",
        lifecycle_recon_status="drift",
        require_recon_veto=True,
    )
    assert decision.verdict == "DENY"
    assert "reconciliation:lifecycle_drift" in decision.reasons

    # Exits bypass OR-4 lifecycle veto
    exit_decision = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="TEST",
        trade_type="sell",
        quantity=1,
        price=10,
        signal_kind="exit_hint",
        lifecycle_recon_status="drift",
        require_recon_veto=True,
    )
    assert "reconciliation:lifecycle_drift" not in exit_decision.reasons
