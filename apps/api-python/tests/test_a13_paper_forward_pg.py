"""V2.33 / A13 — CERTIFICACIÓN Paper Forward end-to-end (PostgreSQL real).

Certifica el salto que V2.32/A12 deja abierto: la estrategia **ACTIVE** genera señal
sobre **mercado nuevo posterior a la promoción** y ese forward se convierte en evidencia
contable persistida (fills/round-trips/P&L) que alimenta la vigilancia.

Flujo certificado:

    ESTUDIO → LAB → SHADOW (hold-out) → PROMOTION → ACTIVE
            → barras NUEVAS post-promoción → PAPER FORWARD
            → señal propia → fill/round-trips → P&L → evidencia persistida → VIGILANCIA

Certifica además dos invariantes de honestidad:

1. **Frontera temporal**: el forward solo cuenta barras con timestamp estrictamente
   posterior a la promoción; sin barras nuevas NO hay evidencia (``forward_sin_barras``,
   fail-closed), nunca un P&L inventado.
2. **Atribución**: la evidencia forward queda enlazada a la ``version_id`` de la ACTIVE.

Honestidad (patrón del repo): sin PostgreSQL real hace skip salvo que
``PAPER_FORWARD_PG_REQUIRED=1`` (job ``paper-forward-pg``), donde un skip es fallo.
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
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "PAPER_FORWARD_PG_REQUIRED"

pytestmark = pytest.mark.asyncio


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(f"A13 Paper Forward E2E PG requerido pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (A13 Paper Forward) no disponible: {exc}")


@pytest_asyncio.fixture
async def a13_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (035).
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_instrument(session: AsyncSession, instrument_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"A3{suffix.upper()}",
            yahoo_symbol=f"A3{suffix}.MC",
            name=f"A13 E2E {suffix}",
            exchange="MCE",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


async def _seed_bars(
    session: AsyncSession,
    instrument_id: str,
    *,
    total: int,
    start_offset_days: int = 0,
) -> list[str]:
    """Siembra ``total`` barras oscilantes y devuelve sus timestamps ISO (ascendentes).

    La oscilación garantiza cruces de SMA (una serie monótona no produce señales y el
    forward quedaría sin operaciones: un no-fill es un FALLO en la certificación).
    """
    from bolsa_infrastructure.database.models.tables import OhlcvBarRow
    from bolsa_infrastructure.ids import new_id

    now = datetime.now(UTC)
    timestamps: list[str] = []
    base = Decimal("10.00")
    for day in range(total):
        wave = Decimal(str(1.5 if day % 40 < 20 else -1.5))
        price = (base + Decimal(day) * Decimal("0.03") + wave).quantize(Decimal("0.0001"))
        ts = now - timedelta(days=(total - 1 - day) + start_offset_days)
        timestamps.append(ts.isoformat())
        session.add(
            OhlcvBarRow(
                id=new_id(),
                instrument_id=instrument_id,
                timeframe="1d",
                timestamp=ts,
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
    return timestamps


def _make_shadow_bars_provider(factory: async_sessionmaker[AsyncSession]):
    """Barras reales de PG para el replay shadow (mismo contrato que el worker)."""
    from bolsa_api.background.auto_orchestrator_worker import LAB_BAR_LIMIT_DEFAULT

    window = 250

    async def _provider(instrument_id: str) -> tuple[object, ...]:
        from bolsa_api.api.dependencies import get_ohlcv_repository

        async with factory() as session:
            repo = get_ohlcv_repository(session)
            bars = await repo.get_bars(instrument_id, limit=LAB_BAR_LIMIT_DEFAULT + window)
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
    """Discovery determinista (familia H0 con CPCV/WFE soportados)."""
    from bolsa_domain.entities.strategy_lifecycle import StrategyCandidate

    grid = {"fast_periods": [10, 20, 30], "slow_periods": [50, 100, 150]}
    structural = {"cpcv_groups": 4, "walk_forward_folds": 3, "max_trials": 60}

    def _discover(instrument_id: str) -> tuple[object, ...]:
        return tuple(
            StrategyCandidate(
                id=f"disc-{instrument_id}-sma-{index}",
                instrument_id=instrument_id,
                strategy_family="sma_crossover",
                params={**structural, **grid, "seed": index},
            )
            for index in range(3)
        )

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


async def _promote_active(
    factory: async_sessionmaker[AsyncSession],
    instrument_id: str,
):
    """Reutiliza el camino A12 real para dejar una ACTIVE con evidencia shadow."""
    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
    from bolsa_application.strategy_shadow_phase import ShadowReplayConfig
    from bolsa_domain.entities.strategy_lifecycle import ShadowPolicy

    orchestrator = AutoOrchestrator(
        OrchestratorDeps(
            store=_SessionScopedStore(factory),
            run_optimize=_make_real_lab_runner(factory),
            discovery=_make_discovery_runner(),
            shadow_bars=_make_shadow_bars_provider(factory),
            shadow_policy=ShadowPolicy(min_closed_round_trips=1, min_return_pct=-100.0),
            shadow_config=ShadowReplayConfig(window_bars=250, min_bars=30),
            shadow_require_holdout=True,
            max_candidates=6,
        )
    )
    return orchestrator, await orchestrator.run_cycle(
        instrument_id=instrument_id,
        data_snapshot_id="a13-e2e",
        run_id="a13-e2e",
    )


async def test_a13_paper_forward_end_to_end_pg(
    a13_factory: async_sessionmaker[AsyncSession],
) -> None:
    """ACTIVE → barras nuevas → forward (sfill/P&L) → evidencia persistida → vigilancia."""
    from bolsa_application.paper_forward_phase import (
        PaperForwardConfig,
        run_paper_forward,
    )
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_domain.entities.strategy_lifecycle import PaperForwardPolicy
    from bolsa_infrastructure.database.models.tables import PaperForwardResultRow

    instrument_id = f"inst-a13-{uuid.uuid4().hex[:10]}"
    version_id: str | None = None

    try:
        # --- Paso 1: barras históricas y promoción de una ACTIVE (camino A12) --------
        async with a13_factory() as session:
            await _seed_instrument(session, instrument_id)
            await _seed_bars(session, instrument_id, total=700)

        orchestrator, result = await _promote_active(a13_factory, instrument_id)
        assert result.status == "active", result
        assert result.active_version_id
        version_id = result.active_version_id

        async with a13_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            active_record = await store.get_active(instrument_id=instrument_id)
            assert active_record is not None
            active = active_record.active
            assert active.version_id == version_id
            # La ACTIVE promocionada debe traer definición ejecutable (señal propia).
            assert active.definition.get("executable"), (
                "la ACTIVE debe tener definición ejecutable para el forward"
            )

        promoted_at = active.promoted_at or datetime.now(UTC).isoformat()

        # --- Caso negativo PRIMERO: sin barras nuevas no hay evidencia forward -------
        from bolsa_api.api.dependencies import get_ohlcv_repository

        async with a13_factory() as session:
            repo = get_ohlcv_repository(session)
            bars_before = tuple(await repo.get_bars(instrument_id, limit=2000) or ())

        no_new = run_paper_forward(
            active=active,
            bars=bars_before,
            policy=PaperForwardPolicy(min_closed_round_trips=1, min_bars=1, min_return_pct=-1e9),
            config=PaperForwardConfig(promoted_at="2999-01-01T00:00:00"),
        )
        assert no_new.passed is False
        assert "forward_sin_barras" in no_new.reasons
        assert no_new.trades == 0

        # --- Paso 2: sembrar MERCADO NUEVO posterior a la promoción ------------------
        # Barras nuevas con fechas claramente posteriores (offset negativo = futuro);
        # se siembran DESPUÉS de ``promoted_at`` para demostrar la frontera temporal.
        # 400 barras: suficiente para que la SMA lenta (100) se forme y complete al menos
        # un ciclo entrada→salida (con 120 solo se abriría y nunca cerraría).
        async with a13_factory() as session:
            await _seed_bars(
                session,
                instrument_id,
                total=400,
                start_offset_days=-500,
            )
            repo = get_ohlcv_repository(session)
            bars_after = tuple(await repo.get_bars(instrument_id, limit=2000) or ())

        assert len(bars_after) > len(bars_before), "deben existir barras nuevas"

        forward = run_paper_forward(
            active=active,
            bars=bars_after,
            policy=PaperForwardPolicy(
                min_closed_round_trips=1, min_bars=20, min_return_pct=-1e9
            ),
            config=PaperForwardConfig(promoted_at=promoted_at, window_bars=400),
            as_of="a13-e2e-forward",
            data_snapshot_id="a13-e2e",
            vetoes=(),
        )

        # Un no-fill es un FALLO duro: la certificación exige evidencia contable real.
        assert forward.trades > 0, "el forward debe ejecutar operaciones reales"
        assert forward.round_trips > 0, "deben registrarse operaciones cerradas"
        assert forward.bars_used > 0
        assert forward.forward_start is not None and forward.forward_start > promoted_at, (
            "la ventana forward debe empezar ESTRICTAMENTE después de la promoción"
        )
        assert forward.bars_hash, "el fingerprint del dataset forward debe existir"
        assert forward.strategy_definition_hash
        assert forward.engine_version == "paper-forward/2.33.0"

        # --- Paso 3: persistir la evidencia forward y releerla ----------------------
        async with a13_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            await store.save_forward_result(forward)

        async with a13_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            stored = await store.list_forward_results(version_id)
            assert stored, "la evidencia forward debe persistirse"
            latest = stored[-1]
            assert latest.version_id == version_id, "atribución a la versión ACTIVE"
            assert latest.round_trips == forward.round_trips
            assert latest.promoted_at == promoted_at
            assert latest.bars_hash == forward.bars_hash

        # --- Paso 4: la vigilancia sigue operando sobre la ACTIVE -------------------
        watch = await orchestrator.watch_active(
            instrument_id=instrument_id,
            as_of="a13-e2e-post-forward",
        )
        assert watch.status in {"active", "degraded"}, watch
        assert watch.active_version_id == version_id

        # --- Invariante de seguridad: cero publicaciones al bridge LIVE -------------
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow

        async with a13_factory() as session:
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
        assert int(bad or 0) == 0, "AUTO/forward no debe publicar al bridge LIVE"
    finally:
        # Limpieza de la evidencia forward del test (no contaminar otros ciclos).
        if version_id:
            async with a13_factory() as session:
                await session.execute(
                    delete(PaperForwardResultRow).where(
                        PaperForwardResultRow.version_id == version_id
                    )
                )
                await session.commit()


async def test_a13_forward_requires_new_bars_pg(
    a13_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sin barras posteriores a la promoción, la evidencia forward es fail-closed.

    Un sistema honesto no puede declarar un P&L forward cuando la estrategia no ha visto
    ni una barra nueva: se declara ``forward_sin_barras`` y ``passed=False``.
    """
    from bolsa_application.paper_forward_phase import (
        PaperForwardConfig,
        run_paper_forward,
    )
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_domain.entities.strategy_lifecycle import PaperForwardPolicy
    from bolsa_infrastructure.database.models.tables import PaperForwardResultRow

    instrument_id = f"inst-a13n-{uuid.uuid4().hex[:10]}"
    version_id: str | None = None

    try:
        async with a13_factory() as session:
            await _seed_instrument(session, instrument_id)
            await _seed_bars(session, instrument_id, total=700)

        _, result = await _promote_active(a13_factory, instrument_id)
        assert result.status == "active", result
        version_id = result.active_version_id
        assert version_id

        async with a13_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            record = await store.get_active(instrument_id=instrument_id)
            assert record is not None
            active = record.active

        from bolsa_api.api.dependencies import get_ohlcv_repository

        async with a13_factory() as session:
            repo = get_ohlcv_repository(session)
            bars = tuple(await repo.get_bars(instrument_id, limit=2000) or ())

        # ``promoted_at`` en el futuro ⇒ ninguna barra existente es "mercado nuevo".
        forward = run_paper_forward(
            active=active,
            bars=bars,
            policy=PaperForwardPolicy(min_closed_round_trips=1, min_bars=1, min_return_pct=-1e9),
            config=PaperForwardConfig(promoted_at="2999-12-31T23:59:59"),
        )
        assert forward.passed is False
        assert "forward_sin_barras" in forward.reasons
        assert forward.trades == 0
        assert forward.round_trips == 0

        # No se persiste una evidencia "vacía" como si fuera válida.
        async with a13_factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            assert await store.list_forward_results(version_id) == []
    finally:
        if version_id:
            async with a13_factory() as session:
                await session.execute(
                    delete(PaperForwardResultRow).where(
                        PaperForwardResultRow.version_id == version_id
                    )
                )
                await session.commit()
