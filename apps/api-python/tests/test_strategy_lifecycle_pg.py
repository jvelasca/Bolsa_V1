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
from typing import Any

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
        # V2.35.1 (P2-01): parámetros del campeón. Sin ellos no hay definición
        # ejecutable y el shadow no puede producir evidencia (la promoción dejó de
        # aceptar el override humano). El stub debe aportar un campeón real.
        params: dict[str, object] | None = None

    @dataclass
    class _Result:
        trials: list[_Trial] = field(default_factory=list)
        cpcv: dict[str, object] | None = None
        pbo: dict[str, object] | None = None
        walk_forward: dict[str, object] | None = None
        edge_report: dict[str, object] | None = None

    return _Result(
        trials=[
            _Trial(
                score=1.5,
                oos_metrics={"score": 0.9},
                max_drawdown_pct=4.0,
                # V2.35.1 (P2-01): campeón con parámetros reales para que
                # ``_champion_definition`` construya un ``executable`` replicable por
                # el shadow (sin override humano la evidencia es la única vía).
                params={"fast": 10, "slow": 30},
            )
        ],
        cpcv={"pbo": 0.1},
        pbo={"pbo": 0.1},
        walk_forward={"walkForwardEfficiency": 0.7, "wfe": 0.7},
        edge_report={"dsr": 0.5},
    )


def _make_shadow_bars_provider(instrument_id: str) -> Any:
    """V2.35.1 (P2-01): barras deterministas para ejecutar evidencia shadow real.

    La ruta AUTO ya no acepta override humano, así que los tests que esperan promoción
    deben aportar barras con hold-out separable. El ``instrument_id`` se acepta por
    firma (el provider real filtra por instrumento), pero la serie es sintética.
    """
    import math
    from datetime import date, timedelta

    from bolsa_analytics.backtest import BacktestBarInput

    base = date(2026, 1, 1)
    bars = []
    for index in range(400):
        price = 100.0 + 12.0 * math.sin(index / 6.0) + index * 0.05
        bars.append(
            BacktestBarInput(
                timestamp=(base + timedelta(days=index)).isoformat(),
                close=price,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                volume=1000.0,
            )
        )

    def _provider(_instrument_id: str) -> tuple[Any, ...]:
        return tuple(bars)

    return _provider



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
        evaluate_admin_promotion,
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
            promo = evaluate_admin_promotion(
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

            from bolsa_application.strategy_vigilance_phase import HealthThresholds

            deps = OrchestratorDeps(
                store=store,
                run_optimize=_run_optimize,
                candidate_id_factory=lambda _inst, _i: candidate_id,
                strategy_family="sma_crossover",
                # V2.32.1 (auditoría 2b): los umbrales predictivos ya no se inventan con
                # 0.0; el test configura explícitamente los que quiere ejercitar.
                health_thresholds=HealthThresholds(min_edge=0.0, min_wfe=0.5),
            )
            orchestrator = AutoOrchestrator(deps)

            # Primera pasada sin shadow ⇒ NO promociona (fail-closed).
            dry = await orchestrator.run_cycle(instrument_id=instrument_id)
            assert not dry.promoted
            assert await store.get_active(instrument_id=instrument_id) is None

            # V2.35.1 (P2-01): la promoción exige EVIDENCIA shadow real (sin override).
            from bolsa_application.strategy_shadow_phase import ShadowReplayConfig
            from bolsa_domain.entities.strategy_lifecycle import ShadowPolicy

            deps.shadow_bars = _make_shadow_bars_provider(instrument_id)
            deps.shadow_policy = ShadowPolicy(min_closed_round_trips=1, min_return_pct=-100.0)
            deps.shadow_config = ShadowReplayConfig(window_bars=99, min_bars=10)

            promoted = await orchestrator.run_cycle(
                instrument_id=instrument_id,
                data_snapshot_id="snap-pg",
                run_id="pg-cycle",
            )
            # V2.35.1 (P2-01): sin override humano, la promoción exige evidencia shadow
            # EJECUTADA. El stub del LAB aporta un campeón con parámetros reales para que
            # el shadow pueda replicar la definición; el promotion gate decide por
            # evidencia, no por un booleano.
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


async def test_default_orchestrator_real_wiring_end_to_end_pg(
    lifecycle_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V2.27/A10 — P1-01/P1-02: composición REAL, sin inyectar dependencias.

    A diferencia de ``test_auto_orchestrator_full_cycle_pg`` (que inyecta
    ``run_optimize`` y el candidato), este test usa ``_default_orchestrator`` tal cual
    lo usa el scheduler: el universo ESTUDIO y el LAB real (``RunSmaGridOptimizeAndSave``)
    se cablean solos. Se siembra instrumento + pertenencia a la lista ``estudio`` +
    barras OHLCV, y se certifica que el ciclo deja ``sin_evidencia_top3`` y produce
    evidencia real (evaluación persistida con ``optimization_run_id``).
    """
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from sqlalchemy import delete

    from bolsa_api.background.auto_orchestrator_worker import _default_orchestrator
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_infrastructure.database.models.tables import (
        InstrumentRow,
        OhlcvBarRow,
        StrategyCandidateRow,
        StrategyEvaluationRow,
    )
    from bolsa_infrastructure.database.repositories.list_repository import (
        SqlAlchemyListRepository,
    )
    from bolsa_infrastructure.ids import new_id

    suffix = uuid.uuid4().hex[:10]
    instrument_id = f"inst-v227-{suffix}"
    symbol = f"V227{suffix[:5].upper()}"
    # Miembros originales de ESTUDIO: se restauran en cleanup (no destructivo).
    original_universe: list[str] = []

    async def _cleanup() -> None:
        async with lifecycle_factory() as session:
            if original_universe:
                repo = SqlAlchemyListRepository(session)
                await repo.ensure_estudio_list()
                await repo.update(
                    SqlAlchemyListRepository.ESTUDIO_LIST_ID,
                    instrument_ids=original_universe,
                )
            await session.execute(
                delete(StrategyEvaluationRow).where(
                    StrategyEvaluationRow.instrument_id == instrument_id
                )
            )
            await session.execute(
                delete(StrategyCandidateRow).where(
                    StrategyCandidateRow.instrument_id == instrument_id
                )
            )
            await session.execute(
                delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id)
            )
            await session.execute(
                delete(InstrumentRow).where(InstrumentRow.id == instrument_id)
            )
            await session.commit()

    await _cleanup()
    try:
        now = datetime.now(UTC)
        async with lifecycle_factory() as session:
            # Instrumento real (el LAB exige get_by_id).
            session.add(
                InstrumentRow(
                    id=instrument_id,
                    symbol=symbol,
                    yahoo_symbol=f"{symbol}.MC",
                    name=f"V227 Test {suffix}",
                    exchange="MCE",
                    country="ES",
                    currency="EUR",
                    type="stock",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            # Serie oscilante con tendencia alcista: SMA cross genera operaciones y un
            # campeón con score > 0 (el gate `backtest` exige score positivo; una serie
            # monótona produce 0 operaciones y no es evidencia válida del LAB).
            base = Decimal("10.00")
            for day in range(420):
                wave = Decimal(str(1.5 * (1 if day % 40 < 20 else -1)))
                drift = Decimal(day) * Decimal("0.03")
                price = base + drift + wave
                session.add(
                    OhlcvBarRow(
                        id=new_id(),
                        instrument_id=instrument_id,
                        timeframe="1d",
                        timestamp=now - timedelta(days=419 - day),
                        open=price,
                        high=price + Decimal("0.10"),
                        low=price - Decimal("0.10"),
                        close=price,
                        volume=1000,
                        adj_close=price,
                        source="yahoo",
                        created_at=now,
                    )
                )
            await session.commit()

            # Universo canónico: se AÑADE el instrumento a ESTUDIO preservando el resto.
            repo = SqlAlchemyListRepository(session)
            existing = await repo.ensure_estudio_list()
            original_universe = list(existing.instrument_ids)
            if instrument_id not in original_universe:
                await repo.update(
                    SqlAlchemyListRepository.ESTUDIO_LIST_ID,
                    instrument_ids=[*original_universe, instrument_id],
                )
            await session.commit()

        # Composición REAL (store + ESTUDIO + LAB), sin inyectar nada.
        orchestrator = _default_orchestrator(lifecycle_factory)

        resolution = await orchestrator.resolve_universe()
        assert resolution is not None
        assert resolution.status == "ok"
        assert instrument_id in resolution.instrument_ids

        result = await orchestrator.run_cycle(
            instrument_id=instrument_id,
            run_id=f"v227-{suffix}",
        )

        # El LAB real se ejecutó: ya no caemos en candidata sintética sin evaluar.
        assert result.evaluated >= 1, result

        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            candidates = await store.list_candidates(instrument_id=instrument_id)
            assert candidates, "el ESTUDIO real debe crear candidata"
            evaluations = await store.list_evaluations(candidates[0].id)
            assert evaluations, "el LAB real debe producir evaluación"
            # Auditable: el ciclo persiste el optimization_run.
            assert any(e.optimization_run_id for e in evaluations)
            # Diagnóstico de gates (el LAB real no promete PASS con cualquier serie).
            gates = {g.gate: g.status.value for g in evaluations[0].gates}
            assert "backtest" in gates
            assert result.status != "sin_evidencia_top3", (result, gates, evaluations[0].metrics)
    finally:
        await _cleanup()


async def test_observed_vigilance_end_to_end_pg(
    lifecycle_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V2.28/A10 (P1-02 real) — la vigilancia usa fills SIM atribuidos a la versión.

    Certifica la cadena completa contra PG real:

    1. se promociona una activa (versión conocida) para un instrumento sembrado;
    2. se insertan fills SIM con ``strategy_version_id`` = esa versión;
    3. la composición REAL construye el provider de métricas observadas;
    4. ``watch_active`` persiste un snapshot de salud con el bloque observado poblado.

    Es el cierre del P1-02: la vigilancia deja de invocarse con ``metrics={}``.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from sqlalchemy import delete

    from bolsa_api.background.auto_orchestrator_worker import _default_orchestrator
    from bolsa_application.sim_durable_store import SimFillFinanceContext
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_infrastructure.database.models.tables import (
        SimFillFinanceContextRow,
        StrategyHealthRow,
    )

    suffix = uuid.uuid4().hex[:10]
    instrument_id = f"inst-v228-{suffix}"
    version_id = f"ver-v228-{suffix}"

    async def _read_active(factory: Any, iid: str) -> Any:
        async with factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            return await store.get_active(instrument_id=iid)

    async def _cleanup() -> None:
        async with lifecycle_factory() as session:
            await session.execute(
                delete(StrategyHealthRow).where(StrategyHealthRow.version_id == version_id)
            )
            await session.execute(
                delete(SimFillFinanceContextRow).where(
                    SimFillFinanceContextRow.instrument_id == instrument_id
                )
            )
            await session.commit()

    await _cleanup()
    try:
        # Activa real: se persiste la VERSIÓN (finalista) + PROMOCIÓN, que es lo que
        # ``get_active`` lee de verdad (``strategy_promotions`` + ``strategy_versions``).
        # Atajar con ``save_active`` no bastaría: no es la fuente del get_active.
        from bolsa_application.strategy_lifecycle_store import (
            StrategyPromotionRecord,
        )
        from bolsa_domain.entities.strategy_lifecycle import (
            StrategyFinalist,
            StrategyPromotion,
        )

        candidate_id = f"cand-v228-{suffix}"
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            await store.save_finalist(
                StrategyFinalist(
                    version_id=version_id,
                    candidate_id=candidate_id,
                    name="v228-observed",
                    definition_hash=f"hash-{suffix}",
                    definition={"instrument_id": instrument_id},
                )
            )
            await store.save_promotion(
                StrategyPromotionRecord(
                    promotion=StrategyPromotion(
                        finalist_id=version_id,
                        promoted=True,
                        reasons=(),
                        shadow_validated=True,
                    ),
                    candidate_id=candidate_id,
                    instrument_id=instrument_id,
                    version_id=version_id,
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
            await session.commit()

        active_record = await _read_active(lifecycle_factory, instrument_id)
        assert active_record is not None, "la promoción real debe dejar activa"
        assert active_record.active.version_id == version_id

        # Fills SIM atribuidos a la versión: 3 round-trips ganadores (guard ≥3).
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            # Se usa el store PG de contexto financiero real vía composición directa.
            from bolsa_application.sim_durable_store import (
                PostgresSimFillFinanceContextStore,
            )

            ctx_store = PostgresSimFillFinanceContextStore(session)
            for i in range(3):
                await ctx_store.save(
                    SimFillFinanceContext(
                        execution_id=f"{suffix}-b-{i}",
                        instrument_id=instrument_id,
                        side="buy",
                        quantity=Decimal("10"),
                        price=Decimal("100"),
                        account_id=None,
                        strategy_version_id=version_id,
                    )
                )
                await ctx_store.save(
                    SimFillFinanceContext(
                        execution_id=f"{suffix}-s-{i}",
                        instrument_id=instrument_id,
                        side="sell",
                        quantity=Decimal("10"),
                        price=Decimal("110"),
                        account_id=None,
                        strategy_version_id=version_id,
                    )
                )
            await session.commit()

        # Guard de muestra mínima: 3 round-trips. Debe fijarse ANTES de componer el
        # orquestador, porque el provider lee el env al construirse.
        import os

        os.environ["AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES"] = "3"
        try:
            orchestrator = _default_orchestrator(lifecycle_factory)
            result = await orchestrator.watch_active(
                instrument_id=instrument_id,
                as_of="v228",
            )
        finally:
            os.environ.pop("AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES", None)

        assert result.active_version_id == version_id

        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            health = await store.list_health(version_id)
            assert health, "la vigilancia debe persistir un snapshot de salud"
            snapshot = health[-1]
            # El bloque observado viene de los fills SIM reales, no de metrics={}.
            assert snapshot.observed_trades == 3
            assert snapshot.observed_return_pct is not None
            assert snapshot.observed_return_pct > 0
    finally:
        await _cleanup()


async def test_promotion_persists_champion_and_coach_pg(
    lifecycle_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V2.29/A10 — la promoción persiste el campeón y el dictamen COACH (PG real).

    Cierra el hueco de atribución de señal: la versión promocionada debe llevar
    ``champion_params`` + ``executable`` (para que la ACTIVE evalúe su propia señal) y
    el dictamen COACH comparativo debe quedar persistido y ser legible.
    """

    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_application.strategy_shadow_phase import ShadowReplayConfig
    from bolsa_domain.entities.strategy_lifecycle import (
        CoachAssessment,
        GateResult,
        ShadowPolicy,
        StrategyEvaluation,
    )

    suffix = uuid.uuid4().hex[:10]
    instrument_id = f"inst-v229-{suffix}"

    async def _cleanup() -> None:
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import (
            StrategyCandidateRow,
            StrategyEvaluationRow,
        )

        async with lifecycle_factory() as session:
            await session.execute(
                delete(StrategyEvaluationRow).where(
                    StrategyEvaluationRow.candidate_id.like(f"cand-v229-{suffix}%")
                )
            )
            await session.execute(
                delete(StrategyCandidateRow).where(
                    StrategyCandidateRow.instrument_id == instrument_id
                )
            )
            await session.commit()

    await _cleanup()

    class _Trial:
        def __init__(self, score: float, params: dict) -> None:
            self.score = score
            self.params = params
            self.oos_metrics = {"score": 0.9}
            self.max_drawdown_pct = 4.0

    class _Result:
        trials = [_Trial(2.0, {"fastPeriod": 10, "slowPeriod": 30})]
        cpcv = {"pbo": 0.1}
        pbo = {"pbo": 0.1}
        walk_forward = {"walkForwardEfficiency": 0.8, "wfe": 0.8}
        edge_report = {"dsr": 0.6}

    class _Resolution:
        status = "ok"
        instrument_ids = [instrument_id]

    async def _resolve() -> _Resolution:
        return _Resolution()

    async def _run_optimize(candidate: object) -> _Result:
        return _Result()

    try:
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            orchestrator = AutoOrchestrator(
                OrchestratorDeps(
                    store=store,
                    resolve_universe=_resolve,
                    run_optimize=_run_optimize,
                    max_candidates=1,
                    shadow_bars=_make_shadow_bars_provider(instrument_id),
                    shadow_policy=ShadowPolicy(min_closed_round_trips=1, min_return_pct=-100.0),
                    shadow_config=ShadowReplayConfig(window_bars=99, min_bars=10),
                )
            )
            result = await orchestrator.run_cycle(instrument_id=instrument_id)

        assert result.promoted, result.reasons

        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            active = await store.get_active(instrument_id=instrument_id)
            assert active is not None
            definition = active.active.definition
            assert definition["champion_params"] == {"fastPeriod": 10, "slowPeriod": 30}
            assert definition["executable"]["presetKey"] == "sma_crossover"

            # El dictamen COACH comparativo queda persistido y es legible.
            candidates = await store.list_candidates(instrument_id=instrument_id)
            assert candidates
            assessments = await store.list_coach_assessments(candidates[0].id)
            assert assessments
            assert assessments[0].candidate_id == candidates[0].id

        # Round-trip directo del store para el dictamen COACH (idempotente).
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            await store.save_coach_assessment(
                CoachAssessment(candidate_id=f"cand-v229-{suffix}-x", approved=True)
            )
            await store.save_coach_assessment(
                CoachAssessment(candidate_id=f"cand-v229-{suffix}-x", approved=True)
            )
            await session.commit()
            rows = await store.list_coach_assessments(f"cand-v229-{suffix}-x")
            assert len(rows) == 1  # idempotente por id determinista
            assert rows[0].approved

        # Round-trip del store de evaluación real (gates + champion) sin pérdida.
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            cid = f"cand-v229-{suffix}-rt"
            await store.save_evaluation(
                StrategyEvaluation(
                    candidate_id=cid,
                    score=1.0,
                    gates=(GateResult.passed_gate("backtest"),),
                    metrics={"instrument_id": instrument_id, "pbo": 0.1},
                )
            )
            await session.commit()
            stored = await store.list_evaluations(cid)
            assert len(stored) == 1
            assert stored[0].metrics["pbo"] == 0.1
    finally:
        await _cleanup()


async def test_paper_forward_result_persistence_pg(
    lifecycle_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V2.33/A13: la evidencia forward se persiste y se relee sin pérdida.

    Certifica el fingerprint reproducible (barras, rango, motor) y la semántica de
    muestra (round-trips/fills ≠ piernas), que es lo que hace auditable el forward.
    """
    from sqlalchemy import delete

    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_domain.entities.strategy_lifecycle import (
        PaperForwardPolicy,
        PaperForwardResult,
    )
    from bolsa_infrastructure.database.models.tables import PaperForwardResultRow

    suffix = uuid.uuid4().hex[:10]
    version_id = f"ver-forward-{suffix}"

    async def _cleanup() -> None:
        async with lifecycle_factory() as session:
            await session.execute(
                delete(PaperForwardResultRow).where(
                    PaperForwardResultRow.version_id == version_id
                )
            )
            await session.commit()

    result = PaperForwardPolicy(
        min_closed_round_trips=1, min_bars=5, min_return_pct=-100.0
    ).evaluate(
        version_id=version_id,
        trades=8,
        round_trips=4,
        return_pct=3.25,
        max_drawdown_pct=2.5,
        win_rate=0.55,
        bars_used=120,
        as_of="2026-10-15",
        data_snapshot_id="snap-forward",
        forward_start="2026-09-12T00:00:00",
        forward_end="2026-10-15T00:00:00",
        bars_hash="deadbeef",
        strategy_definition_hash="def-hash",
        engine_version="paper-forward/2.33.0",
        config_hash="cfg",
        promoted_at="2026-09-11T00:00:00",
        fills=4,
        vetoes=("risk_gate:concentracion",),
    )

    try:
        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            await store.save_forward_result(result)

        async with lifecycle_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            rows = await store.list_forward_results(version_id)

        assert len(rows) == 1
        stored = rows[0]
        assert stored.version_id == version_id
        assert stored.trades == 8
        assert stored.round_trips == 4
        assert stored.passed is True
        assert stored.reasons == ()
        assert stored.forward_start == "2026-09-12T00:00:00"
        assert stored.forward_end == "2026-10-15T00:00:00"
        assert stored.bars_hash == "deadbeef"
        assert stored.engine_version == "paper-forward/2.33.0"
        assert stored.promoted_at == "2026-09-11T00:00:00"
        assert stored.vetoes == ("risk_gate:concentracion",)
        assert isinstance(stored, PaperForwardResult)
    finally:
        await _cleanup()


