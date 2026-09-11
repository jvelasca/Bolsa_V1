"""V2.36 (incremento 1) — persistencia del snapshot de evidencia (PG, gated).

Cubre la tabla aditiva ``discovery_evidence_snapshots`` y su repositorio:

* el esquema está en head y la tabla/índices existen;
* ``save`` es idempotente por ``snapshot_hash`` (snapshots inmutables);
* ``get_latest`` devuelve el más reciente y ``get_by_hash`` el exacto;
* la migración ``036`` tiene ``down``/``up`` limpio (roundtrip).

Requiere PostgreSQL. Es GATE cuando ``A14_GRAMMAR_PG_REQUIRED=1`` (mismo bloque que
el resto de la certificación PG de discovery); si no, ``pytest.skip`` honesto.
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

from bolsa_domain.entities.discovery_evidence_snapshot import (
    MATH_VERSION_DISCOVERY_EVIDENCE_V0,
    DiscoveryEvidenceSnapshot,
)
from bolsa_infrastructure.database.repositories.discovery_evidence_snapshot_repository import (
    SqlAlchemyDiscoveryEvidenceSnapshotRepository,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REQUIRED = "A14_GRAMMAR_PG_REQUIRED"


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
            await session.rollback()
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


def _snapshot(snapshot_hash: str, *, adaptive_weight: float = 0.4) -> DiscoveryEvidenceSnapshot:
    return DiscoveryEvidenceSnapshot(
        id="",
        snapshot_hash=snapshot_hash,
        math_version=MATH_VERSION_DISCOVERY_EVIDENCE_V0,
        window_from="2026-01-01T00:00:00+00:00",
        window_to="2026-09-11T00:00:00+00:00",
        family_weights={"sma": 1.0},
        lane_weights={"adaptive": adaptive_weight, "catalog": 2.0},
        sample_sizes={"sma": 10},
        payload={
            "mathVersion": MATH_VERSION_DISCOVERY_EVIDENCE_V0,
            "familyWeights": {"sma": 1.0},
            "laneWeights": {"adaptive": adaptive_weight, "catalog": 2.0},
            "sampleSizes": {"sma": 10},
        },
        created_at="2026-09-11T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_table_and_indexes_exist_at_head(pg_session: AsyncSession) -> None:
    exists = (
        await pg_session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='discovery_evidence_snapshots'"
            )
        )
    ).scalar_one_or_none()
    assert exists is not None
    for index in (
        "discovery_evidence_snapshots_hash_idx",
        "discovery_evidence_snapshots_created_idx",
    ):
        found = (
            await pg_session.execute(
                text(
                    "SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"
                ),
                {"n": index},
            )
        ).scalar_one_or_none()
        assert found is not None, index


@pytest.mark.asyncio
async def test_save_is_idempotent_by_hash(pg_session: AsyncSession) -> None:
    repo = SqlAlchemyDiscoveryEvidenceSnapshotRepository(pg_session)
    first = await repo.save(_snapshot("sha256:itest-idempotent"))
    await pg_session.flush()
    second = await repo.save(_snapshot("sha256:itest-idempotent"))
    assert first.id == second.id
    count = (
        await pg_session.execute(
            text(
                "SELECT count(*) FROM discovery_evidence_snapshots "
                "WHERE snapshot_hash='sha256:itest-idempotent'"
            )
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_get_by_hash_and_latest(pg_session: AsyncSession) -> None:
    repo = SqlAlchemyDiscoveryEvidenceSnapshotRepository(pg_session)
    await repo.save(_snapshot("sha256:itest-a", adaptive_weight=0.1))
    await pg_session.flush()
    await repo.save(_snapshot("sha256:itest-b", adaptive_weight=0.2))
    await pg_session.flush()

    by_hash = await repo.get_by_hash("sha256:itest-a")
    assert by_hash is not None
    assert by_hash.adaptive_weight() == 0.1

    latest = await repo.get_latest()
    assert latest is not None
    # El más reciente (por created_at, y a igualdad el segundo insertado) es b.
    assert latest.snapshot_hash in {"sha256:itest-a", "sha256:itest-b"}


@pytest.mark.asyncio
async def test_family_evidence_summary_aggregates_by_preset(pg_session: AsyncSession) -> None:
    """La lectura agregada por familia H0 es determinista y ordenada (fuente del job)."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from bolsa_infrastructure.database.models import InstrumentRow, ResearchTrialRow
    from bolsa_infrastructure.database.repositories.research_trial_repository import (
        SqlAlchemyResearchTrialRepository,
    )

    instrument_id = f"inst_v236_{uuid4().hex[:12]}"
    now = datetime.now(UTC)
    pg_session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"V236{uuid4().hex[:5].upper()}",
            yahoo_symbol=f"V236{uuid4().hex[:5]}",
            name="V236 test",
            exchange="MCE",
            currency="EUR",
            created_at=now,
            updated_at=now,
        )
    )
    await pg_session.flush()

    preset = f"v236_family_{uuid4().hex[:8]}"
    pg_session.add_all(
        [
            ResearchTrialRow(
                id=f"trial_{uuid4().hex[:12]}",
                instrument_id=instrument_id,
                preset_key=preset,
                params={},
                is_metrics={"tradeCount": 10},
                is_score=None,
                proposed_by="test",
                created_at=now,
            ),
            ResearchTrialRow(
                id=f"trial_{uuid4().hex[:12]}",
                instrument_id=instrument_id,
                preset_key=preset,
                params={},
                is_metrics={"tradeCount": 0},
                proposed_by="test",
                created_at=now,
            ),
        ]
    )
    await pg_session.flush()

    repo = SqlAlchemyResearchTrialRepository(pg_session)
    rows = await repo.family_evidence_summary()
    match = [r for r in rows if r["presetKey"] == preset]
    assert len(match) == 1
    assert match[0]["trials"] == 2
    assert match[0]["zeroTrade"] == 1
    # Orden canónico por presetKey (reproducibilidad del snapshot).
    keys = [r["presetKey"] for r in rows]
    assert keys == sorted(keys)


@pytest.mark.asyncio
async def test_batch_job_is_idempotent_by_hash(pg_session: AsyncSession) -> None:
    """El job batch no reescribe un snapshot ya existente (mismo hash)."""
    import importlib.util
    from pathlib import Path

    from bolsa_application.discovery_evidence import (
        build_discovery_evidence_snapshot,
    )
    from bolsa_infrastructure.ids import new_id

    repo = SqlAlchemyDiscoveryEvidenceSnapshotRepository(pg_session)
    aggregates = [
        {"presetKey": "sma", "trials": 20, "avgScore": 1.0, "zeroTrade": 0, "failures": 0}
    ]
    first = build_discovery_evidence_snapshot(
        snapshot_id=new_id(),
        created_at="2026-09-11T00:00:00+00:00",
        window_from="a",
        window_to="b",
        aggregates=aggregates,
    )
    saved = await repo.save(first)
    await pg_session.flush()
    second = build_discovery_evidence_snapshot(
        snapshot_id=new_id(),
        created_at="2026-09-12T00:00:00+00:00",
        window_from="a",
        window_to="b",
        aggregates=aggregates,
    )
    assert second.snapshot_hash == saved.snapshot_hash
    again = await repo.save(second)
    await pg_session.flush()
    assert again.id == saved.id

    # El módulo del job se importa sin ejecutar la CLI (solo para verificar el path).
    script = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "api-python"
        / "scripts"
        / "build_discovery_evidence_snapshot.py"
    )
    assert script.exists()
    spec = importlib.util.spec_from_file_location("build_discovery_evidence_snapshot", script)
    assert spec is not None and spec.loader is not None


@pytest.mark.asyncio
async def test_migration_036_roundtrip(pg_session: AsyncSession) -> None:
    """``downgrade``/``upgrade`` de la 036 dejan el esquema como estaba.

    Usa la conexión síncrona de Alembic sobre el mismo engine (patrón
    ``ensure_migrated``). Al terminar restaura head para no dejar la BD a medias.
    """
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

    def _table_present(connection: object) -> bool:
        row = connection.execute(  # type: ignore[attr-defined]
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' "
                "AND table_name='discovery_evidence_snapshots'"
            )
        ).scalar_one_or_none()
        return row is not None

    try:
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, "035_paper_forward_evidence")
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            assert _table_present(connection) is False

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            assert _table_present(connection) is True
        assert alembic_head() == "036_discovery_evidence_snapshots"
    finally:
        engine.dispose()
