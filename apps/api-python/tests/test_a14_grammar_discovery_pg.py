"""V2.34 / A14 — CERTIFICACIÓN gramática controlada de Discovery (PostgreSQL real).

Certifica el salto de A14: el Discovery ya no es solo un catálogo de familias fijas, sino
una **gramática controlada** (REGIME + TREND FILTER + MOMENTUM + ENTRY TRIGGER + EXIT)
acotada por presupuesto. Una candidata gramatical debe poder recorrer el lifecycle
completo con evidencia real:

    DISCOVERY (gramática) → LAB (CPCV/PBO/DSR/WFE/OOS reales)
        → 6 GATES → SHADOW (hold-out estricto, H1) → PROMOTION → ACTIVE

Certifica además las invariantes de honestidad del repo:

1. **Sin segundo motor**: la candidata gramatical es una ``StrategyDefinitionV1`` más y
   se ejecuta con el único motor declarativo (``_simulate_rules_strategy``).
2. **Gates medidos de verdad**: la rama declarativa de CPCV/WF produce evidencia, de modo
   que ``robustness``/``walk_forward`` no quedan NOT_EVALUATED (el fallo de fondo que A14
   cierra). Antes de A14 ningún candidato declarativo podía promocionar.
3. **Fail-closed**: sin evidencia shadow no hay promoción (``shadow_validation_requerida``).
4. **Cero LIVE**: el ciclo no publica al bridge LIVE (``ExecutionEventRow`` live == 0).

Honestidad (patrón del repo): sin PostgreSQL real hace skip salvo que
``A14_GRAMMAR_PG_REQUIRED=1`` (job dedicado), donde un skip es fallo. NUNCA abre LIVE.
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
_REQUIRED_ENV = "A14_GRAMMAR_PG_REQUIRED"

pytestmark = pytest.mark.asyncio


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"A14 Grammar Discovery E2E PG requerido pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (A14 Grammar Discovery) no disponible: {exc}")


@pytest_asyncio.fixture
async def a14_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (035: A14 no migra).
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
            symbol=f"A4{suffix.upper()}",
            yahoo_symbol=f"A4{suffix}.MC",
            name=f"A14 E2E {suffix}",
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


async def _seed_bars(session: AsyncSession, instrument_id: str, *, total: int) -> list[str]:
    """Siembra ``total`` barras oscilantes (cruces de EMA ⇒ señales y fills reales)."""
    from bolsa_infrastructure.database.models.tables import OhlcvBarRow
    from bolsa_infrastructure.ids import new_id

    now = datetime.now(UTC)
    timestamps: list[str] = []
    base = Decimal("10.00")
    for day in range(total):
        wave = Decimal(str(1.5 if day % 40 < 20 else -1.5))
        price = (base + Decimal(day) * Decimal("0.03") + wave).quantize(Decimal("0.0001"))
        ts = now - timedelta(days=(total - 1 - day))
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


def _make_grammar_discovery_runner(budget: dict[str, int] | None = None):
    """Discovery REAL con la gramática habilitada (A14), determinista.

    Usa ``discover_for_instrument`` con un ``GrammarBudget``: las candidatas emitidas son
    gramaticales (``strategy_family`` con prefijo ``grammar:``). El wiring es el real; la
    única diferencia con producción es que aquí se habilita la gramática explícitamente.
    """
    from bolsa_application.discovery_catalog import DiscoveryBudget
    from bolsa_application.discovery_grammar import GrammarBudget
    from bolsa_application.strategy_discovery_engine import discover_for_instrument

    base = DiscoveryBudget(**(budget or {}))

    def _discover(instrument_id: str) -> tuple[object, ...]:
        return discover_for_instrument(
            instrument_id=instrument_id,
            budget=base,
            grammar_budget=GrammarBudget(base=base),
            bar_count=700,
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


def _build_orchestrator(factory: async_sessionmaker[AsyncSession], *, shadow_bars):
    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
    from bolsa_application.strategy_shadow_phase import ShadowReplayConfig
    from bolsa_domain.entities.strategy_lifecycle import ShadowPolicy

    return AutoOrchestrator(
        OrchestratorDeps(
            store=_SessionScopedStore(factory),
            run_optimize=_make_real_lab_runner(factory),
            discovery=_make_grammar_discovery_runner(
                {
                    "max_trials_total": 48,
                    "max_per_family": 8,
                    "max_candidates": 24,
                }
            ),
            shadow_bars=shadow_bars,
            shadow_policy=ShadowPolicy(min_closed_round_trips=1, min_return_pct=-100.0),
            shadow_config=ShadowReplayConfig(window_bars=250, min_bars=30),
            max_candidates=8,
        )
    )


async def test_a14_grammar_candidate_is_discovered_and_promotes_or_fails_honestly(
    a14_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Una candidata GRAMATICAL recorre el lifecycle con evidencia real de gates.

    El objetivo no es forzar un PASS (una estrategia puede legítimamente no superar los
    gates), sino certificar que:

    * el Discovery emite candidatas gramaticales reales (``grammar:``);
    * el LAB las evalúa con la vía declarativa produciendo CPCV/PBO/WFE reales;
    * los gates ``robustness``/``walk_forward`` ya NO quedan NOT_EVALUATED;
    * si no hay evidencia shadow, la promoción es fail-closed;
    * si promociona, la ACTIVE trae definición ejecutable del campeón.
    """
    from bolsa_application.discovery_grammar import enumerate_grammar_plans
    from bolsa_application.optimize import RunSmaGridOptimize
    from bolsa_application.strategy_lab_phase import evaluate_optimize_result
    from bolsa_domain.entities.strategy_lifecycle import GateStatus, StrategyCandidate
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    instrument_id = f"inst-a14-{uuid.uuid4().hex[:10]}"
    try:
        async with a14_factory() as session:
            await _seed_instrument(session, instrument_id)
            await _seed_bars(session, instrument_id, total=700)

        # --- 1) Discovery real: hay candidatas gramaticales ------------------------
        discovery = _make_grammar_discovery_runner(
            {"max_trials_total": 48, "max_per_family": 8, "max_candidates": 24}
        )
        candidates = discovery(instrument_id)
        grammar_candidates = [
            c for c in candidates if str(c.strategy_family).startswith("grammar:")
        ]
        assert grammar_candidates, "el Discovery no emitió candidatas gramaticales"
        assert any(
            str(c.params.get("discovery_parent")) == "grammar" for c in grammar_candidates
        )

        # --- 2) El LAB declarativo mide gates reales sobre candidatas gramaticales --
        # Se evalúan planes gramaticales reales vía el motor declarativo (la misma ruta
        # que el orquestador: ``execute(definition=...)``). No todos los planes ganan
        # dinero en la serie sembrada; se certifica que el CPCV/PBO declarativo produce
        # evidencia REAL para los planes que sí operan, y que los gates dejan de quedar
        # NOT_EVALUATED cuando hay evidencia.
        from bolsa_api.api.dependencies import get_instrument_repository, get_ohlcv_repository
        from bolsa_application.discovery_grammar import grammar_variants_for_plan

        evaluated_with_evidence = 0
        checked_gate_status = False
        for plan in enumerate_grammar_plans():
            definition = plan.materialize()
            if definition is None:
                continue
            variants = grammar_variants_for_plan(plan, max_variants=4)
            if len(variants) < 2:
                # Sin variantes hermanas el PBO CSCV no tiene columnas que rankear.
                continue
            async with a14_factory() as session:
                use_case = RunSmaGridOptimize(
                    get_instrument_repository(session),
                    get_ohlcv_repository(session),
                )
                result = await use_case.execute(
                    instrument_id=instrument_id,
                    strategy_family=f"grammar:{plan.preset_key}",
                    definition=definition,
                    grammar_variants=variants,
                    bar_limit=400,
                    max_trials=10,
                    cpcv_groups=4,
                )
            if result.cpcv is None or not result.cpcv.get("pathCount"):
                continue
            assert result.cpcv.get("pathCount", 0) > 0
            if result.pbo is None:
                # El plan no reúne las condiciones del CSCV (p. ej. pierde en casi todos
                # los paths): no se fuerza evidencia, se prueba otro plan.
                continue
            if result.cpcv.get("walkForwardEfficiency") is None:
                # Un plan que pierde dinero no tiene WFE (mean IS <= 0): se prueba otro.
                continue
            evaluated_with_evidence += 1

            candidate = StrategyCandidate(
                id=f"disc-{instrument_id}-grammar-{evaluated_with_evidence}",
                instrument_id=instrument_id,
                strategy_family=f"grammar:{plan.preset_key}",
                params={"definition": definition},
                origin="discovery",
                preset_key=plan.preset_key,
            )
            evaluation = evaluate_optimize_result(candidate=candidate, result=result)
            by_gate = {gate.gate: gate for gate in evaluation.gates}
            # Con evidencia real, robustness/walk_forward ya no pueden quedar N/E.
            assert by_gate["robustness"].status is not GateStatus.NOT_EVALUATED, (
                "A14 debe medir robustness sobre la vía declarativa"
            )
            assert by_gate["walk_forward"].status is not GateStatus.NOT_EVALUATED, (
                "A14 debe medir walk_forward sobre la vía declarativa"
            )
            checked_gate_status = True
            break

        assert evaluated_with_evidence > 0, (
            "ningún plan gramatical produjo evidencia CPCV/PBO real"
        )
        assert checked_gate_status

        # --- 3) Fail-closed: sin evidencia shadow no hay promoción ------------------
        no_shadow_orchestrator = _build_orchestrator(a14_factory, shadow_bars=None)
        no_shadow = await no_shadow_orchestrator.run_cycle(
            instrument_id=instrument_id,
            data_snapshot_id="a14-e2e",
            run_id="a14-e2e-no-shadow",
        )
        assert no_shadow.status in {"no_promocionada", "sin_candidatas_discovery"}, no_shadow
        if no_shadow.status == "no_promocionada":
            assert "shadow_validation_requerida" in no_shadow.reasons

        # --- 4) Ciclo real completo con shadow: promoción o rechazo honesto ---------
        orchestrator = _build_orchestrator(
            a14_factory, shadow_bars=_make_shadow_bars_provider(a14_factory)
        )
        result_cycle = await orchestrator.run_cycle(
            instrument_id=instrument_id,
            data_snapshot_id="a14-e2e",
            run_id="a14-e2e",
        )
        assert result_cycle.status in {"active", "no_promocionada", "sin_candidatas_discovery"}

        if result_cycle.status == "active":
            from bolsa_application.strategy_lifecycle_store import (
                PostgresStrategyLifecycleStore,
            )

            async with a14_factory() as session:
                store = PostgresStrategyLifecycleStore(session)
                record = await store.get_active(instrument_id=instrument_id)
                assert record is not None
                assert record.active.version_id == result_cycle.active_version_id
                # La ACTIVE debe traer el ejecutable del CAMPEÓN (no el punto plantilla).
                assert record.active.definition.get("executable")

        # --- 5) Invariante LIVE: cero publicaciones al bridge real ------------------
        async with a14_factory() as session:
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
        assert int(bad or 0) == 0, "AUTO/A14 no debe publicar al bridge LIVE"
    finally:
        # Limpieza del estado de lifecycle del test (no contaminar otros ciclos).
        await _cleanup_lifecycle(a14_factory, instrument_id)


async def test_a14_promotion_requires_shadow_evidence_pg(
    a14_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sin evidencia shadow ejecutada, la promoción es fail-closed (H1 intacto)."""
    instrument_id = f"inst-a14n-{uuid.uuid4().hex[:10]}"
    try:
        async with a14_factory() as session:
            await _seed_instrument(session, instrument_id)
            await _seed_bars(session, instrument_id, total=700)

        orchestrator = _build_orchestrator(a14_factory, shadow_bars=None)
        result = await orchestrator.run_cycle(
            instrument_id=instrument_id,
            data_snapshot_id="a14-e2e",
            run_id="a14-e2e-negative",
        )
        assert result.status in {"no_promocionada", "sin_candidatas_discovery"}
        if result.status == "no_promocionada":
            assert "shadow_validation_requerida" in result.reasons
    finally:
        await _cleanup_lifecycle(a14_factory, instrument_id)


async def _cleanup_lifecycle(
    factory: async_sessionmaker[AsyncSession], instrument_id: str
) -> None:
    """Borra el rastro de lifecycle del test para no contaminar otros ciclos."""
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore

    try:
        async with factory() as session:
            store = PostgresStrategyLifecycleStore(session)
            record = await store.get_active(instrument_id=instrument_id)
            if record is not None:
                from bolsa_infrastructure.database.models.tables import StrategyVersionRow

                await session.execute(
                    delete(StrategyVersionRow).where(
                        StrategyVersionRow.instrument_id == instrument_id
                    )
                )
                await session.commit()
    except Exception:  # noqa: BLE001 — la limpieza best-effort no debe enmascarar fallos.
        pass
