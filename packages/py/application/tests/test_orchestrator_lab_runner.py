"""V2.27 / A10 — adaptador LAB del Auto Orchestrator (tests herméticos).

Certifica que ``LabOptimizeRunner``:

* descompone el ``StrategyCandidate`` (instrumento + familia normalizada + grid),
* desempaqueta el ``(result, run)`` de *AndSave* y expone ``optimization_run_id``,
* enruta el ``edge_report`` persistido como ``edge_report_id``,
* traduce errores de dominio (``ValueError``) a ``None`` ("sin evidencia"),
* y resulta compatible con ``evaluate_optimize_result``.

Sin PG, sin red y sin IA: los use-cases se doblan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bolsa_application.orchestrator_lab_runner import (
    AUTO_LAB_GRID_DEFAULTS,
    LabOptimizeResult,
    LabOptimizeRunner,
)
from bolsa_application.strategy_lab_phase import evaluate_optimize_result
from bolsa_domain.entities.strategy_lifecycle import GateStatus, StrategyCandidate

# ── Dobles ──────────────────────────────────────────────────────────────────────


@dataclass
class _Trial:
    score: float
    oos_metrics: dict[str, Any] | None = None
    max_drawdown_pct: float | None = 5.0


@dataclass
class _Result:
    trials: list[_Trial] = field(default_factory=list)
    cpcv: dict[str, Any] | None = None
    pbo: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    edge_report: dict[str, Any] | None = None
    instrument_id: str = "AAA"


@dataclass
class _Run:
    id: str = "run-1"


class _FakeSession:
    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


def _session_factory() -> _FakeSession:
    return _FakeSession()


class _FakeUseCase:
    def __init__(self, outcome: Any) -> None:
        self._outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _good_result() -> _Result:
    return _Result(
        trials=[_Trial(score=1.5, oos_metrics={"score": 0.9}, max_drawdown_pct=4.0)],
        cpcv={"pbo": 0.1},
        pbo={"pbo": 0.1},
        walk_forward={"walkForwardEfficiency": 0.7, "wfe": 0.7},
        edge_report={"dsr": 0.5, "persistedEdgeReportId": "edge-9"},
    )


def _candidate(**overrides: Any) -> StrategyCandidate:
    base: dict[str, Any] = {
        "id": "cand-AAA-0",
        "instrument_id": "AAA",
        "strategy_family": "sma",
        "params": {},
    }
    base.update(overrides)
    return StrategyCandidate(**base)


def _runner(outcome: Any) -> tuple[LabOptimizeRunner, _FakeUseCase]:
    use_case = _FakeUseCase(outcome)
    runner = LabOptimizeRunner(_session_factory, lambda _session: use_case)
    return runner, use_case


# ── Adaptación de firma ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_maps_candidate_to_lab_call() -> None:
    runner, use_case = _runner((_good_result(), _Run()))
    await runner(_candidate())

    assert len(use_case.calls) == 1
    call = use_case.calls[0]
    assert call["instrument_id"] == "AAA"
    # ``sma`` se normaliza a la familia canónica.
    assert call["strategy_family"] == "sma_crossover"
    # Grid por defecto de la familia aplicado.
    assert call["fast_periods"] == AUTO_LAB_GRID_DEFAULTS["sma_crossover"]["fast_periods"]


@pytest.mark.asyncio
async def test_runner_honours_candidate_param_overrides() -> None:
    runner, use_case = _runner((_good_result(), _Run()))
    await runner(_candidate(params={"fast_periods": [7], "bar_limit": 250}))

    call = use_case.calls[0]
    assert call["fast_periods"] == [7]
    assert call["bar_limit"] == 250


@pytest.mark.asyncio
async def test_runner_ignores_unknown_param_keys() -> None:
    runner, use_case = _runner((_good_result(), _Run()))
    await runner(_candidate(params={"totally_unknown": 1}))

    assert "totally_unknown" not in use_case.calls[0]


# ── Identidad persistida ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_exposes_run_and_edge_report_ids() -> None:
    runner, _ = _runner((_good_result(), _Run(id="run-42")))
    result = await runner(_candidate())

    assert isinstance(result, LabOptimizeResult)
    assert result.optimization_run_id == "run-42"
    assert result.edge_report_id == "edge-9"
    # Delegación de campos al resultado real.
    assert result.instrument_id == "AAA"


@pytest.mark.asyncio
async def test_runner_accepts_bare_result_without_run() -> None:
    runner, _ = _runner(_good_result())
    result = await runner(_candidate())

    assert result is not None
    assert result.optimization_run_id is None
    assert result.edge_report_id == "edge-9"


# ── Fail-closed ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_domain_error_returns_none() -> None:
    runner, _ = _runner(ValueError("Instrumento no encontrado"))
    assert await runner(_candidate()) is None


@pytest.mark.asyncio
async def test_runner_unknown_family_still_calls_lab() -> None:
    # Una familia libre no debe romper el adaptador: la valida el LAB (fail-closed).
    runner, use_case = _runner((_good_result(), _Run()))
    await runner(_candidate(strategy_family="my_custom_family"))

    assert use_case.calls[0]["strategy_family"] == "my_custom_family"


# ── Compatibilidad con evaluate_optimize_result ─────────────────────────────────


@pytest.mark.asyncio
async def test_runner_result_feeds_evaluate_optimize_result() -> None:
    runner, _ = _runner((_good_result(), _Run(id="run-7")))
    result = await runner(_candidate())

    evaluation = evaluate_optimize_result(candidate=_candidate(), result=result)
    gates = {g.gate: g for g in evaluation.gates}

    assert gates["backtest"].status is GateStatus.PASS
    assert gates["oos"].status is GateStatus.PASS
    assert gates["walk_forward"].status is GateStatus.PASS
    # El COACH nunca se decide en el LAB.
    assert gates["coach"].status is GateStatus.NOT_EVALUATED
    assert evaluation.metrics["instrument_id"] == "AAA"
