"""Tests for Research Observatory query API (Fase 1.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
async def test_research_list_filter_and_summary(db_session) -> None:
    from bolsa_infrastructure.database.models import InstrumentRow, ResearchTrialRow
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )

    from bolsa_application.research_trials import (
        GetInstrumentResearchSummary,
        GetLaboratoryResearchSummary,
        GetResearchTrial,
        ListResearchTrials,
    )

    try:
        await db_session.execute(select(ResearchTrialRow.id).limit(1))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"research_trials no migrada: {exc}")

    now = datetime.now(UTC)
    instrument_id = _new_id("inst")
    yahoo = f"TESTRES.{uuid.uuid4().hex[:8]}"

    db_session.add(
        InstrumentRow(
            id=instrument_id,
            symbol="TRES",
            yahoo_symbol=yahoo,
            name="Research Test",
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
    t1 = await repo.insert_trial(
        instrument_id=instrument_id,
        params={"n": 1},
        is_metrics={
            "totalReturnPct": 10.0,
            "sharpeRatio": 1.5,
            "sortinoRatio": 2.0,
            "maxDrawdownPct": 5.0,
            "totalCommission": 3.0,
            "profitFactor": 1.8,
        },
        proposed_by="human",
        preset_key="sma_crossover",
        k_contribution=1,
    )
    await repo.insert_trial(
        instrument_id=instrument_id,
        params={"n": 2},
        is_metrics={
            "totalReturnPct": 5.0,
            "sharpeRatio": 0.8,
            "sortinoRatio": 1.0,
            "maxDrawdownPct": 8.0,
            "totalCommission": 1.0,
            "profitFactor": 1.2,
        },
        proposed_by="grid",
        preset_key="sma_crossover",
        k_contribution=1,
    )

    listed, total = await ListResearchTrials(repo).execute(
        instrument_id=instrument_id,
        proposed_by="human",
        limit=10,
        offset=0,
    )
    assert total == 1
    assert listed[0].id == t1.id

    detail = await GetResearchTrial(repo).execute(t1.id)
    assert detail is not None
    assert detail.is_metrics["sharpeRatio"] == 1.5

    # Empty / null sharpe must sort AFTER real values (NULLS LAST friction-fix).
    await repo.insert_trial(
        instrument_id=instrument_id,
        params={"n": 0},
        is_metrics={
            "totalReturnPct": 0.0,
            "sharpeRatio": None,
            "sortinoRatio": None,
            "maxDrawdownPct": 0.0,
            "totalCommission": 0.0,
            "profitFactor": None,
        },
        proposed_by="human",
        preset_key="rsi_mean_reversion",
        k_contribution=1,
    )
    top, _ = await ListResearchTrials(repo).execute(
        instrument_id=instrument_id,
        sort="sharpe",
        sort_dir="desc",
        limit=10,
    )
    assert top[0].is_metrics.get("sharpeRatio") is not None
    assert top[-1].is_metrics.get("sharpeRatio") is None or any(
        t.is_metrics.get("sharpeRatio") is None for t in top
    )
    assert top[0].is_metrics.get("sharpeRatio") == 1.5

    summary = await GetInstrumentResearchSummary(repo).execute(instrument_id)
    assert summary is not None
    assert summary["trials"] == 3
    assert summary["kConsumed"] == 3
    assert summary["proposedBy"]["human"] == 2
    assert summary["proposedBy"]["grid"] == 1
    assert summary["avgSharpe"] is not None

    lab = await GetLaboratoryResearchSummary(repo).execute()
    assert lab["totalTrials"] >= 3
    assert lab["totalK"] >= 3

    from bolsa_application.research_trials import GetLabHealth

    health = await GetLabHealth(repo).execute()
    assert health["totalTrials"] >= 3
    assert "sharpeRatio" in health["coverage"]
    assert "zeroTradePct" in health
    assert "caveat" in health
