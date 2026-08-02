"""Smoke test CORE-R account blob API (Q3.4) — requires PostgreSQL + migration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_env() -> None:
    env_path = _repo_root() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def db_session():
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


@pytest.mark.asyncio
async def test_core_r_upsert_roundtrip(db_session) -> None:
    from bolsa_infrastructure.database.models import CoreRAccountStateRow, InvestmentAccountRow
    from bolsa_infrastructure.database.repositories.core_r_repository import (
        SqlAlchemyCoreRRepository,
    )

    try:
        await db_session.execute(select(CoreRAccountStateRow.account_id).limit(1))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"core_r_account_state no migrada: {exc}")

    now = datetime.now(timezone.utc)
    account_id = f"acc_corer_{uuid.uuid4().hex[:16]}"
    db_session.add(
        InvestmentAccountRow(
            id=account_id,
            name="CORE-R test",
            type="simulated",
            status="active",
            currency="EUR",
            base_currency="EUR",
            is_default=False,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()

    repo = SqlAlchemyCoreRRepository(db_session)
    saved = await repo.upsert(
        account_id,
        queue=[{"id": "q1", "listId": "ibex35", "status": "open"}],
        reports={"ibex35": {"engine": "core-r-v0", "listId": "ibex35", "rows": []}},
        scheduler={"enabled": True, "intervalMinutes": 60, "scope": "shell"},
    )
    assert saved.account_id == account_id
    assert len(saved.queue) == 1
    assert "ibex35" in saved.reports

    again = await repo.get(account_id)
    assert again is not None
    assert again.scheduler.get("enabled") is True
