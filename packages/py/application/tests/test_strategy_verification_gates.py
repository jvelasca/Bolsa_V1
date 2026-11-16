"""Tests de gates y veredicto advisory (Fase 5, ADR-050)."""

from __future__ import annotations

from typing import Any

from bolsa_application.dia_d_as_run import ARM_AS_RUN, ARM_CASH, ARM_HOLD_STRUCTURAL, ARM_MARKET_BH
from bolsa_application.strategy_verification import (
    GATE_FAIL,
    GATE_NOT_EVALUATED,
    GATE_PASS,
    VERDICT_CONTINUE,
    VERDICT_INCONCLUSIVE_VERSION,
    VERDICT_INSUFFICIENT_SAMPLE,
    VERDICT_PROMOTE_REQUIRES_HUMAN,
    VERDICT_RELAB,
    VERDICT_WATCH,
    EpochMeasurement,
    evaluate_verification,
)
from bolsa_application.strategy_verification_profile import (
    StrategyVerificationProfileV1,
    VerificationThresholds,
)

TODAY = "2026-09-30"


def _profile(**thresholds: Any):
    return StrategyVerificationProfileV1(
        profile_id="p",
        account_scope="acct",
        universe_instruments=("AAA",),
        thresholds=(
            VerificationThresholds(**thresholds) if thresholds else VerificationThresholds()
        ),
    )


def _epoch(
    index: int,
    *,
    as_run_r: float = 1.0,
    best_r: float = 0.5,
    certified: bool = True,
    strategy: str = "v1",
    mandate: str = "m1",
    candidate: float | None = None,
    candidate_measured: bool = False,
    as_run_return: float = 2.0,
) -> EpochMeasurement:
    return EpochMeasurement(
        epoch_id=f"epoch:{index}",
        day=f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
        to_day=f"2026-{1 + (index + 1) // 28:02d}-{1 + (index + 1) % 28:02d}",
        artifact_hash=f"hash-{index}",
        measured=True,
        certified=certified,
        arms_r={
            ARM_AS_RUN: as_run_r,
            ARM_HOLD_STRUCTURAL: best_r,
            ARM_CASH: 0.0,
            ARM_MARKET_BH: None,
        },
        arms_return_pct={ARM_AS_RUN: as_run_return, ARM_HOLD_STRUCTURAL: 1.0},
        closed_cycles=3,
        operations=3,
        consistent_decisions=3,
        strategy_version=strategy,
        mandate_version=mandate,
        candidate_measured=candidate_measured,
        candidate_return_pct=candidate,
    )


def _gates(verdict: dict[str, Any]) -> dict[str, str]:
    return {str(gate["gate"]): str(gate["status"]) for gate in verdict["gates"]}


def test_insufficient_sample_never_passes() -> None:
    verdict = evaluate_verification(
        [_epoch(index) for index in range(5)],
        profile=_profile(),
        today=TODAY,
    ).to_dict()
    assert verdict["verdict"] == VERDICT_INSUFFICIENT_SAMPLE
    assert verdict["activationAllowed"] is False
    assert _gates(verdict)["independent_sample"] == GATE_FAIL


def test_not_evaluated_health_is_never_counted_as_pass() -> None:
    verdict = evaluate_verification(
        [_epoch(index) for index in range(12)],
        profile=_profile(),
        today=TODAY,
    ).to_dict()
    assert _gates(verdict)["observed_health"] == GATE_NOT_EVALUATED
    assert verdict["verdict"] == VERDICT_WATCH


def test_continue_requires_all_gates_including_health() -> None:
    verdict = evaluate_verification(
        [_epoch(index) for index in range(12)],
        profile=_profile(),
        today=TODAY,
        health={"state": "continue"},
    ).to_dict()
    assert verdict["verdict"] == VERDICT_CONTINUE
    assert verdict["activationAllowed"] is False
    assert verdict["samples"] == 12
    assert verdict["bestArm"] == ARM_HOLD_STRUCTURAL
    assert verdict["meanExcessR"] == 0.5


def test_version_change_in_window_is_inconclusive() -> None:
    epochs = [_epoch(index) for index in range(12)]
    epochs[-1] = _epoch(11, strategy="v2")
    verdict = evaluate_verification(
        epochs, profile=_profile(), today=TODAY, health={"state": "continue"}
    ).to_dict()
    assert verdict["verdict"] == VERDICT_INCONCLUSIVE_VERSION
    assert _gates(verdict)["version_integrity"] == GATE_FAIL


def test_uncertified_artifact_downgrades_to_insufficient_sample() -> None:
    epochs = [_epoch(index) for index in range(12)]
    epochs[0] = _epoch(0, certified=False)
    verdict = evaluate_verification(
        epochs, profile=_profile(), today=TODAY, health={"state": "continue"}
    ).to_dict()
    assert verdict["verdict"] == VERDICT_INSUFFICIENT_SAMPLE
    assert _gates(verdict)["method_certified"] == GATE_FAIL


def test_stale_evidence_downgrades_the_verdict() -> None:
    verdict = evaluate_verification(
        [_epoch(index) for index in range(12)],
        profile=_profile(max_evidence_age_days=30.0),
        today="2027-06-30",
        health={"state": "continue"},
    ).to_dict()
    assert verdict["verdict"] == VERDICT_INSUFFICIENT_SAMPLE
    assert _gates(verdict)["freshness"] == GATE_FAIL


def test_sustained_underperformance_requests_relab() -> None:
    verdict = evaluate_verification(
        [_epoch(index, as_run_r=-1.0, best_r=0.5) for index in range(12)],
        profile=_profile(),
        today=TODAY,
        health={"state": "continue"},
    ).to_dict()
    assert verdict["verdict"] == VERDICT_RELAB
    assert _gates(verdict)["as_run_vs_best_arm"] == GATE_FAIL


def test_mixed_underperformance_is_only_watch() -> None:
    epochs = [
        _epoch(index, as_run_r=-2.0 if index < 4 else 1.0, best_r=0.5) for index in range(12)
    ]
    verdict = evaluate_verification(
        epochs, profile=_profile(), today=TODAY, health={"state": "continue"}
    ).to_dict()
    assert verdict["verdict"] == VERDICT_WATCH


def test_candidate_better_in_every_epoch_is_a_human_proposal_not_an_activation() -> None:
    verdict = evaluate_verification(
        [
            _epoch(index, candidate=5.0, candidate_measured=True)
            for index in range(12)
        ],
        profile=_profile(),
        today=TODAY,
        health={"state": "continue"},
    ).to_dict()
    assert verdict["verdict"] == VERDICT_PROMOTE_REQUIRES_HUMAN
    assert verdict["activationAllowed"] is False
    assert _gates(verdict)["candidate_vs_as_run"] == GATE_PASS


def test_candidate_measured_in_only_some_epochs_is_not_evaluated() -> None:
    epochs = [_epoch(index, candidate=5.0, candidate_measured=True) for index in range(12)]
    epochs[3] = _epoch(3)
    verdict = evaluate_verification(
        epochs, profile=_profile(), today=TODAY, health={"state": "continue"}
    ).to_dict()
    assert _gates(verdict)["candidate_vs_as_run"] == GATE_NOT_EVALUATED
    assert verdict["candidateMeanReturnPct"] is None


def test_health_watch_downgrades_to_watch() -> None:
    verdict = evaluate_verification(
        [_epoch(index) for index in range(12)],
        profile=_profile(),
        today=TODAY,
        health={"state": "watch"},
    ).to_dict()
    assert verdict["verdict"] == VERDICT_WATCH
    assert _gates(verdict)["observed_health"] == GATE_FAIL


def test_verdict_is_deterministic() -> None:
    epochs = [_epoch(index) for index in range(12)]
    first = evaluate_verification(epochs, profile=_profile(), today=TODAY).to_dict()
    second = evaluate_verification(epochs, profile=_profile(), today=TODAY).to_dict()
    assert first["bootstrapLow"] == second["bootstrapLow"]
    assert first["gates"] == second["gates"]


def test_bootstrap_low_is_published_as_evidence() -> None:
    verdict = evaluate_verification(
        [_epoch(index, as_run_r=1.0, best_r=0.5) for index in range(12)],
        profile=_profile(),
        today=TODAY,
        health={"state": "continue"},
    ).to_dict()
    assert verdict["bootstrapLow"] is not None
    assert verdict["bootstrapLow"] > 0.0
