"""Tests F3b — Alembic como autoridad de esquema + columna ``data_epoch``.

Cubre:
- ``ensure_migrated`` aplica migraciones Alembic hasta ``head`` de forma idempotente.
- La columna ``data_epoch`` existe en ``backtest_runs`` y ``research_trials``.
- La lógica de etiquetado old/next_open (``_mark_legacy``) del recalc script.
Requiere PostgreSQL (mismas convenciones que los tests de infraestructura).
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.migrations import _alembic_config, ensure_migrated

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REPO_ROOT = Path(__file__).resolve().parents[4]

_RECALC_MODULE_PATH = _REPO_ROOT / "scripts" / "research" / "recalc_trials_next_open.py"


def _load_recalc_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("recalc_trials_next_open", _RECALC_MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_env() -> None:
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


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


def test_alembic_instala_baseline_y_head_migracion() -> None:
    """La cadena Alembic es ejecutable y llega a head (autoridad D2)."""
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, heads
    assert heads[0] == "002_research_data_epoch"


@pytest.mark.asyncio
async def test_ensure_migrated_idempotente_y_columna_data_epoch() -> None:
    """ensure_migrated no falla, es idempotente y deja data_epoch en ambas tablas."""
    assert ensure_migrated() is True
    assert ensure_migrated() is True  # segunda llamada: ok (idempotente)

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine

    engine = create_engine(get_settings())
    try:
        async with engine.connect() as conn:
            for table in ("backtest_runs", "research_trials"):
                exists = (
                    await conn.execute(
                        text(
                            "SELECT 1 FROM information_schema.columns "
                            "WHERE table_name=:t AND column_name='data_epoch'"
                        ),
                        {"t": table},
                    )
                ).scalar_one_or_none()
                assert exists is not None, f"{table} no tiene columna data_epoch"
            version = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalars().one()
            assert version == "002_research_data_epoch"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mark_legacy_etiqueta_old_vs_next_open(db_session: AsyncSession) -> None:
    """_mark_legacy marca next_open los runs con engine.version actual y legacy los demás."""
    module = _load_recalc_module()

    from bolsa_infrastructure.database.models import (
        BacktestRunRow,
        InstrumentRow,
        ResearchTrialRow,
    )

    instrument_id = f"inst_f3b_{uuid4().hex[:12]}"
    now = datetime.now(UTC)
    db_session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"F3B{uuid4().hex[:6].upper()}",
            yahoo_symbol=f"F3B{uuid4().hex[:6]}",
            name="F3B test",
            exchange="MCE",
            currency="EUR",
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()

    run_old = BacktestRunRow(
        id=f"run_old_{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        initial_cash=Decimal("10000"),
        final_equity=Decimal("10500"),
        total_return_pct=Decimal("5"),
        max_drawdown_pct=Decimal("1"),
        trade_count=1,
        win_count=1,
        bar_count=100,
        first_date=now.date(),
        last_date=now.date(),
        created_at=now,
        strategy_type="sma_crossover",
        manifest={"engine": {"version": "0.3.0"}},
        data_epoch=None,
    )
    run_new = BacktestRunRow(
        id=f"run_new_{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        initial_cash=Decimal("10000"),
        final_equity=Decimal("10500"),
        total_return_pct=Decimal("5"),
        max_drawdown_pct=Decimal("1"),
        trade_count=1,
        win_count=1,
        bar_count=100,
        first_date=now.date(),
        last_date=now.date(),
        created_at=now,
        strategy_type="sma_crossover",
        manifest={"engine": {"version": "0.4.0"}},
        data_epoch=None,
    )
    db_session.add_all([run_old, run_new])
    await db_session.flush()

    db_session.add(
        ResearchTrialRow(
            id=f"trial_{uuid4().hex[:12]}",
            instrument_id=instrument_id,
            backtest_run_id=run_old.id,
            params={},
            is_metrics={},
            proposed_by="test",
            created_at=now,
        )
    )
    await db_session.flush()

    changed = await module._mark_legacy(db_session, engine_version="0.4.0")
    await db_session.flush()

    assert changed >= 1
    await db_session.refresh(run_old)
    await db_session.refresh(run_new)
    assert run_old.data_epoch == module.DATA_EPOCH_LEGACY
    assert run_new.data_epoch == module.DATA_EPOCH_NEXT_OPEN

    trial = (
        await db_session.scalars(
            select(ResearchTrialRow).where(ResearchTrialRow.backtest_run_id == run_old.id)
        )
    ).one()
    assert trial.data_epoch == module.DATA_EPOCH_LEGACY
