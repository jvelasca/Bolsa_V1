"""Validación de adaptación (ADR-049): LAB y DÍA-D separados, fail-closed, sin PASE automático."""

from __future__ import annotations

from datetime import date, timedelta

from bolsa_application.adaptation_validation import (
    GATE_FAIL,
    GATE_NOT_EVALUATED,
    GATE_PASS,
    VERDICT_REJECTED,
    VERDICT_REQUIRES_HUMAN,
    preregistration_hash,
    validate_adaptation_proposal,
    validate_as_run_gates,
    validate_lab_gates,
)
from bolsa_application.dia_d_as_run import (
    AsRunExecutionModel,
    AsRunFill,
    AsRunLeg,
    build_as_run_artifact,
)
from bolsa_domain.entities.ohlcv_bar import OhlcvBar

DAY = "2026-01-01"


def _lab(**overrides) -> dict:
    lab = {
        "measured": True,
        "netReturnPct": 12.0,
        "maxDrawdownPct": 9.0,
        "positiveWindowPct": 66.0,
        "excessVsBuyHoldPct": 3.0,
        "roundTripCostBps": 24.0,
        "samples": 40,
        "multipleTestingCorrected": True,
    }
    lab.update(overrides)
    return lab


def _bar(timestamp: str, *, open_: float, high: float, low: float, close: float) -> OhlcvBar:
    return OhlcvBar(
        timestamp=timestamp, open=open_, high=high, low=low, close=close, volume=1_000
    )


def _leg(*, instrument_id: str = "AAA", stop: float = 95.0) -> AsRunLeg:
    return AsRunLeg(
        instrument_id=instrument_id,
        direction="long",
        quantity=10.0,
        entry=100.0,
        structural_stop=stop,
        target1=110.0,
        target2=None,
    )


def _plus(day: str, offset: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=offset)).isoformat()


def _artifact(
    day: str = DAY,
    *,
    candidate_stop: float = 97.5,
    audited: bool = True,
    candidate_as_of: str | None = DAY,
) -> dict:
    """Artefacto as-run real: el LAB no puede fabricarlo ni certificarlo por su cuenta."""
    execution = AsRunExecutionModel(
        commission_bps=5.0,
        slippage_bps=3.0,
        spread_bps=2.0,
        max_participation_pct=0.1,
    )
    entry_day = _plus(day, 1)
    exit_day = _plus(day, 2)
    bars = {
        "AAA": [
            _bar(entry_day, open_=100.0, high=105.0, low=99.0, close=104.0),
            _bar(exit_day, open_=104.0, high=111.0, low=103.0, close=110.0),
        ]
    }
    fills = [
        AsRunFill(timestamp=entry_day, instrument_id="AAA", side="buy", quantity=10.0, price=100.0),
        AsRunFill(timestamp=exit_day, instrument_id="AAA", side="sell", quantity=10.0, price=110.0),
    ]
    kwargs: dict = {
        "day": day,
        "account_id": "acc-1",
        "legs": [_leg()],
        "fills": fills,
        "bars_by_instrument": bars,
        "execution": execution,
        "candidate_legs": [_leg(stop=candidate_stop)],
        "candidate_as_of": candidate_as_of,
        "to_day": exit_day,
    }
    if audited:
        kwargs.update(
            state_source="sim_auto_positions",
            bars_source="postgres:ohlcv_bars",
            bars_timeframe="1d",
            params={
                "engineStopMultiplier": None,
                "engineTargetMultiplier": None,
                "universe": "watch",
                "execution": execution.to_dict(),
            },
            universe_instruments=["AAA"],
            bump="test-bump",
        )
    return build_as_run_artifact(**kwargs)


def _artifacts(*, candidate_stop: float = 97.5, count: int = 12, audited: bool = True) -> list[dict]:
    return [
        _artifact(day=f"2026-01-{index + 1:02d}" if index < 31 else DAY, candidate_stop=candidate_stop, audited=audited)
        for index in range(count)
    ]


def test_all_measured_and_green_still_requires_human_approval() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=_artifacts(),
    )

    assert verdict.verdict == VERDICT_REQUIRES_HUMAN
    assert all(gate.status == GATE_PASS for gate in verdict.gates)
    assert verdict.measured is True
    assert "human_approval_required" in verdict.reasons
    assert "activation_forbidden" in verdict.reasons
    payload = verdict.to_dict()
    assert payload["gates"][0]["name"] == "preregistration"
    assert payload["candidateId"] == "cand-1"
    # Los dos métodos se publican por separado y ambos en verde.
    assert payload["lab"]["status"] == GATE_PASS
    assert payload["asRun"]["status"] == GATE_PASS
    assert payload["certification"]["verdict"] == "certified"


def test_lab_and_as_run_verdicts_have_independent_hashes() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=_artifacts(),
    )

    assert verdict.lab.hash != verdict.as_run.hash
    assert verdict.lab.side == "lab"
    assert verdict.as_run.side == "as_run"


def test_lab_green_with_uncertified_as_run_is_rejected() -> None:
    """Un LAB perfecto no sustituye al DÍA-D: sin certificación, no hay veredicto favorable."""
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=_artifacts(audited=False),
    )

    assert verdict.verdict == VERDICT_REJECTED
    assert verdict.lab.status == GATE_PASS
    assert verdict.as_run.status == GATE_FAIL
    certification_gate = next(g for g in verdict.gates if g.name == "as_run_certification")
    assert certification_gate.status == GATE_FAIL
    assert certification_gate.reason == "as_run_not_certified"


def test_as_run_green_does_not_rescue_a_failed_lab() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(maxDrawdownPct=22.0),
        as_run_artifacts=_artifacts(),
    )

    assert verdict.verdict == VERDICT_REJECTED
    assert verdict.lab.status == GATE_FAIL
    assert verdict.as_run.status == GATE_PASS


def test_failed_threshold_rejects() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(maxDrawdownPct=22.0),
        as_run_artifacts=_artifacts(),
    )

    assert verdict.verdict == VERDICT_REJECTED
    gate = next(g for g in verdict.gates if g.name == "maxDrawdownPct")
    assert gate.status == GATE_FAIL
    assert gate.reason == "maxDrawdownPct_above_threshold"
    assert any(reason.endswith("gate_fail:maxDrawdownPct") for reason in verdict.reasons)


def test_unmeasured_lab_is_never_a_pass() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id=None,
        lab={"measured": False},
        as_run_artifacts=_artifacts(),
    )

    assert verdict.verdict == VERDICT_REJECTED
    assert verdict.measured is False
    metric_gates = [gate for gate in verdict.gates if gate.name in {"minNetReturnPct", "maxDrawdownPct"}]
    assert all(gate.status == GATE_NOT_EVALUATED for gate in metric_gates)
    assert "lab:gate_not_evaluated:minNetReturnPct" in verdict.reasons


def test_missing_metric_is_not_zero_and_blocks() -> None:
    lab = _lab()
    lab.pop("excessVsBuyHoldPct")
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=lab,
        as_run_artifacts=_artifacts(),
    )

    gate = next(g for g in verdict.gates if g.name == "minExcessVsBuyHoldPct")
    assert gate.status == GATE_NOT_EVALUATED
    assert gate.reason == "excessVsBuyHoldPct_not_measured"
    assert verdict.verdict == VERDICT_REJECTED


def test_preregistration_mismatch_rejects_without_measuring() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=_artifacts(),
        declared_preregistration_hash="0" * 64,
    )

    assert verdict.verdict == VERDICT_REJECTED
    assert verdict.reasons == ("preregistration_mismatch",)
    assert len(verdict.gates) == 1
    assert verdict.gates[0].status == GATE_FAIL
    # El lado as-run no se evalúa: no hay medición que contrastar con un pre-registro roto.
    assert verdict.as_run.gates == ()
    assert verdict.certification is None


def test_matching_preregistration_hash_is_accepted() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=_artifacts(),
        declared_preregistration_hash=preregistration_hash(),
    )

    assert verdict.verdict == VERDICT_REQUIRES_HUMAN


def test_missing_multiple_testing_correction_blocks() -> None:
    lab = _lab()
    lab.pop("multipleTestingCorrected")
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=lab,
        as_run_artifacts=_artifacts(),
    )

    gate = next(g for g in verdict.gates if g.name == "multiple_testing")
    assert gate.status == GATE_NOT_EVALUATED
    assert verdict.verdict == VERDICT_REJECTED


def test_insufficient_lab_sample_blocks() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(samples=1),
        as_run_artifacts=_artifacts(),
    )

    gate = next(g for g in verdict.gates if g.name == "min_samples")
    assert gate.status == GATE_FAIL
    assert gate.reason == "insufficient_sample"


def test_insufficient_as_run_sample_blocks() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=_artifacts(count=3),
    )

    gate = next(g for g in verdict.gates if g.name == "as_run_cohort")
    assert gate.status == GATE_NOT_EVALUATED
    assert gate.reason == "insufficient_as_run_sample"
    certification_gate = next(g for g in verdict.gates if g.name == "as_run_certification")
    assert certification_gate.status == GATE_NOT_EVALUATED
    assert verdict.verdict == VERDICT_REJECTED


def test_candidate_not_measured_blocks() -> None:
    artifacts = _artifacts()
    for artifact in artifacts:
        artifact["arms"] = [
            arm for arm in artifact["arms"] if arm["arm"] != "candidate"
        ]
        artifact["arms"].append(
            {"arm": "candidate", "measured": False, "realizedR": None, "reason": "no_candidate"}
        )

    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=artifacts,
    )

    gate = next(g for g in verdict.gates if g.name == "as_run_cohort")
    assert gate.status == GATE_NOT_EVALUATED
    assert gate.reason == "candidate_arm_not_measured"


def test_candidate_worse_than_as_run_rejects() -> None:
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(),
        as_run_artifacts=_artifacts(candidate_stop=80.0),
    )

    gate = next(g for g in verdict.gates if g.name == "as_run_cohort")
    assert gate.status == GATE_FAIL
    assert gate.reason == "candidate_does_not_beat_as_run"


def test_verdict_hash_is_deterministic() -> None:
    first = validate_adaptation_proposal(
        proposal_id="adp_1", candidate_id="cand-1", lab=_lab(), as_run_artifacts=_artifacts()
    ).to_dict()
    second = validate_adaptation_proposal(
        proposal_id="adp_1", candidate_id="cand-1", lab=_lab(), as_run_artifacts=_artifacts()
    ).to_dict()

    assert first["hash"] == second["hash"]


def test_partial_thresholds_are_completed_with_baseline() -> None:
    from bolsa_application.adaptation_proposals import (
        preregistration_hash as proposal_preregistration_hash,
    )

    partial = {"maxDrawdownPct": 10.0}
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1",
        candidate_id="cand-1",
        lab=_lab(maxDrawdownPct=12.0),
        as_run_artifacts=_artifacts(),
        thresholds=partial,
    )

    gate = next(g for g in verdict.gates if g.name == "maxDrawdownPct")
    assert gate.threshold == 10.0
    assert gate.status == GATE_FAIL
    assert verdict.preregistration_hash == preregistration_hash(partial)
    assert verdict.preregistration_hash == proposal_preregistration_hash(partial)


def test_lab_gates_do_not_read_the_as_run() -> None:
    """El método LAB se evalúa solo: mismos gates con o sin artefactos as-run."""
    alone = validate_lab_gates(lab=_lab())
    verdict = validate_adaptation_proposal(
        proposal_id="adp_1", candidate_id="cand-1", lab=_lab(), as_run_artifacts=_artifacts()
    )

    assert alone.to_dict() == verdict.lab.to_dict()


def test_as_run_gates_do_not_read_the_lab() -> None:
    side, certification = validate_as_run_gates(as_run_artifacts=_artifacts())

    assert side.status == GATE_PASS
    assert certification.verdict == "certified"
    assert [gate.name for gate in side.gates] == ["as_run_certification", "as_run_cohort"]
