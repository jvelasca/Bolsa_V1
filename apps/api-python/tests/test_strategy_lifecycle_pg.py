"""V2.25 / A10 — persistencia del Strategy Lifecycle en PG real (migración 030).

Certifica el store durable del ciclo de vida end-to-end sobre PostgreSQL:

* candidata (reproducible por ``data_snapshot_id``) → evaluación de LAB → finalista
  (``StrategyVersion`` inmutable) → promoción (gate cuantitativo + coach + shadow) →
  ACTIVE → snapshot de salud.
* El ACTIVE leído por ``get_active`` reconstruye la versión inmutable.
* La degradación de salud se detecta por umbral.

Honestidad (patrón del repo): sin PostgreSQL real hace skip salvo que
``STRATEGY_LIFECYCLE_PG_REQUIRED=1`` (job ``lifecycle-pg``), donde un skip es fallo.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_ENV_REQUIRED = "STRATEGY_LIFECYCLE_PG_REQUIRED"
_ENV_REQUIRED_V26 = "AUTO_ORCHESTRATOR_PG_REQUIRED"

pytestmark = pytest.mark.asyncio


def _require_or_skip(exc: Exception) -> None:
    # V2.25 y V2.26 comparten fixture: cualquiera de los dos gates exige PG real.
    if (
        os.environ.get(_ENV_REQUIRED) == "1"
        or os.environ.get(_ENV_REQUIRED_V26) == "1"
    ):
        raise AssertionError(f"Strategy Lifecycle PG requerido pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (A10 lifecycle) no disponible: {exc}")


def _optimize_result() -> object:
    """Doble del resultado de LAB con evidencia sobrada (mismo shape que ``_good_result``).

    Se define localmente para no acoplar el test PG a helpers privados de otro root.
    """
    from dataclasses import dataclass, field

    @dataclass
    class _Trial:
        score: float
        oos_metrics: dict[str, object] | None = None
        max_drawdown_pct: float | None = 5.0

    @dataclass
    class _Result:
        trials: list[_Trial] = field(default_factory=list)
        cpcv: dict[str, object] | None = None
        pbo: dict[str, object] | None = None
        walk_forward: dict[str, object] | None = None
        edge_report: dict[str, object] | None = None

    return _Result(
        trials=[_Trial(score=1.5, oos_metrics={"score": 0.9}, max_drawdown_pct=4.0)],
        cpcv={"pbo": 0.1},
        pbo={"pbo": 0.1},
        walk_forward={"walkForwardEfficiency": 0.7, "wfe": 0.7},
        edge_report={"dsr": 0.5},
    )



@pytest_asyncio.fixture
async def lifecycle_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto head 030.
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def test_strategy_lifecycle_roundtrip_pg(
    lifecycle_factory: async_sessionmaker[AsyncSession],
) -> None:
    from sqlalchemy import delete

    from bolsa_application.strategy_lifecycle_store import (
        ActiveStrategyRecord,
        PostgresStrategyLifecycleStore,
        new_promotion_record,
    )
    from bolsa_domain.entities.strategy_lifecycle import (
        PROMOTION_GATES,
        CoachAssessment,
        GateResult,
        StrategyCandidate,
        StrategyEvaluation,
        StrategyFinalist,
        StrategyHealth,
        StrategyValidation,
        evaluate_promotion,
    )
    from bolsa_infrastructure.database.models.tables import (
        StrategyCandidateRow,
        StrategyEvaluationRow,
        StrategyHealthRow,
        StrategyPromotionRow,
        StrategyVersionRow,
    )

    suffix = uuid.uuid4().hex[:10]
    candidate_id = f"cand-{suffix}"
    version_id = f"ver-{suffix}"
    instrument_id = f"inst-{suffix}"

    def _cleanup_stmt() -> list:
        return [
            delete(StrategyHealthRow).where(StrategyHealthRow.version_id == version_id),
            delete(StrategyPromotionRow).where(StrategyPromotionRow.candidate_id == candidate_id),
            delete(StrategyVersionRow).where(StrategyVersionRow.candidate_id == candidate_id),
            delete(StrategyEvaluationRow).where(
                StrategyEvaluationRow.candidate_id == candidate_id
            ),
            delete(StrategyCandidateRow).where(StrategyCandidateRow.id == candidate_id),
        ]

    try:
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            # 1) Candidata reproducible (ESTUDIO→LAB).
            await store.save_candidate(
                StrategyCandidate(
                    id=candidate_id,
                    instrument_id=instrument_id,
                    strategy_family="sma",
                    params={"fast": 20, "slow": 50},
                    data_snapshot_id="snap-2026-09-10",
                )
            )
            loaded = await store.get_candidate(candidate_id)
            assert loaded is not None
            assert loaded.data_snapshot_id == "snap-2026-09-10"
            assert loaded.params == {"fast": 20, "slow": 50}

            # 2) Evaluación de LAB con los gates en PASS.
            evaluation = StrategyEvaluation(
                candidate_id=candidate_id,
                score=1.42,
                gates=tuple(GateResult.passed_gate(g) for g in PROMOTION_GATES),
                metrics={"instrument_id": instrument_id},
            )
            await store.save_evaluation(evaluation)
            loaded_evals = await store.list_evaluations(candidate_id)
            assert len(loaded_evals) == 1
            assert loaded_evals[0].score == pytest.approx(1.42)
            assert loaded_evals[0].gates_passed

            # 3) Finalista → StrategyVersion inmutable.
            finalist = StrategyFinalist(
                candidate_id=candidate_id,
                version_id=version_id,
                name="SMA-20/50",
                definition_hash=f"hash-{suffix}",
                definition={"family": "sma", "instrument_id": instrument_id},
            )
            await store.save_finalist(finalist)
            from bolsa_domain.entities.strategy_lifecycle import StrategyLifecycleState

            reloaded_candidate = await store.get_candidate(candidate_id)
            assert reloaded_candidate is not None
            assert reloaded_candidate.state == StrategyLifecycleState.FINALISTA

            # 4) Promotion Gate + persistencia de la decisión.
            validation = StrategyValidation(finalist_id=version_id, gates=evaluation.gates)
            promo = evaluate_promotion(
                finalist=finalist,
                validation=validation,
                coach=CoachAssessment(candidate_id=candidate_id, approved=True),
                shadow_validated=True,
            )
            assert promo.promoted
            await store.save_promotion(
                new_promotion_record(
                    promotion=promo,
                    candidate_id=candidate_id,
                    instrument_id=instrument_id,
                )
            )
            promotions = await store.list_promotions(promoted=True)
            assert any(p.version_id == version_id for p in promotions)

            # 5) ACTIVE persistida y releída con su versión inmutable.
            from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

            await store.save_active(
                ActiveStrategyRecord(
                    active=ActiveStrategy(
                        version_id=version_id,
                        candidate_id=candidate_id,
                        instrument_id=instrument_id,
                        name="SMA-20/50",
                        definition=finalist.definition,
                    ),
                    promoted_at=datetime.now(UTC).isoformat(),
                )
            )
            active = await store.get_active(instrument_id=instrument_id)
            assert active is not None
            assert active.active.version_id == version_id
            assert active.active.definition["family"] == "sma"

            # 6) Vigilancia: snapshot de salud y detección de degradación.
            await store.save_health(
                version_id,
                StrategyHealth(
                    version_id=version_id,
                    as_of=datetime.now(UTC).isoformat(),
                    edge=0.05,
                    thresholds={"edge": 0.2},
                ),
            )
            health = await store.list_health(version_id)
            assert len(health) == 1
            assert health[0].degraded, "edge 0.05 < 0.2 debe marcar degradación"
    finally:
        async with lifecycle_factory() as session:
            for stmt in _cleanup_stmt():
                await session.execute(stmt)
            await session.commit()


async def test_auto_orchestrator_full_cycle_pg(
    lifecycle_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V2.26/A10: ciclo completo del orquestador sobre el store PG real.

    ESTUDIO (candidata directa) → LABORATORIO (runner inyectado con evidencia) →
    TOP3 → COACH → FINALISTA → PROMOCION (shadow) → ACTIVE; después vigilancia con
    métricas degradadas ⇒ re-LAB (sin swap directo).
    """
    from sqlalchemy import delete

    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_infrastructure.database.models.tables import (
        StrategyCandidateRow,
        StrategyEvaluationRow,
        StrategyHealthRow,
        StrategyPromotionRow,
        StrategyVersionRow,
    )

    suffix = uuid.uuid4().hex[:10]
    instrument_id = f"inst-{suffix}"
    candidate_id = f"cand-{suffix}"

    async def _cleanup() -> None:
        async with lifecycle_factory() as session:
            for stmt in (
                delete(StrategyHealthRow),
                delete(StrategyPromotionRow).where(
                    StrategyPromotionRow.instrument_id == instrument_id
                ),
                delete(StrategyVersionRow).where(
                    StrategyVersionRow.candidate_id == candidate_id
                ),
                delete(StrategyEvaluationRow).where(
                    StrategyEvaluationRow.candidate_id == candidate_id
                ),
                delete(StrategyCandidateRow).where(StrategyCandidateRow.id == candidate_id),
            ):
                await session.execute(stmt)
            await session.commit()

    await _cleanup()
    try:
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)

            async def _run_optimize(_candidate: object) -> object:
                return _optimize_result()

            deps = OrchestratorDeps(
                store=store,
                run_optimize=_run_optimize,
                candidate_id_factory=lambda _inst, _i: candidate_id,
                strategy_family="sma_crossover",
            )
            orchestrator = AutoOrchestrator(deps)

            # Primera pasada sin shadow ⇒ NO promociona (fail-closed).
            dry = await orchestrator.run_cycle(
                instrument_id=instrument_id, shadow_validated=False
            )
            assert not dry.promoted
            assert await store.get_active(instrument_id=instrument_id) is None

            promoted = await orchestrator.run_cycle(
                instrument_id=instrument_id,
                data_snapshot_id="snap-pg",
                shadow_validated=True,
                run_id="pg-cycle",
            )
            assert promoted.status == "active", promoted.reasons
            assert promoted.active_version_id is not None

            active = await store.get_active(instrument_id=instrument_id)
            assert active is not None
            assert active.active.version_id == promoted.active_version_id

            watched = await orchestrator.watch_active(
                instrument_id=instrument_id,
                metrics={"edge": -1.0, "wfe": 0.0},
                as_of="2026-09-11",
            )
            assert watched.degraded
            assert watched.relab_triggered
            # La degradación no sustituye la activa.
            still = await store.get_active(instrument_id=instrument_id)
            assert still is not None
            assert still.active.version_id == active.active.version_id
    finally:
        await _cleanup()
