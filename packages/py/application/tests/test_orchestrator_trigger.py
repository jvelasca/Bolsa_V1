"""R2 — disparador gobernado del embudo AUTO (auditoría LAB 2026-11-16).

Certifica el contrato SIN tocar la red ni PostgreSQL:

* ``dryRun`` (default) no escribe NADA del lifecycle y declara lo que habría escrito.
* El techo es FINALISTA: la ruta nunca escribe ACTIVE, aunque el ciclo completo sí
  promocionaría con la misma evidencia.
* Idempotencia: repetir el mismo cuerpo devuelve el MISMO ``run_id`` con
  ``replayed=True`` y ejecuta el ciclo UNA sola vez.
* Ámbito ESTUDIO: un instrumento fuera del universo es ``TriggerScopeError`` (409).
* Fail-closed: sin evidencia el recibo es ``INCOMPLETE`` con fase y motivo, y
  ``toPhase='active'`` se rechaza (400).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from bolsa_domain.entities.strategy_lifecycle import ShadowPolicy

from bolsa_application.auto_orchestrator import (
    PHASE_FINALISTA,
    AutoOrchestrator,
    OrchestratorDeps,
)
from bolsa_application.orchestrator_trigger import (
    STATUS_COMPLETED,
    STATUS_INCOMPLETE,
    InMemoryTriggerLedger,
    OrchestratorTrigger,
    TriggerRequest,
    TriggerRequestError,
    TriggerScopeError,
    trigger_idempotency_key,
    trigger_run_id,
)
from bolsa_application.strategy_lifecycle_store import InMemoryStrategyLifecycleStore
from bolsa_application.strategy_shadow_phase import ShadowReplayConfig
from bolsa_application.strategy_top3_coach_phase import CoachThresholds

CLOCK = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


# ── Dobles ─────────────────────────────────────────────────────────────────────


@dataclass
class _Trial:
    score: float
    oos_metrics: dict[str, Any] | None = None
    max_drawdown_pct: float | None = 5.0
    params: dict[str, Any] = field(default_factory=dict)
    is_metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "returnBasis": "net",
            "netReturnPct": 12.5,
            "roundTripCostBps": 32.0,
            "expectancyCurrency": 25.0,
            "excessReturnPct": 3.0,
            "netTradeCount": 60,
        }
    )


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
        edge_report={"dsr": 0.7, "suite": {"sampleTradesCount": 60}},
    )


@dataclass
class _Resolution:
    status: str = "ok"
    instrument_ids: list[str] = field(default_factory=lambda: ["AAA"])


async def _runner(value: Any) -> Any:
    return value


class _RecordingStore(InMemoryStrategyLifecycleStore):
    """Store del lifecycle que cuenta las escrituras observadas."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def save_candidate(self, candidate: Any) -> None:
        self.calls.append("save_candidate")
        await super().save_candidate(candidate)

    async def save_evaluation(self, evaluation: Any) -> None:
        self.calls.append("save_evaluation")
        await super().save_evaluation(evaluation)

    async def save_finalist(self, finalist: Any) -> None:
        self.calls.append("save_finalist")
        await super().save_finalist(finalist)

    async def save_promotion(self, record: Any) -> None:
        self.calls.append("save_promotion")
        await super().save_promotion(record)

    async def save_active(self, record: Any) -> None:
        self.calls.append("save_active")
        await super().save_active(record)

    async def save_health(self, version_id: str, health: Any) -> None:
        self.calls.append("save_health")
        await super().save_health(version_id, health)

    async def save_coach_assessment(self, assessment: Any) -> None:
        self.calls.append("save_coach_assessment")
        await super().save_coach_assessment(assessment)

    async def save_shadow_result(self, result: Any) -> None:
        self.calls.append("save_shadow_result")
        await super().save_shadow_result(result)


class _ExplodingOptimize:
    """Runner del LAB que revienta: el recibo debe ser INCOMPLETE, no un 200 optimista."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, candidate: Any) -> Any:
        self.calls += 1
        raise RuntimeError("lab caído")


def _orchestrator(
    *,
    store: Any,
    instruments: tuple[str, ...] = ("AAA",),
    runner: Any = None,
    shadow: bool = False,
) -> AutoOrchestrator:
    deps = OrchestratorDeps(
        store=store,
        resolve_universe=lambda: _runner(_Resolution(instrument_ids=list(instruments))),
        run_optimize=(runner if runner is not None else (lambda candidate: _runner(_good_result()))),
        coach_thresholds=CoachThresholds(),
    )
    if shadow:
        deps.shadow_bars = lambda instrument_id: ()
        deps.shadow_policy = ShadowPolicy(min_closed_round_trips=1, min_return_pct=-100.0)
        deps.shadow_config = ShadowReplayConfig(window_bars=99, min_bars=10)
    return AutoOrchestrator(deps)


def _trigger(orchestrator: Any, ledger: Any = None) -> OrchestratorTrigger:
    return OrchestratorTrigger(
        orchestrator=orchestrator,
        ledger=ledger or InMemoryTriggerLedger(),
        clock=lambda: CLOCK,
    )


def _request(**overrides: Any) -> TriggerRequest:
    base: dict[str, Any] = {
        "instrument_id": "AAA",
        "account_id": "acc-1",
        "dry_run": True,
        "actor": "tester",
    }
    base.update(overrides)
    return TriggerRequest(**base)


# ── dryRun ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dry_run_writes_nothing_and_declares_it() -> None:
    store = _RecordingStore()
    orchestrator = _orchestrator(store=store)

    receipt = await _trigger(orchestrator).execute(_request(dry_run=True))

    assert store.calls == [], f"un dryRun no puede escribir el lifecycle: {store.calls}"
    assert "save_candidate" in receipt.writes
    assert "save_finalist" in receipt.writes
    # El recibo declara la fase alcanzada y los gates, no un hueco.
    assert receipt.dry_run is True
    assert receipt.phase_reached == PHASE_FINALISTA
    assert receipt.status == STATUS_COMPLETED
    assert receipt.promoted is False
    assert [gate["gate"] for gate in receipt.gates], "el recibo debe traer gates evaluados"
    assert any(gate["gate"] == "p1" for gate in receipt.gates)


@pytest.mark.asyncio
async def test_dry_run_restores_the_real_store() -> None:
    store = _RecordingStore()
    orchestrator = _orchestrator(store=store)
    trigger = _trigger(orchestrator)

    await trigger.execute(_request(dry_run=True))

    assert orchestrator.deps.store is store


# ── Techo FINALISTA ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_real_run_stops_at_finalista_and_never_writes_active() -> None:
    store = _RecordingStore()
    orchestrator = _orchestrator(store=store, shadow=True)

    receipt = await _trigger(orchestrator).execute(_request(dry_run=False))

    assert "save_active" not in store.calls
    assert "save_promotion" not in store.calls, "con techo FINALISTA no se decide promoción"
    assert "save_finalist" in store.calls
    assert await store.get_active(instrument_id="AAA") is None
    assert receipt.promoted is False
    assert receipt.active_version_id is None
    assert receipt.phase_reached == PHASE_FINALISTA


@pytest.mark.asyncio
async def test_to_phase_active_is_rejected() -> None:
    orchestrator = _orchestrator(store=_RecordingStore())

    with pytest.raises(TriggerRequestError) as exc:
        await _trigger(orchestrator).execute(_request(to_phase="active"))

    assert exc.value.code == "phase_not_allowed"


# ── Idempotencia ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_repeating_the_same_request_replays_the_same_receipt() -> None:
    store = _RecordingStore()
    ledger = InMemoryTriggerLedger()
    calls: list[str] = []

    async def _counting_run_cycle(orchestrator: Any, **kwargs: Any) -> Any:
        from bolsa_application.orchestrator_cycle import run_cycle_once

        calls.append(kwargs["instrument_id"])
        return await run_cycle_once(orchestrator, **kwargs)

    trigger = OrchestratorTrigger(
        orchestrator=_orchestrator(store=store),
        ledger=ledger,
        clock=lambda: CLOCK,
        run_cycle=_counting_run_cycle,
    )

    first = await trigger.execute(_request(dry_run=False))
    second = await trigger.execute(_request(dry_run=False))

    assert len(calls) == 1, "repetir el mismo cuerpo no re-ejecuta el ciclo"
    assert first.run_id == second.run_id
    assert second.replayed is True
    assert second.status == first.status
    assert len(ledger.entries) == 1


@pytest.mark.asyncio
async def test_dry_and_real_runs_have_distinct_keys() -> None:
    dry = trigger_idempotency_key(
        instrument_id="AAA", account_id="acc-1", snapshot=None, cycle="2026-11-16", dry_run=True
    )
    real = trigger_idempotency_key(
        instrument_id="AAA", account_id="acc-1", snapshot=None, cycle="2026-11-16", dry_run=False
    )
    assert dry != real
    assert trigger_run_id(dry) != trigger_run_id(real)
    # Estable: la misma clave da el mismo run_id (idempotencia real).
    assert trigger_run_id(dry) == trigger_run_id(dry)


# ── Ámbito ESTUDIO ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_instrument_outside_estudio_is_a_scope_conflict() -> None:
    orchestrator = _orchestrator(store=_RecordingStore(), instruments=("BBB",))

    with pytest.raises(TriggerScopeError) as exc:
        await _trigger(orchestrator).execute(_request(instrument_id="AAA"))

    assert exc.value.code == "instrument_out_of_estudio_scope"


@pytest.mark.asyncio
async def test_unresolved_universe_does_not_run() -> None:
    deps = OrchestratorDeps(store=_RecordingStore(), resolve_universe=None)
    orchestrator = AutoOrchestrator(deps)

    with pytest.raises(TriggerScopeError) as exc:
        await _trigger(orchestrator).execute(_request(instrument_id="AAA"))

    assert exc.value.code == "estudio_universe_unavailable"


# ── Fail-closed ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lab_failure_is_incomplete_with_reason_never_optimistic() -> None:
    runner = _ExplodingOptimize()
    store = _RecordingStore()
    orchestrator = _orchestrator(store=store, runner=runner)

    receipt = await _trigger(orchestrator).execute(_request(dry_run=False))

    assert runner.calls == 1
    assert receipt.status == STATUS_INCOMPLETE
    assert receipt.phase_reached != PHASE_FINALISTA
    assert any("fase_no_alcanzada" in note for note in receipt.notes)
    assert await store.get_active(instrument_id="AAA") is None


@pytest.mark.asyncio
async def test_cycle_exception_is_incomplete_and_restores_store() -> None:
    store = _RecordingStore()
    orchestrator = _orchestrator(store=store)

    async def _boom(orchestrator_: Any, **kwargs: Any) -> Any:
        raise RuntimeError("ciclo roto")

    trigger = OrchestratorTrigger(
        orchestrator=orchestrator,
        ledger=InMemoryTriggerLedger(),
        clock=lambda: CLOCK,
        run_cycle=_boom,
    )

    receipt = await trigger.execute(_request(dry_run=True))

    assert receipt.status == STATUS_INCOMPLETE
    assert receipt.phase_reached is None
    assert "ciclo_fallo:RuntimeError" in receipt.notes
    assert orchestrator.deps.store is store
