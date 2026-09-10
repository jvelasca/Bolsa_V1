"""V2.26 / A10 — Auto Orchestrator (tests herméticos, SIM-only).

Certifica el ciclo completo ESTUDIO→…→ACTIVE→vigilancia con dependencias inyectadas:
sin evidencia no promociona, el COACH puede vetar, la promoción exige shadow, y la
degradación dispara re-LAB (nunca swap directo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bolsa_application.auto_orchestrator import (
    AutoOrchestrator,
    OrchestratorDeps,
    active_strategy_decider,
)
from bolsa_application.strategy_lifecycle_store import InMemoryStrategyLifecycleStore
from bolsa_domain.entities.strategy_lifecycle import PROMOTION_GATES, ActiveStrategy

# ── Dobles ──────────────────────────────────────────────────────────────────────


@dataclass
class _Trial:
    score: float
    oos_metrics: dict[str, Any] | None = None
    max_drawdown_pct: float | None = 5.0


@dataclass
class _OptimizeResult:
    trials: list[_Trial] = field(default_factory=list)
    cpcv: dict[str, Any] | None = None
    pbo: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    edge_report: dict[str, Any] | None = None


def _good_result() -> _OptimizeResult:
    return _OptimizeResult(
        trials=[_Trial(score=1.5, oos_metrics={"score": 0.9}, max_drawdown_pct=4.0)],
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
) -> tuple[OrchestratorDeps, InMemoryStrategyLifecycleStore]:
    store = InMemoryStrategyLifecycleStore()
    deps = OrchestratorDeps(
        store=store,
        resolve_universe=(lambda: _runner(resolution)) if resolution is not None else None,
        run_optimize=(lambda candidate: _runner(runner(candidate))),
        max_candidates=3,
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
    deps, store = _deps(runner=lambda c: _good_result(), resolution=_Resolution())
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
