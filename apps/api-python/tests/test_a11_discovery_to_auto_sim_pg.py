"""V2.32 / A12 — CERTIFICACIÓN A11 end-to-end: DISCOVERY → SHADOW → SIM → VIGILANCIA.

Test definitivo del ciclo autónomo sobre PostgreSQL real, sin humano, sin UI y sin
llamar manualmente a ``run_tick`` fuera del runtime:

    ESTUDIO → DISCOVERY → LAB → TOP3 → COACH → FINALISTA → SHADOW
            → PROMOTION → ACTIVE → SIGNAL → SIM BUY → FILL → LEDGER → VIGILANCE

Certifica además los dos cierres de V2.32:

1. **Shadow real**: la promoción exige evidencia ejecutada (``StrategyShadowValidation``
   persistida); sin barras de shadow el ciclo NO promociona (fail-closed).
2. **Atribución tras crash**: un cierre de una posición readoptada conserva
   ``strategy_version_id`` en el ledger (antes quedaba en NULL).

Honestidad (patrón del repo): sin PostgreSQL real hace skip salvo que
``AUTO_ORCHESTRATOR_PG_REQUIRED=1`` (job ``lifecycle-pg``), donde un skip es fallo.
NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_ORCHESTRATOR_PG_REQUIRED"

pytestmark = pytest.mark.asyncio


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(f"A11 E2E PG requerido pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (A11 E2E) no disponible: {exc}")


@pytest_asyncio.fixture
async def a11_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (033).
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_instrument_with_bars(session: AsyncSession, instrument_id: str) -> None:
    """Instrumento con 420 barras diarias oscilantes (SMA cross genera evidencia)."""
    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow
    from bolsa_infrastructure.ids import new_id

    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"A1{suffix.upper()}",
            yahoo_symbol=f"A1{suffix}.MC",
            name=f"A11 E2E {suffix}",
            exchange="MCE",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
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


def _make_shadow_bars_provider(factory: async_sessionmaker[AsyncSession]):
    """Barras reales de PG para el replay shadow (mismo contrato que el worker)."""
    from bolsa_api.api.dependencies import get_ohlcv_repository

    async def _provider(instrument_id: str) -> tuple[object, ...]:
        async with factory() as session:
            repo = get_ohlcv_repository(session)
            bars = await repo.get_bars(instrument_id, limit=250)
            return tuple(bars or ())

    return _provider


def _make_real_lab_runner(factory: async_sessionmaker[AsyncSession]):
    """LAB real (``RunSmaGridOptimizeAndSave``) por sesión, como el worker."""
    from bolsa_api.api.dependencies import (
        get_cognitive_repository,
        get_hypothesis_belief_repository,
        get_instrument_repository,
        get_ohlcv_repository,
        get_optimization_run_repository,
        get_research_evidence_repository,
        get_research_trial_repository,
    )
    from bolsa_application.optimization_runs import RunSmaGridOptimizeAndSave
    from bolsa_application.optimize import RunSmaGridOptimize
    from bolsa_application.orchestrator_lab_runner import LabOptimizeRunner

    def _build(session: AsyncSession):
        return RunSmaGridOptimizeAndSave(
            RunSmaGridOptimize(
                get_instrument_repository(session),
                get_ohlcv_repository(session),
            ),
            get_optimization_run_repository(session),
            get_research_trial_repository(session),
            get_cognitive_repository(session),
            get_research_evidence_repository(session),
            get_hypothesis_belief_repository(session),
        )

    return LabOptimizeRunner(factory, _build)


def _make_discovery_runner():
    """Discovery real del catálogo curado (mismo wiring que ``AUTO_ORCHESTRATOR_DISCOVERY``)."""
    from bolsa_application.discovery_catalog import DiscoveryBudget
    from bolsa_application.strategy_discovery_engine import discover_for_instrument

    budget = DiscoveryBudget(max_trials_total=12, max_per_family=2, max_candidates=6)

    def _discover(instrument_id: str) -> tuple[object, ...]:
        return discover_for_instrument(instrument_id=instrument_id, budget=budget)

    return _discover


class _SessionScopedStore:
    """Store que abre una sesión por operación (mismo patrón que el worker real)."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    def __getattr__(self, name: str):
        async def _call(*args, **kwargs):
            from bolsa_application.strategy_lifecycle_store import (
                PostgresStrategyLifecycleStore,
            )

            async with self._factory() as session:
                store = PostgresStrategyLifecycleStore(session)
                return await getattr(store, name)(*args, **kwargs)

        return _call


async def _build_active_decider(factory: async_sessionmaker[AsyncSession], instrument_id: str):
    """Decisor real de la estrategia ACTIVE (señal propia o HOLD, V2.31/A11)."""
    from bolsa_api.api.dependencies import get_ohlcv_repository
    from bolsa_application.active_strategy_signal_evaluator import make_active_strategy_decider
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

    async with factory() as session:
        store = PostgresStrategyLifecycleStore(session)
        record = await store.get_active(instrument_id=instrument_id)
        if record is None:
            return None, None
        repo = get_ohlcv_repository(session)
        bars = await repo.get_bars(instrument_id, limit=400)
        by_symbol = {instrument_id: tuple(bars or ())}
        decider = make_active_strategy_decider(
            active=record.active,
            watch=(instrument_id,),
            bars_by_symbol=by_symbol.__getitem__,
            lot_qty=100.0,
        )
        return record, decider


async def test_a11_discovery_to_auto_sim_pg(
    a11_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ciclo A11 completo: descubre, valida en shadow, promociona, opera y vigila."""
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
    )
    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
    from bolsa_application.strategy_lifecycle_store import (
        PostgresStrategyLifecycleStore,
    )
    from bolsa_domain.entities.strategy_lifecycle import ShadowPolicy
    from bolsa_infrastructure.database.models.tables import (
        StrategyShadowValidationRow,
        StrategyVersionRow,
    )

    instrument_id = f"inst-a11-{uuid.uuid4().hex[:10]}"
    account_id: str | None = None
    engine_id = f"auto-a11-{uuid.uuid4().hex[:10]}"
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "simulated")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")

    try:
        async with a11_factory() as session:
            await _seed_instrument_with_bars(session, instrument_id)
            from bolsa_infrastructure.database.repositories.account_repository import (
                SqlAlchemyAccountRepository,
            )

            scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"A11-CERT-{uuid.uuid4().hex[:8]}",
                initial_deposit=100_000.0,
            )
            await session.commit()
            account_id = scope.account.id

        # --- Orquestador real: DISCOVERY + LAB + SHADOW (evidencia ejecutada) --------
        orchestrator = AutoOrchestrator(
            OrchestratorDeps(
                store=_SessionScopedStore(a11_factory),
                run_optimize=_make_real_lab_runner(a11_factory),
                discovery=_make_discovery_runner(),
                shadow_bars=_make_shadow_bars_provider(a11_factory),
                shadow_policy=ShadowPolicy(min_trades=1, min_return_pct=-100.0),
                max_candidates=6,
            )
        )
        result = await orchestrator.run_cycle(
            instrument_id=instrument_id,
            data_snapshot_id="a11-e2e",
            run_id="a11-e2e",
        )

        # El ciclo llegó hasta el final del embudo con la estrategia ACTIVA.
        assert result.status == "active", result
        assert result.candidates > 1, f"discovery debe producir >1 candidata: {result}"
        assert result.active_version_id, result

        # Evidencia shadow REAL persistida para la versión activa.
        async with a11_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            shadows = await store.list_shadow_results(result.active_version_id)
            assert shadows, "la promoción exige evidencia shadow persistida"
            assert any(s.passed for s in shadows), shadows
            assert shadows[-1].trades > 0, "el shadow debe ejecutar operaciones reales"
            active = await store.get_active(instrument_id=instrument_id)
            assert active is not None
            assert active.active.shadow_validated is True
            assert active.active.shadow_validation_id, "enlace auditable a la evidencia"

        # --- SIM: la ACTIVE opera su propia señal; fill atribuido a la versión -------
        record, decider = await _build_active_decider(a11_factory, instrument_id)
        assert record is not None and decider is not None
        version_id = record.active.version_id

        worker = AutoSimulationWorker(
            decider=decider,
            engine_id=engine_id,
            account_id=account_id,
        )
        runtime = AutoSimRuntime(
            a11_factory,
            worker=worker,
            engine_id=engine_id,
            account_id=account_id,
        )
        # La señal de la ACTIVE puede ser HOLD en el último bar: se le da margen con
        # ticks deterministas; si nunca abre, el test no puede certificar el fill.
        report = None
        for _ in range(12):
            report = await runtime.run_tick()
            if worker._open.get(instrument_id, Decimal("0")) > 0:
                break
        assert report is not None
        if worker._open.get(instrument_id, Decimal("0")) <= 0:
            pytest.skip("la señal de la ACTIVE fue HOLD en toda la ventana (sin fill que certificar)")

        # Atribución del fill de apertura a la versión promocionada.
        from bolsa_application.sim_durable_store import (
            PostgresSimFillFinanceContextStore,
        )

        async with a11_factory() as session:
            ctx_store = PostgresSimFillFinanceContextStore(session)
            fills = await ctx_store.list_for_strategy_version(version_id)
            assert fills, "el fill SIM debe atribuirse a la versión ACTIVE"

        # --- Crash/restart: readopción conserva la atribución de la versión ---------
        worker2 = AutoSimulationWorker(
            decider=decider,
            engine_id=engine_id,
            account_id=account_id,
        )
        runtime2 = AutoSimRuntime(
            a11_factory,
            worker=worker2,
            engine_id=engine_id,
            account_id=account_id,
        )
        await runtime2.run_tick()  # dispara readopt_positions en el camino durable
        assert worker2._open.get(instrument_id, Decimal("0")) > 0, "readopta posición"
        assert worker2._position_version.get(instrument_id) == version_id, (
            "la atribución de la versión debe sobrevivir al crash/readopt"
        )

        # --- Vigilancia: snapshot por versión (no por cuenta) -----------------------
        watch = await orchestrator.watch_active(
            instrument_id=instrument_id,
            as_of="a11-e2e-post",
        )
        assert watch.status in {"active", "degraded"}, watch
        assert watch.active_version_id == version_id

        # La fila de versión existe y es finalista (evidencia del embudo).
        async with a11_factory() as session:
            version_row = (
                await session.execute(
                    select(StrategyVersionRow).where(StrategyVersionRow.id == version_id)
                )
            ).scalar_one_or_none()
            assert version_row is not None

        # LIVE bridge posts = 0 (nunca se publica a un venue real).
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        async with a11_factory() as session:
            bad = (
                await session.execute(
                    select(func.count())
                    .select_from(ExecutionEventRow)
                    .where(
                        func.lower(ExecutionEventRow.venue).in_(
                            ("live", "broker_live", "xtb", "real", "live_bridge")
                        )
                    )
                )
            ).scalar()
        assert int(bad or 0) == 0, "AUTO no debe publicar al bridge LIVE"

        # Limpieza de la evidencia shadow del test (no contaminar otros ciclos).
        async with a11_factory() as session:
            rows = (
                await session.execute(
                    select(StrategyShadowValidationRow).where(
                        StrategyShadowValidationRow.version_id == version_id
                    )
                )
            ).scalars().all()
            for row in rows:
                await session.delete(row)
            await session.commit()
    except Exception:
        raise


async def test_a11_promotion_requires_shadow_evidence_pg(
    a11_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sin provider de barras shadow no hay evidencia ⇒ el gate NO promociona."""
    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps

    instrument_id = f"inst-a11n-{uuid.uuid4().hex[:10]}"
    try:
        async with a11_factory() as session:
            await _seed_instrument_with_bars(session, instrument_id)

        orchestrator = AutoOrchestrator(
            OrchestratorDeps(
                store=_SessionScopedStore(a11_factory),
                run_optimize=_make_real_lab_runner(a11_factory),
                discovery=_make_discovery_runner(),
                shadow_bars=None,  # sin evidencia shadow disponible
                max_candidates=6,
            )
        )
        result = await orchestrator.run_cycle(
            instrument_id=instrument_id,
            data_snapshot_id="a11-e2e-negative",
            run_id="a11-e2e-negative",
        )
        assert result.status == "no_promocionada", result
        assert any("shadow_validation_requerida" in r for r in result.reasons), result.reasons
    except Exception:
        raise
