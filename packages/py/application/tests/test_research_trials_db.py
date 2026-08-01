"""Persistencia research_trials + K sumable (ADR-016 Fase 1)."""

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


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


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
async def test_research_trial_k_summable_by_instrument(db_session) -> None:
    from bolsa_infrastructure.database.models import InstrumentRow, ResearchTrialRow
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )

    # Skip if migration not applied yet
    try:
        await db_session.execute(select(ResearchTrialRow.id).limit(1))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"research_trials no migrada: {exc}")

    now = datetime.now(timezone.utc)
    instrument_id = _new_id("inst")
    yahoo = f"TESTK.{uuid.uuid4().hex[:8]}"

    db_session.add(
        InstrumentRow(
            id=instrument_id,
            symbol="TKSUM",
            yahoo_symbol=yahoo,
            name="K Sum Test",
            exchange="NASDAQ",
            country="US",
            currency="USD",
            sector=None,
            type="stock",
            is_active=True,
            profile_snapshot=None,
            last_xtb_validation=None,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()

    repo = SqlAlchemyResearchTrialRepository(db_session)
    await repo.insert_trial(
        instrument_id=instrument_id,
        params={"n": 1},
        is_metrics={"totalReturnPct": 1.0},
        proposed_by="human",
        k_contribution=1,
    )
    await repo.insert_trial(
        instrument_id=instrument_id,
        params={"n": 2},
        is_metrics={"totalReturnPct": 2.0},
        proposed_by="grid",
        k_contribution=1,
    )
    await repo.insert_trial(
        instrument_id=instrument_id,
        params={"n": 3},
        is_metrics={"totalReturnPct": 3.0},
        proposed_by="grid",
        k_contribution=2,
    )

    total_k = await repo.sum_k_by_instrument(instrument_id)
    assert total_k == 4

    listed = await repo.list_by_instrument(instrument_id, limit=10)
    assert len(listed) == 3
    assert all(t.instrument_id == instrument_id for t in listed)
