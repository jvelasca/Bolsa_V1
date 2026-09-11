"""V2.26 / A10 — Auto Orchestrator (tests herméticos, SIM-only).

Certifica el ciclo completo ESTUDIO→…→ACTIVE→vigilancia con dependencias inyectadas:
sin evidencia no promociona, el COACH puede vetar, la promoción exige shadow, y la
degradación dispara re-LAB (nunca swap directo).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pytest

from bolsa_application.auto_orchestrator import (
    AutoOrchestrator,
    OrchestratorDeps,
    active_strategy_decider,
)
from bolsa_application.discovery_catalog import DiscoveryBudget, family_by_name
from bolsa_application.strategy_discovery_engine import discover_for_instrument
from bolsa_application.strategy_lifecycle_store import InMemoryStrategyLifecycleStore
from bolsa_application.strategy_top3_coach_phase import CoachThresholds
from bolsa_domain.entities.strategy_lifecycle import PROMOTION_GATES, ActiveStrategy

# ── Dobles ──────────────────────────────────────────────────────────────────────


@dataclass
class _Trial:
    score: float
    oos_metrics: dict[str, Any] | None = None
    max_drawdown_pct: float | None = 5.0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class _OptimizeResult:
    trials: list[_Trial] = field(default_factory=list)
    cpcv: dict[str, Any] | None = None
    pbo: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    edge_report: dict[str, Any] | None = None


def _good_result() -> _OptimizeResult:
    return _OptimizeResult(
        trials=[
            _Trial(
                score=1.5,
                oos_metrics={"score": 0.9},
                max_drawdown_pct=4.0,
                params={"fastPeriod": 10, "slowPeriod": 30},
            )
        ],
        cpcv={"pbo": 0.1},
        pbo={"pbo": 0.1},
        walk_forward={"walkForwardEfficiency": 0.7, "wfe": 0.7},
        edge_report={"dsr": 0.5},
    )


@dataclass
class _Resolution:
    status: str = "ok"
    instrument_ids: list[str] = field(default_factory=lambda: ["AAA"])


def _deps(
    *,
    runner: Any = None,
    resolution: Any = None,
    health_thresholds: Any = None,
) -> tuple[OrchestratorDeps, InMemoryStrategyLifecycleStore]:
    store = InMemoryStrategyLifecycleStore()
    deps = OrchestratorDeps(
        store=store,
        resolve_universe=(lambda: _runner(resolution)) if resolution is not None else None,
        run_optimize=(lambda candidate: _runner(runner(candidate))),
        max_candidates=3,
        **( {"health_thresholds": health_thresholds} if health_thresholds is not None else {} ),
    )
    return deps, store


async def _runner(value: Any) -> Any:
    return value


# ── Ciclo feliz ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_cycle_promotes_with_shadow() -> None:
    deps, store = _deps(runner=lambda c: _good_result(), resolution=_Resolution())
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(
        instrument_id="AAA", data_snapshot_id="snap-1", shadow_validated=True
    )
    assert result.status == "active"
    assert result.promoted
    assert result.active_version_id is not None
    active = await store.get_active(instrument_id="AAA")
    assert active is not None
    assert active.active.version_id == result.active_version_id


@pytest.mark.asyncio
async def test_cycle_without_shadow_does_not_promote() -> None:
    deps, store = _deps(runner=lambda c: _good_result(), resolution=_Resolution())
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(
        instrument_id="AAA", data_snapshot_id="snap-1", shadow_validated=False
    )
    assert result.status == "no_promocionada"
    assert not result.promoted
    assert "shadow_validation_requerida" in result.reasons
    assert await store.get_active(instrument_id="AAA") is None


@pytest.mark.asyncio
async def test_cycle_without_evidence_does_not_promote() -> None:
    deps, _store = _deps(runner=lambda c: None, resolution=_Resolution())
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    assert result.status == "sin_evidencia_top3"
    assert not result.promoted


@pytest.mark.asyncio
async def test_universe_unavailable_produces_no_candidates() -> None:
    deps, _store = _deps(runner=lambda c: _good_result(), resolution=_Resolution(status="unavailable"))
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    assert result.status == "unavailable"
    assert result.candidates == 0


# ── Vigilancia ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vigilance_degrades_to_relab() -> None:
    # V2.32.1 (auditoría 2b): los umbrales predictivos ya no se inventan con 0.0; el
    # llamante debe configurarlos explícitamente para que la vigilancia los aplique.
    from bolsa_application.strategy_vigilance_phase import HealthThresholds

    deps, store = _deps(
        runner=lambda c: _good_result(),
        resolution=_Resolution(),
        health_thresholds=HealthThresholds(min_edge=0.0, min_wfe=0.5),
    )
    orchestrator = AutoOrchestrator(deps)
    await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    watched = await orchestrator.watch_active(
        instrument_id="AAA",
        metrics={"edge": -0.5, "wfe": 0.1},
        as_of="2026-09-11",
    )
    assert watched.degraded
    assert watched.relab_triggered
    assert watched.status == "degraded"
    # La degradación NO sustituye la activa (solo propone re-LAB).
    active = await store.get_active(instrument_id="AAA")
    assert active is not None


@pytest.mark.asyncio
async def test_watch_without_active_is_noop() -> None:
    deps, _store = _deps()
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.watch_active(instrument_id="ZZZ", metrics={}, as_of="x")
    assert result.status == "sin_activa"


# ── Seam DecisionProvider (SIM-only) ────────────────────────────────────────────


def test_active_strategy_decider_rebuilds_lot_and_source() -> None:
    from bolsa_application.decision_contract import DecisionPackage

    def fallback(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=50)

    active = ActiveStrategy(
        version_id="ver-1",
        candidate_id="cand-1",
        instrument_id="AAA",
        name="SMA",
        definition={"lot_qty": 100.0, "watch": ["AAA"]},
    )
    decider = active_strategy_decider(active=active, fallback=fallback, watch=("AAA",))
    prop = decider("AAA")
    assert prop.action == "BUY"
    assert prop.quantity == 50  # no supera el lote de la estrategia
    assert prop.source == "active-strategy:ver-1"


def test_active_strategy_decider_holds_outside_watch() -> None:
    from bolsa_application.decision_contract import DecisionPackage

    def fallback(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=50)

    active = ActiveStrategy(
        version_id="ver-1",
        candidate_id="cand-1",
        instrument_id="AAA",
        name="SMA",
        definition={"lot_qty": 100.0, "watch": ["AAA"]},
    )
    decider = active_strategy_decider(active=active, fallback=fallback, watch=("AAA",))
    assert decider("BBB").action == "HOLD"


def test_promotion_gate_names_are_the_six() -> None:
    assert set(PROMOTION_GATES) == {
        "backtest",
        "robustness",
        "walk_forward",
        "oos",
        "risk",
        "coach",
    }


# ── Campeón persistido (V2.29) ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promoted_version_carries_champion_params_and_executable() -> None:
    """La versión promocionada incluye los params del campeón y la definición ejecutable."""
    deps, store = _deps(runner=lambda c: _good_result(), resolution=_Resolution())
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    assert result.promoted

    active = await store.get_active(instrument_id="AAA")
    assert active is not None
    definition = active.active.definition
    assert definition["champion_params"] == {"fastPeriod": 10, "slowPeriod": 30}
    executable = definition["executable"]
    assert executable["presetKey"] == "sma_crossover"
    assert executable["indicatorSpecs"] == [
        {"definitionId": "sma", "parameters": {"period": 10}},
        {"definitionId": "sma", "parameters": {"period": 30}},
    ]


@pytest.mark.asyncio
async def test_version_without_champion_keeps_plain_definition() -> None:
    """Sin params de campeón no se inventa definición ejecutable (fail-closed)."""
    no_params = _OptimizeResult(
        trials=[_Trial(score=1.5, oos_metrics={"score": 0.9}, max_drawdown_pct=4.0)],
        cpcv={"pbo": 0.1},
        pbo={"pbo": 0.1},
        walk_forward={"walkForwardEfficiency": 0.7, "wfe": 0.7},
        edge_report={"dsr": 0.5},
    )
    deps, store = _deps(runner=lambda c: no_params, resolution=_Resolution())
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    assert result.promoted

    active = await store.get_active(instrument_id="AAA")
    assert active is not None
    assert "executable" not in active.active.definition
    assert "champion_params" not in active.active.definition


# ── COACH comparativo (V2.29) ───────────────────────────────────────────────────


@dataclass
class _MultiResolution:
    """Universo con VARIAS candidatas para el mismo instrumento (COACH comparativo)."""

    status: str = "ok"
    instrument_ids: list[str] = field(
        default_factory=lambda: ["AAA", "AAA", "AAA"]
    )


@pytest.mark.asyncio
async def test_coach_comparativo_persists_all_assessments() -> None:
    """El COACH dictamina el TOP3 entero y persiste un assessment por candidato."""
    deps, store = _deps(runner=lambda c: _good_result(), resolution=_MultiResolution())
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)

    assert result.status == "active"
    candidates = await store.list_candidates(instrument_id="AAA")
    assert len(candidates) == 3
    # Un dictamen por cada candidata evaluada.
    total = 0
    for candidate in candidates:
        total += len(await store.list_coach_assessments(candidate.id))
    assert total == 3


@pytest.mark.asyncio
async def test_coach_comparativo_veto_blocks_promotion_with_aggregated_reasons() -> None:
    """Si TODOS los candidatos quedan vetados, no se promociona (fail-closed)."""
    deps, store = _deps(runner=lambda c: _good_result(), resolution=_MultiResolution())
    # PBO por encima del umbral del COACH ⇒ veta a todas las candidatas.
    deps.coach_thresholds = CoachThresholds(max_pbo=-1.0)
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)

    assert result.status == "coach_veto"
    assert not result.promoted
    assert "pbo_alto" in result.reasons
    assert await store.get_active(instrument_id="AAA") is None


# ── Discovery Engine (V2.31/A11) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_replaces_single_candidate_and_promotes() -> None:
    """Con el discovery cableado, el ciclo usa sus candidatas y puede promocionar."""
    store = InMemoryStrategyLifecycleStore()
    deps = OrchestratorDeps(
        store=store,
        run_optimize=(lambda candidate: _runner(_good_result())),
        discovery=lambda instrument_id: discover_for_instrument(
            instrument_id=instrument_id,
            budget=DiscoveryBudget(max_trials_total=3, max_per_family=1, max_candidates=3),
        ),
    )
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    assert result.status == "active"
    assert result.promoted
    candidates = await store.list_candidates(instrument_id="AAA")
    assert len(candidates) == 3
    assert all(c.origin == "discovery" for c in candidates)


@pytest.mark.asyncio
async def test_discovery_without_candidates_does_not_invent_one() -> None:
    """Discovery vacío ⇒ fail-closed: no se sintetiza la candidata única."""
    store = InMemoryStrategyLifecycleStore()
    deps = OrchestratorDeps(
        store=store,
        run_optimize=(lambda candidate: _runner(_good_result())),
        discovery=lambda instrument_id: (),
    )
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    assert result.status == "sin_candidatas_discovery"
    assert result.candidates == 0
    assert not result.promoted
    assert await store.get_active(instrument_id="AAA") is None


@pytest.mark.asyncio
async def test_discovery_definition_is_carried_to_promoted_version() -> None:
    """La versión promocionada conserva la definición ejecutable del discovery."""
    store = InMemoryStrategyLifecycleStore()
    deps = OrchestratorDeps(
        store=store,
        run_optimize=(lambda candidate: _runner(_good_result())),
        discovery=lambda instrument_id: discover_for_instrument(
            instrument_id=instrument_id,
            families=(family_by_name("bb_reversion"),),
            budget=DiscoveryBudget(max_trials_total=1, max_per_family=1, max_candidates=1),
        ),
    )
    orchestrator = AutoOrchestrator(deps)
    result = await orchestrator.run_cycle(instrument_id="AAA", shadow_validated=True)
    assert result.promoted
    active = await store.get_active(instrument_id="AAA")
    assert active is not None
    executable = active.active.definition["executable"]
    assert executable["presetKey"] == "bb_reversion"


# ── Hardening H1 (audit V2.32.1): hold-out inviolable en la ruta de promoción ───


def _shadow_bars(count: int = 400) -> list[Any]:
    """Barras OHLCV con timestamps crecientes (serie amplia LAB + hold-out)."""
    from datetime import date, timedelta

    from bolsa_analytics.backtest import BacktestBarInput

    base = date(2026, 1, 1)
    out = []
    for index in range(count):
        price = 100.0 + 12.0 * math.sin(index / 6.0) + index * 0.05
        out.append(
            BacktestBarInput(
                timestamp=(base + timedelta(days=index)).isoformat(),
                close=price,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                volume=1000.0,
            )
        )
    return out


def _finalist_stub() -> Any:
    from bolsa_application.discovery_catalog import family_by_name
    from bolsa_domain.entities.strategy_lifecycle import StrategyFinalist

    family = family_by_name("ema_crossover")
    definition = family.template({"fastPeriod": 5, "slowPeriod": 20})
    assert definition is not None
    return StrategyFinalist(
        candidate_id="cand-h1",
        version_id="ver-h1",
        name="h1",
        definition_hash="h1",
        definition={"executable": definition, "instrument_id": "AAA"},
    )


@pytest.mark.asyncio
async def test_run_shadow_forces_require_holdout_unconditionally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H1: la ruta de promoción fuerza ``require_holdout=True`` sin opción de escape."""
    import bolsa_application.auto_orchestrator as orchestrator_module
    from bolsa_application.strategy_shadow_phase import ShadowReplayConfig

    captured: dict[str, Any] = {}

    def _spy(**kwargs: Any) -> Any:
        captured["config"] = kwargs["config"]
        return None

    monkeypatch.setattr(orchestrator_module, "run_shadow_replay", _spy)

    bars = tuple(_shadow_bars(400))
    deps, _store = _deps()
    # No existe flag para desactivar el hold-out: la ruta lo fuerza siempre.
    deps.shadow_config = ShadowReplayConfig(window_bars=99, min_bars=10)
    deps.shadow_bars = lambda instrument_id: bars
    orchestrator = AutoOrchestrator(deps)

    await orchestrator._run_shadow(
        finalist=_finalist_stub(),
        instrument_id="AAA",
        run_id="run-h1",
        data_snapshot_id="snap-h1",
    )

    config = captured["config"]
    assert config.require_holdout is True
    assert config.lab_end is not None


def test_orchestrator_deps_has_no_holdout_escape_hatch() -> None:
    """H1: no hay campo en deps para desactivar el hold-out (contrato eliminado)."""
    from dataclasses import fields

    assert "shadow_require_holdout" not in {f.name for f in fields(OrchestratorDeps)}


@pytest.mark.asyncio
async def test_run_shadow_without_demonstrable_lab_end_does_not_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H1: sin frontera LAB demostrable no se construye el replay (fail-closed)."""
    import bolsa_application.auto_orchestrator as orchestrator_module

    called = False

    def _spy(**kwargs: Any) -> Any:
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(orchestrator_module, "run_shadow_replay", _spy)

    deps, _store = _deps()
    deps.shadow_bars = lambda instrument_id: ()  # Serie vacía ⇒ lab_end irresoluble.
    orchestrator = AutoOrchestrator(deps)

    result = await orchestrator._run_shadow(
        finalist=_finalist_stub(),
        instrument_id="AAA",
        run_id="run-h1-empty",
    )

    assert result is None
    assert called is False


